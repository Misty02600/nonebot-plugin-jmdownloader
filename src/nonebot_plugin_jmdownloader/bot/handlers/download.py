"""下载命令处理

jm下载 和 jm本子集 命令，群聊和私聊统一处理。
"""

from jmcomic import JmAlbumDetail, JmPhotoDetail
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
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER

from .. import DataManagerDep, JmServiceDep
from ..dependencies import AlbumWithSelection, Photo, plugin_config
from .common import group_enabled_check, private_enabled_check

# region 前置检查 handler


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
        return f"你本周还有 {remaining_limit} 次下载次数，开始下载...\n{info}"
    return f"开始下载...\n{info}"


def build_album_progress_message(
    album: JmAlbumDetail,
    episodes: list[int] | None,
    remaining_limit: int | None,
    jm: JmServiceDep,
) -> str:
    """构建本子集进度消息"""
    info = jm.format_album_info(album)
    if episodes is not None:
        ep_display = ", ".join(str(i + 1) for i in episodes)
        info += f"\n📖 选择章节: 第{ep_display}话"
    prefix = (
        f"你本周还有 {remaining_limit} 次下载次数，开始下载..."
        if remaining_limit is not None
        else "开始下载..."
    )
    return f"{prefix}\n{info}"


# endregion

# region 事件处理函数


async def page_count_check(event: MessageEvent, matcher: Matcher, photo: Photo):
    """检查页数是否超过限制（群聊和私聊都触发）"""
    max_pages = plugin_config.jmcomic_max_page_count
    if max_pages <= 0:
        return

    if not hasattr(photo, "page_arr") or not photo.page_arr:
        return

    page_count = len(photo.page_arr)
    if page_count > max_pages:
        await matcher.finish(
            f"该本子共 {page_count} 页，超过单次下载限制({max_pages}页)"
        )


async def photo_restriction_check(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
):
    """检查内容限制，违规则根据配置惩罚（仅群聊触发）

    所有用户（包括超管）都受内容限制，但超管/管理员/群主免于惩罚。
    """
    photo_tags = list(photo.tags) if photo.tags else []
    if not dm.restriction.is_photo_restricted(photo.id, photo_tags):
        return  # 未被限制，允许下载

    # 检查是否应该惩罚
    should_punish = plugin_config.jmcomic_punish_on_violation

    # 超管/管理员/群主免惩罚（无论配置如何）
    if should_punish:
        is_privileged = await SUPERUSER(bot, event) or await (
            GROUP_ADMIN | GROUP_OWNER
        )(bot, event)
        if is_privileged:
            should_punish = False

    if should_punish:
        # 惩罚：禁言 + 黑名单
        user_id = str(event.user_id)
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
    else:
        # 只阻止，不惩罚（特权用户 或 配置关闭惩罚）
        await matcher.finish("该本子（或其tag）被禁止下载！")


async def album_enabled_check(matcher: Matcher):
    """本子集下载功能开关检查"""
    if not plugin_config.jmcomic_allow_album_download:
        await matcher.finish("本子集下载功能未启用")


async def album_restriction_check(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    selection: AlbumWithSelection,
    dm: DataManagerDep,
):
    """检查本子集内容限制，违规则根据配置惩罚（仅群聊触发）"""
    album, _ = selection
    album_tags = list(album.tags) if album.tags else []
    if not dm.restriction.is_photo_restricted(album.id, album_tags):
        return

    should_punish = plugin_config.jmcomic_punish_on_violation

    if should_punish:
        is_privileged = await SUPERUSER(bot, event) or await (
            GROUP_ADMIN | GROUP_OWNER
        )(bot, event)
        if is_privileged:
            should_punish = False

    if should_punish:
        user_id = str(event.user_id)
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
            + "该本子集（或其tag）被禁止下载！\n你已被加入本群jm黑名单"
        )
    else:
        await matcher.finish("该本子集（或其tag）被禁止下载！")


async def send_progress_message(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """发送进度消息（不扣额度，群聊和私聊都触发）"""
    is_su = await SUPERUSER(bot, event)

    # 查询剩余次数（不扣减）
    remaining: int | None = None
    if not is_su:
        remaining = dm.users.get_limit(event.user_id, dm.default_user_limit)

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
    """下载文件并上传群文件（仅群聊触发）"""
    # 下载
    try:
        result = await jm.prepare_photo_file(photo)
    except Exception:
        logger.warning(f"下载本子失败: photo_id={photo.id}", exc_info=True)
        await matcher.finish("下载失败")
    if result is None:
        await matcher.finish("下载失败")

    file_path, ext = result

    # 上传
    group_config = dm.get_group(event.group_id)
    try:
        params = {
            "group_id": event.group_id,
            "file": file_path,
            "name": f"{photo.id}{ext}",
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
    """下载文件并上传私聊文件（仅私聊触发）"""
    # 下载
    result = await jm.prepare_photo_file(photo)

    if result is None:
        await matcher.finish("下载失败")

    file_path, ext = result

    # 上传
    try:
        await bot.call_api(
            "upload_private_file",
            user_id=event.user_id,
            file=file_path,
            name=f"{photo.id}{ext}",
        )
    except ActionFailed:
        await matcher.finish("发送文件失败")


async def send_album_progress_message(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    selection: AlbumWithSelection,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """发送本子集进度消息（不扣额度，群聊和私聊都触发）"""
    album, episodes = selection
    is_su = await SUPERUSER(bot, event)

    remaining: int | None = None
    if not is_su:
        remaining = dm.users.get_limit(event.user_id, dm.default_user_limit)

    try:
        await matcher.send(build_album_progress_message(album, episodes, remaining, jm))
    except ActionFailed:
        await matcher.send("本子集信息可能被屏蔽，已开始下载")
    except NetworkError as e:
        logger.warning(f"{e},可能是协议端发送文件时间太长导致的报错")


async def group_album_download_and_upload(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    selection: AlbumWithSelection,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """下载本子集并上传群文件（仅群聊触发）"""
    album, episodes = selection
    output_name = jm.get_album_output_name(album, episodes)
    try:
        result = await jm.prepare_album_file(album, episodes)
    except Exception:
        logger.warning(f"下载本子集失败: album_id={album.id}", exc_info=True)
        await matcher.finish("下载失败")
    if result is None:
        await matcher.finish("下载失败")

    file_path, ext = result

    group_config = dm.get_group(event.group_id)
    try:
        params = {
            "group_id": event.group_id,
            "file": file_path,
            "name": f"{output_name}{ext}",
        }
        if group_config.folder_id:
            params["folder_id"] = group_config.folder_id
        await bot.call_api("upload_group_file", **params)
    except ActionFailed:
        await matcher.send("发送文件失败")


async def private_album_download_and_upload(
    bot: Bot,
    event: PrivateMessageEvent,
    matcher: Matcher,
    selection: AlbumWithSelection,
    jm: JmServiceDep,
):
    """下载本子集并上传私聊文件（仅私聊触发）"""
    album, episodes = selection
    output_name = jm.get_album_output_name(album, episodes)
    result = await jm.prepare_album_file(album, episodes)

    if result is None:
        await matcher.finish("下载失败")

    file_path, ext = result

    try:
        await bot.call_api(
            "upload_private_file",
            user_id=event.user_id,
            file=file_path,
            name=f"{output_name}{ext}",
        )
    except ActionFailed:
        await matcher.finish("发送文件失败")


async def deduct_limit(
    bot: Bot,
    event: MessageEvent,
    dm: DataManagerDep,
):
    """扣减额度（下载成功后触发，静默）"""
    if await SUPERUSER(bot, event):
        return
    dm.users.decrease_limit(event.user_id, 1, dm.default_user_limit)
    dm.save_users()


# endregion

# region 命令注册

jm_download = on_command(
    "jm下载",
    aliases={"JM下载"},
    block=True,
    handlers=[
        private_enabled_check,  # 1. 私聊功能开关检查（仅私聊，禁用时终止）
        group_enabled_check,  # 2. 群聊启用检查（仅群聊，未启用终止）
        user_blacklist_check,  # 3. 群聊黑名单检查（仅群聊）
        download_limit_check,  # 4. 下载次数检查（群聊和私聊）
        page_count_check,  # 5. 页数限制检查（群聊和私聊）
        photo_restriction_check,  # 6. 内容限制检查（仅群聊）
        send_progress_message,  # 7. 发送进度消息（不扣额度）
        group_download_and_upload,  # 8. 下载 + 上传群文件（仅群聊）
        private_download_and_upload,  # 9. 下载 + 上传私聊文件（仅私聊）
        deduct_limit,  # 10. 扣减额度（下载成功后静默扣减）
    ],
)

jm_album_download = on_command(
    "jm下载集",
    aliases={"JM下载集"},
    block=True,
    handlers=[
        album_enabled_check,
        private_enabled_check,
        group_enabled_check,
        user_blacklist_check,
        download_limit_check,
        album_restriction_check,
        send_album_progress_message,
        group_album_download_and_upload,
        private_album_download_and_upload,
        deduct_limit,
    ],
)

# endregion
