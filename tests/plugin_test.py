import pytest
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebug import App


def make_onebot_msg(message: Message) -> GroupMessageEvent:
    from time import time

    from nonebot.adapters.onebot.v11.event import Sender

    event = GroupMessageEvent(
        time=int(time()),
        sub_type="normal",
        self_id=123456,
        post_type="message",
        message_type="group",
        message_id=12345623,
        user_id=1234567890,
        group_id=1234567890,
        raw_message=message.extract_plain_text(),
        message=message,
        original_message=message,
        sender=Sender(),
        font=123456,
    )
    return event


@pytest.mark.asyncio
async def test_jm_download(app: App):
    from nonebot import require

    assert require("nonebot_plugin_jmdownloader")

    from nonebot_plugin_jmdownloader.bot.handlers.download import jm_download

    # This is a basic sanity test to verify the matcher is loaded correctly
    assert jm_download is not None
