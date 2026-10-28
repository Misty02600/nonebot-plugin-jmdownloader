"""搜索命令处理

jm搜索 和 jm下一页 命令，群聊和私聊统一处理。
"""

import asyncio

from nonebot import logger, on_command
from nonebot.adapters import Bot, Event
from nonebot.exception import ActionFailed, NetworkError
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_uninfo import Uninfo

from ...infra import blur_image_async
from .. import DataManagerDep, JmServiceDep, SessionsDep
from ..dependencies import ArgText, RandomNickname
from ..nonebot_utils import recall_progress, send_forward_msg
from ..session import search_key
from .common import group_enabled_check, private_enabled_check

# region 辅助函数


async def build_search_result_messages(
    photo_ids: list[str],
    dm: DataManagerDep,
    jm: JmServiceDep,
    blocked_message: str,
) -> list[UniMessage]:
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
            message = UniMessage(blocked_message)
        else:
            message = UniMessage(jm.format_photo_info(photo))

            if not isinstance(avatar, BaseException):
                avatar = await blur_image_async(avatar)
                message.image(raw=avatar)

        messages.append(message)

    return messages


# endregion

# region 搜索事件处理函数


async def search_handler(
    bot: Bot,
    event: Event,
    session_info: Uninfo,
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

    user_id = search_key(session_info)
    searching_receipt = await UniMessage("正在搜索中...").send(target=event, bot=bot)

    try:
        try:
            page = await jm.search(query)
        except Exception:
            logger.warning(f"搜索失败: query={query}", exc_info=True)
            await matcher.finish("搜索失败")

        session = sessions.create(
            user_id=user_id,
            query=query,
            results=list(page.iter_id()),
        )

        if not session.results:
            sessions.remove(user_id)
            await matcher.finish("未搜索到本子")

        current_results = session.get_current_page()
        blocked_message = f"{nickname}吃掉了一个不豪吃的本子"
        messages = await build_search_result_messages(
            current_results, dm, jm, blocked_message
        )

        try:
            await send_forward_msg(bot, event, messages, "jm搜索结果")
        except (ActionFailed, NetworkError):
            sessions.remove(user_id)
            await matcher.finish("搜索结果发送失败")

        session.advance_page(len(current_results))
        if session.has_remaining_results():
            sessions.set(user_id, session)
            await matcher.send("搜索有更多结果，使用'jm下一页'指令查看更多")
        else:
            sessions.remove(user_id)
            await matcher.send("已发送所有搜索结果")
    finally:
        await recall_progress(searching_receipt)


# endregion

# region 下一页事件处理函数


async def next_page_handler(
    bot: Bot,
    event: Event,
    session_info: Uninfo,
    matcher: Matcher,
    dm: DataManagerDep,
    jm: JmServiceDep,
    sessions: SessionsDep,
    nickname: RandomNickname,
):
    """处理下一页请求（群聊和私聊都触发）"""
    user_id = search_key(session_info)
    session = sessions.get(user_id)
    if not session:
        await matcher.finish("没有进行中的搜索，请先使用'jm搜索'命令")

    searching_receipt = await UniMessage("正在搜索更多内容...").send(
        target=event, bot=bot
    )

    try:
        if session.needs_fetch_more():
            try:
                next_page = await jm.search(session.query, page=session.api_page + 1)
                new_ids = list(next_page.iter_id())
                if not session.append_results(new_ids) and new_ids:
                    logger.warning(
                        f"搜索下一页无新结果，停止取页: query={session.query}, "
                        f"page={session.api_page + 1}"
                    )
            except Exception:
                session.can_fetch_more = False
                logger.warning(
                    f"获取搜索下一页失败: query={session.query}, page={session.api_page + 1}",
                    exc_info=True,
                )
                await matcher.send("下一页获取失败")

        current_results = session.get_current_page()
        if not current_results:
            sessions.remove(user_id)
            await matcher.finish("已显示所有搜索结果")

        blocked_message = f"{nickname}吃掉了一个不豪吃的本子"
        messages = await build_search_result_messages(
            current_results, dm, jm, blocked_message
        )

        try:
            await send_forward_msg(bot, event, messages, "jm搜索结果")
        except (ActionFailed, NetworkError):
            sessions.remove(user_id)
            await matcher.finish("下一页结果发送失败")

        session.advance_page(len(current_results))
        if session.has_remaining_results():
            await matcher.send("搜索有更多结果，使用'jm下一页'指令查看更多")
        else:
            sessions.remove(user_id)
            await matcher.send("已显示所有搜索结果")
    finally:
        await recall_progress(searching_receipt)


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
