"""JM API 服务

封装 jmcomic 库的操作，提供统一的异步接口。
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import copy
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import httpx
from jmcomic import (
    JmAlbumDetail,
    JmcomicClient,
    JmDownloader,
    JmModuleConfig,
    JmPhotoDetail,
)

from ..core.enums import OutputFormat
from .jm_option import (
    DownloadMode,
    JMOptionContext,
    copy_option_with_password,
    create_jm_option,
)
from .output_cache import OutputCache
from .output_password import resolve_output_password, validate_output_file
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


class JMService:
    """封装 JM 客户端操作，提供统一的异步接口。"""

    def __init__(self, config: JMOptionContext, logger: Logger):
        self._config = config
        self._photo_option = create_jm_option(config, mode="photo")
        self._album_option = create_jm_option(config, mode="album")
        self._logger = logger
        self._output_cache = OutputCache(
            self._photo_option.dir_rule.base_dir,
            config.output_format,
            logger,
        )

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
        return self._output_cache.output_dir

    @asynccontextmanager
    async def cache_usage(self) -> AsyncIterator[None]:
        """持有缓存共享租约，保护准备产物到外部消费完成的完整区间。

        Note:
            当前 handler 在最外层获取一次，以便让租约范围清晰覆盖准备和上传。不要在
            持有读锁时调用需要写锁的 `clear_cache()`，依赖会拒绝读锁升级。
        """
        async with self._output_cache.usage():
            yield

    async def clear_cache(self) -> None:
        """等待缓存使用者退出后，在线程中独占重建缓存目录。"""
        await self._output_cache.clear()

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

    def _resolve_password(self, content_id: str | int) -> str | None:
        template = (
            self._config.pdf_password
            if self._config.output_format == OutputFormat.PDF
            else self._config.zip_password
        )
        return resolve_output_password(template, content_id)

    def _create_request_downloader(
        self, mode: DownloadMode, password: str | None
    ) -> JmDownloader:
        base_option = self._photo_option if mode == "photo" else self._album_option
        request_option = copy_option_with_password(
            base_option, mode, self._config.output_format, password
        )
        downloader = JmDownloader(base_option)
        downloader.option = request_option
        return downloader

    async def download_photo(self, photo: JmPhotoDetail) -> None:
        """异步下载本子。"""

        password = self._resolve_password(photo.id)

        def _sync() -> None:
            downloader = self._create_request_downloader("photo", password)
            with downloader as dler:
                dler.download_by_photo_detail(photo)

        await asyncio.to_thread(_sync)

    async def download_album(
        self, album: JmAlbumDetail, episodes: list[int] | None = None
    ) -> None:
        """异步下载本子集。

        episodes: 从0开始的章节索引列表，None 表示全部。
        """
        password = self._resolve_password(album.id)
        album_for_download = copy(album)
        cast(Any, album_for_download).output_name = self.get_album_output_name(
            album, episodes
        )
        if episodes is not None:
            album_for_download.episode_list = [album.episode_list[i] for i in episodes]

        def _sync() -> None:
            downloader = self._create_request_downloader("album", password)
            with downloader as dler:
                dler.download_by_album_detail(album_for_download)

        await asyncio.to_thread(_sync)

    async def prepare_photo_file(self, photo: JmPhotoDetail) -> tuple[str, str] | None:
        """下载并准备输出文件，返回 (文件路径, 扩展名) 或 None。"""
        fmt = self._config.output_format
        ext = fmt.ext
        file_path = self.output_dir / f"{photo.id}{ext}"
        password = self._resolve_password(photo.id)

        ready = await self._output_cache.prepare(
            file_path,
            photo.id,
            password,
            lambda: self.download_photo(photo),
        )
        if not ready:
            return None

        if fmt == OutputFormat.PDF and self._config.modify_md5:
            modified_path = await prepare_pdf_with_unique_md5(
                str(file_path), str(self.output_dir), str(photo.id)
            )
            if modified_path is None:
                return None
            is_valid = await asyncio.to_thread(
                validate_output_file, modified_path, fmt, password
            )
            if not is_valid:
                await asyncio.to_thread(Path(modified_path).unlink, missing_ok=True)
                self._logger.error(f"修改 MD5 后 PDF 密码状态验证失败: {modified_path}")
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
        password = self._resolve_password(album.id)

        ready = await self._output_cache.prepare(
            file_path,
            album.id,
            password,
            lambda: self.download_album(album, episodes),
        )
        if not ready:
            return None

        if fmt == OutputFormat.PDF and self._config.modify_md5:
            modified_path = await prepare_pdf_with_unique_md5(
                str(file_path), str(self.output_dir), output_name
            )
            if modified_path is None:
                return None
            is_valid = await asyncio.to_thread(
                validate_output_file, modified_path, fmt, password
            )
            if not is_valid:
                await asyncio.to_thread(Path(modified_path).unlink, missing_ok=True)
                self._logger.error(f"修改 MD5 后 PDF 密码状态验证失败: {modified_path}")
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
