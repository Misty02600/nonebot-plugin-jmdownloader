"""Handler 层通用工具函数"""

from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
)


async def send_forward_msg(
    bot: Bot, event: MessageEvent, messages: list[MessageSegment]
):
    """发送合并转发消息（根据事件类型选择 API）"""
    if isinstance(event, GroupMessageEvent):
        await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    else:
        await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )
