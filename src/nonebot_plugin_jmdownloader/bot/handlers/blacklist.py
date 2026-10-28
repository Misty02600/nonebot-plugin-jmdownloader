"""黑名单管理命令

jm拉黑、jm解除拉黑、jm黑名单 命令。
"""

from nonebot import on_command
from nonebot.adapters import Bot, Event
from nonebot.exception import ActionFailed, NetworkError
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_uninfo import ADMIN, QryItrface, Uninfo

from .. import DataManagerDep
from ..dependencies import TargetUserId
from ..session import group_key, role_level
from .common import group_scene

# region 事件处理函数


async def can_operate_check(
    bot: Bot,
    event: Event,
    session: Uninfo,
    interface: QryItrface,
    matcher: Matcher,
    target_id: TargetUserId,
):
    """检查操作权限：不能操作比自己权限高的用户"""
    if await SUPERUSER(bot, event):
        return  # 超管可以操作任何人

    member_scene = session.guild or session.scene
    try:
        target = await interface.get_member(
            member_scene.type, member_scene.id, target_id
        )
    except (ActionFailed, NetworkError, ValueError):
        await matcher.finish("无法确认目标用户权限，操作已取消")
    if target is None or not target.roles:
        await matcher.finish("无法确认目标用户权限，操作已取消")
    if role_level(session.member) <= role_level(target):
        await matcher.finish("权限不足，无法操作该用户")


async def ban_user_handler(
    bot: Bot,
    session: Uninfo,
    matcher: Matcher,
    target_id: TargetUserId,
    dm: DataManagerDep,
):
    """将用户加入当前群的黑名单"""
    group_config = dm.get_group(group_key(session))
    group_config.blacklist.add(target_id)
    dm.save_group(group_key(session))
    message = UniMessage.at(target_id).text("已加入本群jm黑名单")
    await matcher.finish(await message.export(bot=bot))


async def unban_user_handler(
    bot: Bot,
    session: Uninfo,
    matcher: Matcher,
    target_id: TargetUserId,
    dm: DataManagerDep,
):
    """将用户移出当前群的黑名单"""
    group_config = dm.get_group(group_key(session))
    group_config.blacklist.discard(target_id)
    dm.save_group(group_key(session))
    message = UniMessage.at(target_id).text("已移出本群jm黑名单")
    await matcher.finish(await message.export(bot=bot))


async def list_blacklist_handler(
    bot: Bot, session: Uninfo, matcher: Matcher, dm: DataManagerDep
):
    """列出当前群的黑名单列表"""
    group_config = dm.get_group(group_key(session))
    if not group_config.blacklist:
        await matcher.finish("当前群的jm黑名单列表为空")

    msg = UniMessage("当前群的jm黑名单列表：\n")
    for user_id in group_config.blacklist:
        msg.at(user_id).text("\n")

    await matcher.finish(await msg.export(bot=bot))


# endregion

# region 命令注册

jm_ban_user = on_command(
    "jm拉黑",
    aliases={"JM拉黑"},
    rule=group_scene,
    permission=SUPERUSER | ADMIN(),
    block=True,
    handlers=[can_operate_check, ban_user_handler],
)

jm_unban_user = on_command(
    "jm解除拉黑",
    aliases={"JM解除拉黑", "jm移除拉黑", "jm取消拉黑", "JM移除拉黑", "JM取消拉黑"},
    rule=group_scene,
    permission=SUPERUSER | ADMIN(),
    block=True,
    handlers=[can_operate_check, unban_user_handler],
)

jm_blacklist = on_command(
    "jm黑名单",
    aliases={"JM黑名单"},
    rule=group_scene,
    permission=SUPERUSER | ADMIN(),
    block=True,
    handlers=[list_blacklist_handler],
)

# endregion
