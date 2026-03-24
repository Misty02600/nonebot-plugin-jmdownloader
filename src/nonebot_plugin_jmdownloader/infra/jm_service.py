"""JM API 服务

封装 jmcomic 库的操作，提供统一的异步接口。
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

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


def _format_episode_selection_for_filename(episodes: list[int]) -> str:
    """将章节索引压缩为适合文件名的表达形式。"""
    if not episodes:
        return "all"

    display = [episode + 1 for episode in sorted(episodes)]
    chunks: list[str] = []
    start = prev = display[0]

    for current in display[1:]:
        if current == prev + 1:
            prev = current
            continue

        chunks.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = current

    chunks.append(str(start) if start == prev else f"{start}-{prev}")
    selection = "_".join(chunks)
    if len(selection) <= 40:
        return f"ep_{selection}"

    digest = hashlib.md5(
        ",".join(str(index) for index in episodes).encode(),
        usedforsecurity=False,
    ).hexdigest()[:8]
    return f"sel_{digest}"


def build_album_output_name(
    album_id: str | int, episodes: list[int] | None = None
) -> str:
    """构建本子集输出文件名（不含扩展名）。"""
    base_name = f"album_{album_id}"
    if episodes is None:
        return base_name
    return f"{base_name}_{_format_episode_selection_for_filename(episodes)}"


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


def _build_plugin_block(config: JMOptionContext, mode: str, quote) -> str:
    """根据输出格式和模式构建插件配置块。

    mode="photo": after_photo 触发，用于单章节下载
    mode="album": after_album 触发，用于本子集下载
    """
    hook = "after_photo" if mode == "photo" else "after_album"
    filename_rule = "Pid" if mode == "photo" else "{Aoutput_name}"

    match config.output_format:
        case OutputFormat.PDF:
            return f"""  {hook}:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {quote(config.cache_dir)}
        filename_rule: {quote(filename_rule)}
"""
        case OutputFormat.ZIP:
            level = "photo" if mode == "photo" else "album"
            encrypt_block = ""
            if config.zip_password:
                encrypt_block = f"""
        encrypt:
          password: {quote(config.zip_password)}"""
            return f"""  {hook}:
    - plugin: zip
      kwargs:
        zip_dir: {quote(config.cache_dir)}
        filename_rule: {quote(filename_rule)}
        level: {level}
        suffix: zip
        delete_original_file: true{encrypt_block}
"""
        case _:
            raise ValueError(f"不支持的输出格式: {config.output_format!r}")


def create_jm_option(config: JMOptionContext, mode: str = "photo") -> JmOption:
    """根据配置构造一个新的 JmOption 实例。

    mode="photo": 单章节下载（after_photo 插件）
    mode="album": 本子集下载（after_album 插件）
    """

    def quote(value: str) -> str:
        """安全地引用 YAML 字符串值"""
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    login_block = ""
    if config.username and config.password:
        login_block = f"""  after_init:
    - plugin: login
      kwargs:
        username: {quote(config.username)}
        password: {quote(config.password)}
"""

    plugin_block = _build_plugin_block(config, mode, quote)

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
        self._photo_option = create_jm_option(config, mode="photo")
        self._album_option = create_jm_option(config, mode="album")
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
        return self._photo_option.build_jm_client()

    @property
    def output_dir(self) -> Path:
        return Path(self._photo_option.dir_rule.base_dir)

    def get_album_output_name(
        self, album: JmAlbumDetail, episodes: list[int] | None = None
    ) -> str:
        """返回本子集输出文件名（不含扩展名）。"""
        return build_album_output_name(album.id, episodes)

    async def get_photo(self, photo_id: str) -> JmPhotoDetail:
        """异步获取本子信息。

        Raises:
            MissingAlbumPhotoException: 当 photo 不存在时
        """
        return await asyncio.to_thread(self._get_client().get_photo_detail, photo_id)

    async def get_album(self, album_id: str):
        """异步获取本子集信息。

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
            downloader = JmDownloader(self._photo_option)
            with downloader as dler:
                dler.download_by_photo_detail(photo)

        await asyncio.to_thread(_sync)

    async def download_album(
        self, album: JmAlbumDetail, episodes: list[int] | None = None
    ) -> None:
        """异步下载本子集。

        episodes: 从0开始的章节索引列表，None 表示全部。
        """
        cast(Any, album).output_name = self.get_album_output_name(album, episodes)
        if episodes is not None:
            album.episode_list = [album.episode_list[i] for i in episodes]

        def _sync() -> None:
            downloader = JmDownloader(self._album_option)
            with downloader as dler:
                dler.download_by_album_detail(album)

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

    async def prepare_album_file(
        self, album: JmAlbumDetail, episodes: list[int] | None = None
    ) -> tuple[str, str] | None:
        """下载并准备本子集输出文件，返回 (文件路径, 扩展名) 或 None。

        episodes: 从0开始的章节索引列表，None 表示全部。
        """
        fmt = self._config.output_format
        ext = fmt.ext
        output_name = self.get_album_output_name(album, episodes)
        file_path = self.output_dir / f"{output_name}{ext}"

        if not file_path.exists():
            await self.download_album(album, episodes)
            if not file_path.exists():
                self._logger.error(
                    f"下载后输出文件不存在: {file_path}，可能是 {fmt} 插件执行失败"
                )
                return None

        if fmt == OutputFormat.PDF and self._config.modify_md5:
            modified_path = await prepare_pdf_with_unique_md5(
                str(file_path), str(self.output_dir), output_name
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
        """格式化本子信息（ID、标题、作者、标签、本子集信息）。"""
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

    @staticmethod
    def format_album_info(album: JmAlbumDetail) -> str:
        """格式化本子集信息（ID、标题、作者、标签、章节数）。"""
        lines = [
            f"jm{album.id} | {album.name}",
            f"🎨 作者: {album.author}",
            "🔖 标签: " + " ".join(f"#{tag}" for tag in (album.tags or [])),
            f"📚 共{len(album.episode_list)}话",
        ]
        return "\n".join(lines)
