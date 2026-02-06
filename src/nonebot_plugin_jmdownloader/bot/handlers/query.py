"""查询命令处理

jm查询 命令，群聊和私聊统一处理。
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    ActionFailed,
    Bot,
    GroupMessageEvent,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.matcher import Matcher

from .. import DataManagerDep, JmServiceDep
from ..dependencies import Photo
from ..nonebot_utils import send_forward_msg

# region 前置检查 handler


async def group_enabled_check(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """群聊启用检查：群未启用则静默终止（仅群聊触发）"""
    group = dm.get_group(event.group_id)
    if not group.is_enabled(dm.default_enabled):
        await matcher.finish()


# endregion

# region 事件处理函数


async def query_handler(
    bot: Bot, event: MessageEvent, matcher: Matcher, photo: Photo, jm: JmServiceDep
):
    """处理查询请求（群聊和私聊都触发）"""
    message = Message()
    message += jm.format_photo_info(photo)

    # 获取头像
    from ...infra.jm_service import AvatarDownloadError

    try:
        avatar_bytes = await jm.download_avatar(photo.id)
        message += MessageSegment.image(avatar_bytes)
    except AvatarDownloadError:
        pass

    message_node = MessageSegment.node_custom(int(bot.self_id), "jm查询结果", message)

    try:
        await send_forward_msg(bot, event, [message_node])
    except ActionFailed:
        await matcher.finish("查询结果发送失败", reply_message=True)


# endregion

# region 命令注册

jm_query = on_command(
    "jm查询",
    aliases={"JM查询"},
    block=True,
    handlers=[
        group_enabled_check,  # 1. 群聊启用检查（仅群聊，未启用静默终止）
        query_handler,  # 2. 查询处理（群聊和私聊都触发）
    ],
)

# endregion

