"""查询命令处理

jm查询 命令，群聊和私聊统一处理。
"""

from jmcomic import JmAlbumDetail
from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.exception import ActionFailed, NetworkError
from nonebot.matcher import Matcher
from nonebot_plugin_alconna import UniMessage

from ...infra import blur_image_async
from ...infra.jm_service import AvatarDownloadError
from .. import JmServiceDep
from ..dependencies import Photo
from ..nonebot_utils import send_forward_msg
from .common import group_enabled_check, private_enabled_check

# region 事件处理函数


async def query_handler(
    bot: Bot, event: Event, matcher: Matcher, photo: Photo, jm: JmServiceDep
):
    """处理查询请求（群聊和私聊都触发）"""
    album: JmAlbumDetail | None = None
    if not photo.is_single_album:
        album = await jm.get_album_from_photo(photo)

    message = UniMessage()
    message += jm.format_photo_info(photo, album)

    try:
        avatar_bytes = await jm.download_avatar(photo.id)
        avatar_bytes = await blur_image_async(avatar_bytes)
        message.image(raw=avatar_bytes)
    except AvatarDownloadError:
        pass

    try:
        await send_forward_msg(bot, event, [message], "jm查询结果")
    except (ActionFailed, NetworkError):
        await matcher.finish("查询结果发送失败")


# endregion

# region 命令注册

jm_query = on_command(
    "jm查询",
    aliases={"JM查询"},
    block=True,
    handlers=[
        private_enabled_check,  # 1. 私聊功能开关检查（仅私聊，禁用时静默终止）
        group_enabled_check,  # 2. 群聊启用检查（仅群聊，未启用静默终止）
        query_handler,  # 3. 查询处理（群聊和私聊都触发）
    ],
)

# endregion
