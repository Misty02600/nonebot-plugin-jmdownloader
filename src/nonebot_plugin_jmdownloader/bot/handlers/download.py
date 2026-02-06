"""下载命令处理

jm下载 命令，群聊和私聊统一处理。
"""

from jmcomic import JmPhotoDetail
from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import (
    ActionFailed,
    Bot,
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    NetworkError,
    PrivateMessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER

from .. import DataManagerDep, JmServiceDep
from ..dependencies import Photo

# region 前置检查 handler


async def group_enabled_check(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """群聊启用检查：群未启用则静默终止（仅群聊触发）"""
    group = dm.get_group(event.group_id)
    if not group.is_enabled(dm.default_enabled):
        await matcher.finish()


async def user_blacklist_check(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """黑名单检查：检查用户是否在群黑名单中（仅群聊触发）"""
    group = dm.get_group(event.group_id)
    if str(event.user_id) in group.blacklist:
        await matcher.finish("你已被拉入本群黑名单，无法使用此功能")


async def download_limit_check(
    bot: Bot, event: MessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """下载次数检查：检查用户是否有剩余下载次数（群聊和私聊都触发）"""
    if await SUPERUSER(bot, event):
        return  # 超管不限制
    if not dm.users.has_limit(event.user_id, dm.default_user_limit):
        await matcher.finish("你的下载次数已经用完了！")


# endregion

# region 辅助函数


def build_progress_message(
    photo: JmPhotoDetail, remaining_limit: int | None, jm: JmServiceDep
) -> str:
    """构建进度消息"""
    info = jm.format_photo_info(photo)
    if remaining_limit is not None:
        return f"{info}\n开始下载...\n你本周还有{remaining_limit}次下载次数！"
    return f"{info}\n开始下载..."


# endregion

# region 事件处理函数


async def photo_restriction_check(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
):
    """检查内容限制，违规则惩罚（仅群聊触发）"""
    if await SUPERUSER(bot, event):
        return

    user_id = str(event.user_id)
    photo_tags = list(photo.tags) if photo.tags else []
    if dm.restriction.is_photo_restricted(photo.id, photo_tags):
        # 惩罚：禁言 + 黑名单
        group_id = event.group_id
        group = dm.get_group(group_id)
        try:
            await bot.set_group_ban(
                group_id=event.group_id, user_id=event.user_id, duration=86400
            )
        except ActionFailed:
            pass
        group.blacklist.add(user_id)
        dm.save_group(group_id)
        await matcher.finish(
            MessageSegment.at(event.user_id)
            + "该本子（或其tag）被禁止下载！\n你已被加入本群jm黑名单"
        )


async def consume_and_notify(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """扣除次数 & 发送进度消息（群聊和私聊都触发）"""
    user_id = event.user_id
    is_su = await SUPERUSER(bot, event)

    # 扣除次数
    remaining: int | None = None
    if not is_su:
        remaining = dm.users.decrease_limit(user_id, 1, dm.default_user_limit)
        dm.save_users()

    # 发送进度消息
    try:
        await matcher.send(build_progress_message(photo, remaining, jm))
    except ActionFailed:
        await matcher.send("本子信息可能被屏蔽，已开始下载")
    except NetworkError as e:
        logger.warning(f"{e},可能是协议端发送文件时间太长导致的报错")


async def group_download_and_upload(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """下载 PDF 并上传群文件（仅群聊触发）"""
    # 下载
    pdf_path = await jm.prepare_photo_pdf(photo)
    if pdf_path is None:
        await matcher.finish("下载失败")

    # 上传
    group_config = dm.get_group(event.group_id)
    try:
        params = {
            "group_id": event.group_id,
            "file": pdf_path,
            "name": f"{photo.id}.pdf",
        }
        if group_config.folder_id:
            params["folder_id"] = group_config.folder_id
        await bot.call_api("upload_group_file", **params)
    except ActionFailed:
        await matcher.send("发送文件失败")


async def private_download_and_upload(
    bot: Bot,
    event: PrivateMessageEvent,
    matcher: Matcher,
    photo: Photo,
    jm: JmServiceDep,
):
    """下载 PDF 并上传私聊文件（仅私聊触发）"""
    # 下载
    pdf_path = await jm.prepare_photo_pdf(photo)

    if pdf_path is None:
        await matcher.finish("下载失败")

    # 上传
    try:
        await bot.call_api(
            "upload_private_file",
            user_id=event.user_id,
            file=pdf_path,
            name=f"{photo.id}.pdf",
        )
    except ActionFailed:
        await matcher.send("发送文件失败")


# endregion

# region 命令注册

jm_download = on_command(
    "jm下载",
    aliases={"JM下载"},
    block=True,
    handlers=[
        group_enabled_check,  # 1. 群聊启用检查（仅群聊，未启用静默终止）
        user_blacklist_check,  # 2. 群聊黑名单检查（仅群聊）
        download_limit_check,  # 3. 下载次数检查（群聊和私聊）
        photo_restriction_check,  # 4. 内容限制检查（仅群聊）
        consume_and_notify,  # 5. 扣次数 + 通知（群聊和私聊）
        group_download_and_upload,  # 6. 下载 + 上传群文件（仅群聊）
        private_download_and_upload,  # 7. 下载 + 上传私聊文件（仅私聊）
    ],
)

# endregion

