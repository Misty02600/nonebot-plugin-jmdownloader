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
    JmcomicClient,
    JmcomicException,
    JmDownloader,
    JmModuleConfig,
    JmPhotoDetail,
    MissingAlbumPhotoException,
    create_option_by_str,
)

from .pdf_utils import prepare_pdf_with_unique_md5

if TYPE_CHECKING:
    from loguru import Logger


class AvatarDownloadError(Exception):
    description = "下载本子封面失败"


# region 工厂函数


@dataclass
class JMConfig:
    """JM 客户端配置"""

    cache_dir: str
    logger: Logger
    log: bool = False
    proxies: str = "system"
    thread_count: int = 10
    username: str | None = None
    password: str | None = None
    modify_md5: bool = False


def create_jm_service(config: JMConfig) -> "JMService":
    """创建 JMService 实例

    Args:
        config: JM 配置

    Returns:
        JMService 实例
    """

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
{login_block}  after_photo:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {quote(config.cache_dir)}
        filename_rule: Pid
"""

    option = create_option_by_str(yaml_config, mode="yml")
    return JMService(
        option.build_jm_client(),
        JmDownloader(option),
        Path(config.cache_dir),
        config.logger,
        config.modify_md5,
    )


# endregion


class JMService:
    """JM API 服务

    封装 JM 客户端操作，提供统一的异步接口。

    Attributes:
        client: JM API 客户端
        downloader: JM 下载器
        cache_dir: 缓存目录
        logger: 日志器
        modify_md5: 是否修改 MD5
    """

    def __init__(
        self,
        client: JmcomicClient,
        downloader: JmDownloader,
        cache_dir: Path,
        logger: Logger,
        modify_md5: bool = False,
    ):
        self._client = client
        self._downloader = downloader
        self._cache_dir = cache_dir
        self._logger = logger
        self._modify_md5 = modify_md5

    # region 获取本子信息

    async def get_photo(self, photo_id: str) -> JmPhotoDetail:
        """异步获取本子信息

        Args:
            photo_id: photo/album ID

        Returns:
            JmPhotoDetail 对象

        Raises:
            MissingAlbumPhotoException: 当 photo 不存在时
            Exception: 其他获取失败的情况
        """

        def _sync() -> JmPhotoDetail:
            try:
                return self._client.get_photo_detail(photo_id)
            except MissingAlbumPhotoException:
                raise
            except Exception:
                self._logger.exception(f"获取本子信息失败: photo_id={photo_id}")
                raise

        return await asyncio.to_thread(_sync)

    # endregion

    # region 下载本子

    async def download_photo(self, photo: JmPhotoDetail) -> bool:
        """异步下载本子

        Args:
            photo: JmPhotoDetail 对象

        Returns:
            下载是否成功
        """

        def _sync() -> bool:
            try:
                with self._downloader as dler:
                    dler.download_by_photo_detail(photo)
                return True
            except JmcomicException:
                self._logger.exception(f"下载本子失败: photo_id={photo.id}")
                return False

        return await asyncio.to_thread(_sync)

    async def prepare_photo_pdf(self, photo: JmPhotoDetail) -> str | None:
        """下载并准备 PDF 文件

        Args:
            photo: JmPhotoDetail 对象

        Returns:
            PDF 文件路径，失败返回 None
        """
        pdf_path = self._cache_dir / f"{photo.id}.pdf"

        # 下载（如果不存在）
        if not pdf_path.exists():
            success = await self.download_photo(photo)
            if not success:
                return None

        # 可选的 MD5 修改
        if self._modify_md5:
            return await prepare_pdf_with_unique_md5(
                str(pdf_path), str(self._cache_dir), str(photo.id)
            )

        return str(pdf_path)

    # endregion

    # region 搜索本子

    async def search(self, query: str, page: int = 1):
        """异步搜索本子

        Args:
            query: 搜索关键词
            page: 页码（从 1 开始）

        Returns:
            搜索结果页或 None（搜索失败时）
        """

        def _sync():
            try:
                return self._client.search_site(search_query=query, page=page)
            except Exception:
                self._logger.exception(f"搜索本子请求失败: query={query}, page={page}")
                raise

        return await asyncio.to_thread(_sync)

    # endregion

    # region 封面下载

    async def download_avatar(self, photo_id: int | str) -> BytesIO:
        """下载本子封面

        Args:
            photo_id: photo/album ID

        Returns:
            封面图片的 BytesIO

        Raises:
            AvatarDownloadError: 下载失败时
        """
        for domain in JmModuleConfig.DOMAIN_IMAGE_LIST:
            url = f"https://{domain}/media/albums/{photo_id}.jpg"
            try:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.get(url, timeout=40)
                    response.raise_for_status()

                    if not response.content or len(response.content) < 1024:
                        self._logger.debug(
                            f"下载{photo_id}封面失败: domain={domain},内容过小"
                        )
                        continue

                    return BytesIO(response.content)

            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                self._logger.debug(
                    f"下载{photo_id}封面失败: domain={domain}, error={e}"
                )
                continue

        self._logger.warning(f"下载{photo_id}封面失败")
        raise AvatarDownloadError(photo_id)

    # endregion

    # region 格式化本子信息

    @staticmethod
    def format_photo_info(photo: JmPhotoDetail) -> str:
        """格式化本子基本信息

        Args:
            photo: 本子详情对象

        Returns:
            格式化的信息文本，包含 ID、标题、作者、标签
        """
        lines = [
            f"jm{photo.id} | {photo.title}",
            f"🎨 作者: {photo.author}",
            "🔖 标签: " + " ".join(f"#{tag}" for tag in (photo.tags or [])),
        ]
        return "\n".join(lines)

    # endregion
