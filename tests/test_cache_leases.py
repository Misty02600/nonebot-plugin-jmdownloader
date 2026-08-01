"""下载 handler 的缓存租约范围测试。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest


class FakeJMService:
    def __init__(self):
        self.events: list[str] = []
        self.lease_active = False

    @asynccontextmanager
    async def cache_usage(self):
        self.events.append("enter")
        self.lease_active = True
        try:
            yield
        finally:
            self.lease_active = False
            self.events.append("exit")

    async def prepare_photo_file(self, photo):
        assert self.lease_active
        self.events.append("prepare")
        return f"cache/{photo.id}.pdf", ".pdf"

    async def prepare_album_file(self, _album, _episodes):
        assert self.lease_active
        self.events.append("prepare")
        return "cache/album_123.pdf", ".pdf"

    def get_album_output_name(self, album, _episodes):
        return f"album_{album.id}"


class FakeBot:
    def __init__(self, jm: FakeJMService):
        self.jm = jm
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_api(self, api: str, **params: Any):
        assert self.jm.lease_active
        self.jm.events.append("upload")
        self.calls.append((api, params))


class FakeMatcher:
    async def finish(self, message: str):
        raise AssertionError(f"unexpected finish: {message}")

    async def send(self, message: str):
        raise AssertionError(f"unexpected send: {message}")


class FakeDataManager:
    def get_group(self, _group_id: int):
        return SimpleNamespace(folder_id=None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_name", "is_group", "is_album"),
    [
        ("group_download_and_upload", True, False),
        ("private_download_and_upload", False, False),
        ("group_album_download_and_upload", True, True),
        ("private_album_download_and_upload", False, True),
    ],
)
async def test_cache_lease_spans_prepare_and_upload(
    handler_name: str, is_group: bool, is_album: bool
):
    from nonebot_plugin_jmdownloader.bot.handlers import download

    jm = FakeJMService()
    bot = FakeBot(jm)
    matcher = FakeMatcher()
    event = SimpleNamespace(group_id=456, user_id=789)
    handler = getattr(download, handler_name)
    common = {"bot": bot, "event": event, "matcher": matcher, "jm": jm}
    if is_group:
        common["dm"] = FakeDataManager()
    if is_album:
        album = SimpleNamespace(id="123")
        common["selection"] = (album, None)
    else:
        common["photo"] = SimpleNamespace(id="123")

    await handler(**common)

    assert jm.events == ["enter", "prepare", "upload", "exit"]
    assert len(bot.calls) == 1
