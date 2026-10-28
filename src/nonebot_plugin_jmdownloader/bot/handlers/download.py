"""下载命令处理

jm下载 和 jm本子集 命令，群聊和私聊统一处理。
"""

from jmcomic import JmAlbumDetail, JmPhotoDetail
from nonebot import logger, on_command
from nonebot.adapters import Bot, Event
from nonebot.exception import ActionFailed, NetworkError
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_alconna.uniseg import SerializeFailed
from nonebot_plugin_uninfo import Uninfo

from .. import DataManagerDep, JmServiceDep
from ..dependencies import AlbumWithSelection, Photo, plugin_config
from ..nonebot_utils import send_file
from ..session import group_key, is_admin, is_onebot_v11, user_key
from .common import group_enabled_check, private_enabled_check

# region 前置检查 handler


async def user_blacklist_check(session: Uninfo, matcher: Matcher, dm: DataManagerDep):
    """黑名单检查：检查用户是否在群黑名单中（仅群聊触发）"""
    if session.scene.is_private:
        return
    group = dm.get_group(group_key(session))
    if session.user.id in group.blacklist:
        await matcher.finish("你已被拉入本群黑名单，无法使用此功能")


async def download_limit_check(
    bot: Bot, event: Event, session: Uninfo, matcher: Matcher, dm: DataManagerDep
):
    """下载次数检查：检查用户是否有剩余下载次数（群聊和私聊都触发）"""
    if await SUPERUSER(bot, event):
        return  # 超管不限制
    if not dm.users.has_limit(user_key(session), dm.default_user_limit):
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


async def page_count_check(matcher: Matcher, photo: Photo):
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


async def enforce_restriction(
    bot: Bot,
    event: Event,
    session: Uninfo,
    matcher: Matcher,
    dm: DataManagerDep,
    photo_id: str,
    tags: list[str],
    label: str,
):
    """群组/频道统一限制；角色未知时只阻止，QQ 额外尝试禁言。"""
    if session.scene.is_private:
        return
    if not dm.restriction.is_photo_restricted(photo_id, tags):
        return
    privileged = await SUPERUSER(bot, event) or is_admin(session)
    known_role = session.member is not None and bool(session.member.roles)
    if plugin_config.jmcomic_punish_on_violation and known_role and not privileged:
        key = group_key(session)
        group = dm.get_group(key)
        if is_onebot_v11(session):
            try:
                await bot.call_api(
                    "set_group_ban",
                    group_id=int(session.scene.id),
                    user_id=int(session.user.id),
                    duration=86400,
                )
            except (ActionFailed, NetworkError):
                pass
        group.blacklist.add(session.user.id)
        dm.save_group(key)
        message = UniMessage.at(session.user.id).text(
            f"该{label}（或其tag）被禁止下载！\n你已被加入本群jm黑名单"
        )
        await matcher.finish(await message.export(bot=bot))
    await matcher.finish(f"该{label}（或其tag）被禁止下载！")


async def photo_restriction_check(
    bot: Bot,
    event: Event,
    session: Uninfo,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
):
    await enforce_restriction(
        bot, event, session, matcher, dm, photo.id, list(photo.tags or []), "本子"
    )


async def album_enabled_check(matcher: Matcher):
    """本子集下载功能开关检查"""
    if not plugin_config.jmcomic_allow_album_download:
        await matcher.finish("本子集下载功能未启用")


async def album_restriction_check(
    bot: Bot,
    event: Event,
    session: Uninfo,
    matcher: Matcher,
    selection: AlbumWithSelection,
    dm: DataManagerDep,
):
    """检查群组/频道的本子集内容限制。"""
    album, _ = selection
    await enforce_restriction(
        bot, event, session, matcher, dm, album.id, list(album.tags or []), "本子集"
    )


async def send_progress_message(
    bot: Bot,
    event: Event,
    session: Uninfo,
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
        remaining = dm.users.get_limit(user_key(session), dm.default_user_limit)

    # 发送进度消息
    try:
        await matcher.send(build_progress_message(photo, remaining, jm))
    except ActionFailed:
        await matcher.send("本子信息可能被屏蔽，已开始下载")
    except NetworkError as e:
        logger.warning(f"{e},可能是协议端发送文件时间太长导致的报错")


async def upload_prepared_file(
    bot: Bot,
    event: Event,
    session: Uninfo,
    matcher: Matcher,
    dm: DataManagerDep,
    file_path: str,
    name: str,
):
    folder_id = None
    if not session.scene.is_private:
        folder_id = dm.get_group(group_key(session)).folder_id
    try:
        await send_file(bot, event, session, file_path, name, folder_id)
    except SerializeFailed:
        await matcher.finish("当前平台不支持文件发送，未扣除下载次数")
    except (ActionFailed, NetworkError):
        await matcher.finish("发送文件失败，未扣除下载次数")


async def download_and_upload(
    bot: Bot,
    event: Event,
    session: Uninfo,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """所有平台共用下载流程；缓存租约覆盖上传全过程。"""
    async with jm.cache_usage():
        try:
            result = await jm.prepare_photo_file(photo)
        except Exception:
            logger.warning(f"下载本子失败: photo_id={photo.id}", exc_info=True)
            await matcher.finish("下载失败")

        if result is None:
            await matcher.finish("下载失败")

        file_path, ext = result

        await upload_prepared_file(
            bot, event, session, matcher, dm, file_path, f"{photo.id}{ext}"
        )


async def send_album_progress_message(
    bot: Bot,
    event: Event,
    session: Uninfo,
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
        remaining = dm.users.get_limit(user_key(session), dm.default_user_limit)

    try:
        await matcher.send(build_album_progress_message(album, episodes, remaining, jm))
    except ActionFailed:
        await matcher.send("本子集信息可能被屏蔽，已开始下载")
    except NetworkError as e:
        logger.warning(f"{e},可能是协议端发送文件时间太长导致的报错")


async def album_download_and_upload(
    bot: Bot,
    event: Event,
    session: Uninfo,
    matcher: Matcher,
    selection: AlbumWithSelection,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """下载并发送本子集，缓存租约覆盖上传全过程。"""
    album, episodes = selection
    output_name = jm.get_album_output_name(album, episodes)
    async with jm.cache_usage():
        try:
            result = await jm.prepare_album_file(album, episodes)
        except Exception:
            logger.warning(f"下载本子集失败: album_id={album.id}", exc_info=True)
            await matcher.finish("下载失败")
        if result is None:
            await matcher.finish("下载失败")

        file_path, ext = result

        await upload_prepared_file(
            bot, event, session, matcher, dm, file_path, f"{output_name}{ext}"
        )


async def deduct_limit(
    bot: Bot,
    event: Event,
    session: Uninfo,
    dm: DataManagerDep,
):
    """扣减额度（下载成功后触发，静默）"""
    if await SUPERUSER(bot, event):
        return
    dm.users.decrease_limit(user_key(session), 1, dm.default_user_limit)
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
        download_and_upload,  # 8. 下载并发送文件（群组、频道或私聊）
        deduct_limit,  # 9. 发送成功后扣减额度
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
        album_download_and_upload,
        deduct_limit,
    ],
)

# endregion
