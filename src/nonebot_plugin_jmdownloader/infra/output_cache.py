"""输出缓存的并发、验证、发布与清理。"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import aiorwlock

from ..core.enums import OutputFormat
from .output_password import validate_output_file

if TYPE_CHECKING:
    from loguru import Logger


@dataclass
class _OutputLockEntry:
    lock: asyncio.Lock
    users: int = 0


class OutputCache:
    """管理单进程内的输出缓存生命周期。"""

    def __init__(
        self,
        cache_dir: str | Path,
        output_format: OutputFormat,
        logger: Logger,
    ):
        self.output_dir = Path(cache_dir)
        self._output_format = output_format
        self._logger = logger
        self._cache_lock = aiorwlock.RWLock()
        self._output_locks: dict[Path, _OutputLockEntry] = {}

    @asynccontextmanager
    async def usage(self) -> AsyncIterator[None]:
        """持有共享租约，保护准备产物到外部消费完成的完整区间。

        Note:
            当前 handler 在最外层获取一次，以便让租约范围清晰覆盖准备和上传。不要在
            持有读锁时调用需要写锁的 `clear()`，依赖会拒绝读锁升级。
        """
        async with self._cache_lock.reader_lock:
            yield

    def _clear_sync(self) -> None:
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def clear(self) -> None:
        """等待缓存使用者退出后，在线程中独占重建缓存目录。"""
        async with self._cache_lock.writer_lock:
            await asyncio.to_thread(self._clear_sync)

    @asynccontextmanager
    async def _acquire_output_lock(self, output_path: Path) -> AsyncIterator[None]:
        entry = self._output_locks.setdefault(
            output_path, _OutputLockEntry(lock=asyncio.Lock())
        )
        entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            entry.users -= 1
            if entry.users == 0 and self._output_locks.get(output_path) is entry:
                del self._output_locks[output_path]

    async def _discard(self, output_path: Path) -> None:
        try:
            await asyncio.to_thread(output_path.unlink, missing_ok=True)
        except OSError:
            self._logger.exception(f"清理无效输出失败: {output_path}")

    async def prepare(
        self,
        output_path: Path,
        content_id: str | int,
        password: str | None,
        download: Callable[[], Awaitable[None]],
    ) -> bool:
        """复用或重新生成一个经过验证的输出文件。

        Args:
            output_path: 最终输出路径。
            content_id: 用于日志定位的 photo 或 album ID。
            password: 当前请求解析后的密码；`None` 表示无密码。
            download: 缓存失效时生成目标文件的异步回调。

        Returns:
            输出存在且能以当前密码正确打开时返回 `True`。
        """
        async with self._acquire_output_lock(output_path):
            try:
                is_current = await asyncio.to_thread(
                    validate_output_file,
                    output_path,
                    self._output_format,
                    password,
                )
                if is_current:
                    return True

                await asyncio.to_thread(output_path.unlink, missing_ok=True)
                await download()
                if not await asyncio.to_thread(output_path.is_file):
                    self._logger.error(
                        f"下载后输出文件不存在: {output_path}，可能是 "
                        f"{self._output_format} 插件执行失败"
                    )
                    await self._discard(output_path)
                    return False

                is_valid = await asyncio.to_thread(
                    validate_output_file,
                    output_path,
                    self._output_format,
                    password,
                )
                if not is_valid:
                    self._logger.error(
                        f"输出文件密码状态验证失败: id={content_id}, "
                        f"format={self._output_format}, path={output_path}"
                    )
                    await self._discard(output_path)
                    return False

                return True
            except Exception:
                self._logger.exception(
                    f"准备输出失败: id={content_id}, "
                    f"format={self._output_format}, path={output_path}"
                )
                await self._discard(output_path)
                return False
