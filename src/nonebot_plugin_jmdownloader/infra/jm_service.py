"""JM API 服务

封装 jmcomic 库的操作，提供统一的异步接口。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from jmcomic import (
    JmAlbumDetail,
    JmcomicClient,
    JmDownloader,
    JmModuleConfig,
    JmOption,
    JmPhotoDetail,
    create_option_by_str,
)

from ..core.enums import OutputFormat
from .pdf_utils import prepare_pdf_with_unique_md5

if TYPE_CHECKING:
    from loguru import Logger


class AvatarDownloadError(Exception):
    description = "下载本子封面失败"


# region 工厂函数


@dataclass
class JMOptionContext:
    """用于构造 jmcomic option 的配置。"""

    cache_dir: str
    output_format: OutputFormat = OutputFormat.PDF
    zip_password: str | None = None
    log: bool = False
    proxies: str = "system"
    thread_count: int = 10
    username: str | None = None
    password: str | None = None
    modify_md5: bool = False


def create_jm_option(config: JMOptionContext) -> JmOption:
    """根据配置构造一个新的 JmOption 实例。"""

    def quote(value: str) -> str:
        """安全地引用 YAML 字符串值"""
        # 使用单引号包裹，内部单引号转义为两个单引号
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    # 构建 login 插件配置（如果提供了用户名和密码）
    login_block = ""
    if config.username and config.password:
        login_block = f"""  after_init:
    - plugin: login
      kwargs:
        username: {quote(config.username)}
        password: {quote(config.password)}
"""

    # 根据输出格式构建插件配置
    match config.output_format:
        case OutputFormat.PDF:
            plugin_block = f"""  after_photo:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {quote(config.cache_dir)}
        filename_rule: Pid
"""
        case OutputFormat.ZIP:
            encrypt_block = ""
            if config.zip_password:
                encrypt_block = f"""
        encrypt:
          password: {quote(config.zip_password)}"""
            plugin_block = f"""  after_photo:
    - plugin: zip
      kwargs:
        zip_dir: {quote(config.cache_dir)}
        filename_rule: Pid
        level: photo
        suffix: zip
        delete_original_file: true{encrypt_block}
"""
        case _:
            raise ValueError(f"不支持的输出格式: {config.output_format!r}")

    yaml_config = f"""\
log: {config.log}

client:
  impl: api
  retry_times: 1
  postman:
    meta_data:
      proxies: {quote(config.proxies)}

download:
  image:
    suffix: .jpg
  threading:
    image: {config.thread_count}

dir_rule:
  base_dir: {quote(config.cache_dir)}
  rule: Bd_Pid

plugins:
{login_block}{plugin_block}"""

    return create_option_by_str(yaml_config, mode="yml")


# endregion


class JMService:
    """封装 JM 客户端操作，提供统一的异步接口。"""

    def __init__(self, config: JMOptionContext, logger: Logger):
        self._config = config
        self._jm_option = create_jm_option(config)
        self._logger = logger

    async def warmup(self):
        """异步预热 JM 客户端（可选）。"""
        try:
            self._logger.info("正在预热JM客户端...")
            await asyncio.to_thread(self._get_client)
        except Exception as e:
            self._logger.warning(f"JM客户端预热失败: {e}")
            return False
        else:
            self._logger.info("JM客户端预热成功")
            return True

    def _get_client(self) -> JmcomicClient:
        return self._jm_option.build_jm_client()

    @property
    def output_dir(self) -> Path:
        return Path(self._jm_option.dir_rule.base_dir)

    async def get_photo(self, photo_id: str) -> JmPhotoDetail:
        """异步获取本子信息。

        Raises:
            MissingAlbumPhotoException: 当 photo 不存在时
        """
        return await asyncio.to_thread(self._get_client().get_photo_detail, photo_id)

    async def get_album(self, album_id: str):
        """异步获取专辑信息。

        Raises:
            MissingAlbumPhotoException: 当 album 不存在时
        """
        return await asyncio.to_thread(self._get_client().get_album_detail, album_id)

    async def get_album_from_photo(self, photo: JmPhotoDetail) -> JmAlbumDetail:
        """从 Photo 获取所属 Album。"""
        return await self.get_album(photo.album_id)

    async def download_photo(self, photo: JmPhotoDetail) -> None:
        """异步下载本子。"""

        def _sync() -> None:
            downloader = JmDownloader(self._jm_option)
            with downloader as dler:
                dler.download_by_photo_detail(photo)

        await asyncio.to_thread(_sync)

    async def prepare_photo_file(self, photo: JmPhotoDetail) -> tuple[str, str] | None:
        """下载并准备输出文件，返回 (文件路径, 扩展名) 或 None。"""
        fmt = self._config.output_format
        ext = fmt.ext
        file_path = self.output_dir / f"{photo.id}{ext}"

        if not file_path.exists():
            await self.download_photo(photo)
            if not file_path.exists():
                self._logger.error(
                    f"下载后输出文件不存在: {file_path}，可能是 {fmt} 插件执行失败"
                )
                return None

        if fmt == OutputFormat.PDF and self._config.modify_md5:
            modified_path = await prepare_pdf_with_unique_md5(
                str(file_path), str(self.output_dir), str(photo.id)
            )
            if modified_path is None:
                return None
            return (modified_path, ext)

        return (str(file_path), ext)

    async def search(self, query: str, page: int = 1):
        """异步搜索本子。"""
        return await asyncio.to_thread(
            self._get_client().search_site, search_query=query, page=page
        )

    async def download_avatar(self, photo_id: int | str) -> BytesIO:
        """下载本子封面。

        Raises:
            AvatarDownloadError: 所有域名均失败时
        """
        async with httpx.AsyncClient() as http_client:
            for domain in JmModuleConfig.DOMAIN_IMAGE_LIST:
                url = f"https://{domain}/media/albums/{photo_id}.jpg"
                try:
                    response = await http_client.get(url, timeout=40)
                    response.raise_for_status()
                    if len(response.content) >= 1024:
                        return BytesIO(response.content)
                    self._logger.debug(
                        f"下载{photo_id}封面失败: domain={domain},内容过小"
                    )
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    self._logger.debug(
                        f"下载{photo_id}封面失败: domain={domain}, error={e}"
                    )

        self._logger.warning(f"下载{photo_id}封面失败")
        raise AvatarDownloadError(photo_id)

    @staticmethod
    def format_photo_info(
        photo: JmPhotoDetail, album: JmAlbumDetail | None = None
    ) -> str:
        """格式化本子信息（ID、标题、作者、标签、专辑信息）。"""
        lines = [
            f"jm{photo.id} | {photo.title}",
            f"🎨 作者: {photo.author}",
            "🔖 标签: " + " ".join(f"#{tag}" for tag in (photo.tags or [])),
        ]

        if album:
            album_index = getattr(photo, "album_index", None)
            episode_index = album_index + 1 if album_index is not None else "?"
            lines.append(
                f"📚 第{episode_index}话 | jm{album.id} (共{len(album.episode_list)}话)"
            )

        return "\n".join(lines)
