"""输出缓存生命周期测试。"""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from typing import Any, cast

import pytest

from nonebot_plugin_jmdownloader.core.enums import OutputFormat

output_cache_module = cast(
    Any, sys.modules["nonebot_plugin_jmdownloader.infra.output_cache"]
)
OutputCache = output_cache_module.OutputCache


class DummyLogger:
    def error(self, _message: str):
        pass

    def exception(self, _message: str):
        pass


def _create_cache(cache_dir: Path) -> Any:
    return OutputCache(
        cache_dir,
        OutputFormat.PDF,
        logger=cast(Any, DummyLogger()),
    )


@pytest.mark.asyncio
async def test_clear_removes_contents_and_recreates_directory(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "output.pdf").write_bytes(b"cached")
    cache = _create_cache(cache_dir)

    await cache.clear()

    assert cache_dir.is_dir()
    assert list(cache_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_clear_waits_for_reader_and_blocks_another_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cache = _create_cache(tmp_path)
    first_reader_entered = asyncio.Event()
    release_first_reader = asyncio.Event()
    cleanup_entered = asyncio.Event()
    release_cleanup = threading.Event()
    second_reader_entered = asyncio.Event()
    loop = asyncio.get_running_loop()

    def blocking_clear() -> None:
        loop.call_soon_threadsafe(cleanup_entered.set)
        release_cleanup.wait(timeout=2)

    monkeypatch.setattr(cache, "_clear_sync", blocking_clear)

    async def hold_first_reader() -> None:
        async with cache.usage():
            first_reader_entered.set()
            await release_first_reader.wait()

    async def enter_second_reader() -> None:
        async with cache.usage():
            second_reader_entered.set()

    first_reader = asyncio.create_task(hold_first_reader())
    await first_reader_entered.wait()
    cleanup = asyncio.create_task(cache.clear())
    await asyncio.sleep(0)

    assert not cleanup_entered.is_set()

    release_first_reader.set()
    await asyncio.wait_for(cleanup_entered.wait(), timeout=1)
    second_reader = asyncio.create_task(enter_second_reader())
    await asyncio.sleep(0)

    assert not second_reader_entered.is_set()

    release_cleanup.set()
    await asyncio.gather(first_reader, cleanup, second_reader)

    assert second_reader_entered.is_set()
