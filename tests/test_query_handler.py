import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from nonebot.adapters.onebot.v11 import Message


@pytest.mark.asyncio
async def test_query_handler_blurs_avatar_before_sending(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_jmdownloader.bot.handlers import query as query_module

    raw_avatar = BytesIO(b"raw-avatar")
    blurred_avatar = BytesIO(b"blurred-avatar")
    blur_mock = AsyncMock(return_value=blurred_avatar)
    send_mock = AsyncMock()

    jm = SimpleNamespace(
        format_photo_info=lambda *_args: Message("info"),
        download_avatar=AsyncMock(return_value=raw_avatar),
    )
    bot = SimpleNamespace(self_id="123456")
    matcher = SimpleNamespace(finish=AsyncMock())
    photo = SimpleNamespace(id="123", is_single_album=True)

    monkeypatch.setattr(query_module, "blur_image_async", blur_mock)
    monkeypatch.setattr(query_module, "send_forward_msg", send_mock)

    await query_module.query_handler(bot, SimpleNamespace(), matcher, photo, jm)

    blur_mock.assert_awaited_once_with(raw_avatar)
    send_mock.assert_awaited_once()

    nodes = send_mock.await_args.args[2]
    assert len(nodes) == 1

    content = nodes[0].data["content"]
    image_segment = next(segment for segment in content if segment.type == "image")
    expected_file = base64.b64encode(b"blurred-avatar").decode()
    assert image_segment.data["file"] == f"base64://{expected_file}"
