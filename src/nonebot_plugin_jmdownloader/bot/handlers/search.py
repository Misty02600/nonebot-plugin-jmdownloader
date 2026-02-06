"""搜索命令处理

jm搜索 和 jm下一页 命令，群聊和私聊统一处理。
"""

import asyncio

from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    ActionFailed,
    Bot,
    Message,
    MessageEvent,
    MessageSegment,
)
from nonebot.matcher import Matcher

from ...infra import blur_image_async
from .. import DataManagerDep, JmServiceDep, SessionsDep
from ..dependencies import ArgText, RandomNickname
from ..nonebot_utils import send_forward_msg
from .common import group_enabled_check, private_enabled_check

# region 辅助函数


async def build_search_result_messages(
    bot: Bot,
    photo_ids: list[str],
    dm: DataManagerDep,
    jm: JmServiceDep,
    blocked_message: str,
) -> list[MessageSegment]:
    """构建搜索结果消息列表"""
    photos = await asyncio.gather(
        *(jm.get_photo(photo_id) for photo_id in photo_ids),
        return_exceptions=True,
    )
    avatars = await asyncio.gather(
        *(jm.download_avatar(photo_id) for photo_id in photo_ids),
        return_exceptions=True,
    )

    messages = []

    for photo, avatar in zip(photos, avatars, strict=True):
        if photo is None or isinstance(photo, BaseException):
            continue

        if not dm.restriction.restricted_tags.isdisjoint(photo.tags):
            message_node = MessageSegment.node_custom(
                int(bot.self_id), "jm搜索结果", blocked_message
            )
        else:
            node_content = Message()
            node_content += jm.format_photo_info(photo)

            if not isinstance(avatar, BaseException):
                avatar = await blur_image_async(avatar)
                node_content += MessageSegment.image(avatar)

            message_node = MessageSegment.node_custom(
                int(bot.self_id), "jm搜索结果", node_content
            )
        messages.append(message_node)

    return messages


# endregion

# region 搜索事件处理函数


async def search_handler(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    query: ArgText,
    dm: DataManagerDep,
    jm: JmServiceDep,
    sessions: SessionsDep,
    nickname: RandomNickname,
):
    """处理搜索请求（群聊和私聊都触发）"""
    if not query:
        await matcher.finish("请输入要搜索的内容")

    searching_msg_id = (await matcher.send("正在搜索中..."))["message_id"]

    try:
        page = await jm.search(query)
    except Exception:
        await bot.delete_msg(message_id=searching_msg_id)
        await matcher.finish("搜索失败", reply_message=True)

    # 创建搜索会话
    session = sessions.create(
        user_id=event.user_id,
        query=query,
        results=list(page.iter_id()),
    )

    if not session.results:
        await bot.delete_msg(message_id=searching_msg_id)
        await matcher.finish("未搜索到本子", reply_message=True)

    current_results = session.get_current_page()
    blocked_message = f"{nickname}吃掉了一个不豪吃的本子"
    messages = await build_search_result_messages(
        bot, current_results, dm, jm, blocked_message
    )

    try:
        await send_forward_msg(bot, event, messages)
    except ActionFailed:
        await matcher.finish("搜索结果发送失败", reply_message=True)

    # 前进到下一页并保存会话（如果有更多结果）
    session.advance_page()
    if session.has_next_page():
        sessions.set(event.user_id, session)
        await matcher.send("搜索有更多结果，使用'jm下一页'指令查看更多")
    else:
        await matcher.send("已发送所有搜索结果")

    await bot.delete_msg(message_id=searching_msg_id)


# endregion

# region 下一页事件处理函数


async def next_page_handler(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    dm: DataManagerDep,
    jm: JmServiceDep,
    sessions: SessionsDep,
    nickname: RandomNickname,
):
    """处理下一页请求（群聊和私聊都触发）"""
    user_id = event.user_id
    session = sessions.get(user_id)
    if not session:
        await matcher.finish("没有进行中的搜索，请先使用'jm搜索'命令")

    searching_msg_id = (await matcher.send("正在搜索更多内容..."))["message_id"]

    # 如果需要获取更多 API 数据
    if session.needs_fetch_more():
        try:
            next_page = await jm.search(session.query, page=session.api_page + 1)
            session.append_results(list(next_page.iter_id()))
        except Exception:
            pass  # 获取下一页失败，继续显示已有结果

    current_results = session.get_current_page()
    blocked_message = f"{nickname}吃掉了一个不豪吃的本子"
    messages = await build_search_result_messages(
        bot, current_results, dm, jm, blocked_message
    )

    try:
        await send_forward_msg(bot, event, messages)
    except ActionFailed:
        sessions.remove(user_id)
        await bot.delete_msg(message_id=searching_msg_id)
        await matcher.finish("下一页结果发送失败", reply_message=True)

    # 前进到下一页
    session.advance_page()

    # 检查是否还有更多
    if session.is_last_page():
        sessions.remove(user_id)
        await matcher.send("已显示所有搜索结果")
    else:
        await matcher.send("搜索有更多结果，使用'jm下一页'指令查看更多")

    await bot.delete_msg(message_id=searching_msg_id)


# endregion

# region 命令注册

jm_search = on_command(
    "jm搜索",
    aliases={"JM搜索"},
    block=True,
    handlers=[
        private_enabled_check,  # 1. 私聊功能开关检查（仅私聊，禁用时静默终止）
        group_enabled_check,  # 2. 群聊启用检查（仅群聊，未启用静默终止）
        search_handler,  # 3. 搜索处理（群聊和私聊都触发）
    ],
)

jm_next_page = on_command(
    "jm下一页",
    aliases={"JM下一页"},
    block=True,
    handlers=[
        private_enabled_check,  # 1. 私聊功能开关检查（仅私聊，禁用时静默终止）
        group_enabled_check,  # 2. 群聊启用检查（仅群聊，未启用静默终止）
        next_page_handler,  # 3. 下一页处理（群聊和私聊都触发）
    ],
)

# endregion
