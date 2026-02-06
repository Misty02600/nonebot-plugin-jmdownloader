"""黑名单管理命令

jm拉黑、jm解除拉黑、jm黑名单 命令。
"""

from nonebot import on_command
from nonebot.adapters.onebot.v11 import (
    GROUP_ADMIN,
    GROUP_OWNER,
    Bot,
    GroupMessageEvent,
    MessageSegment,
)
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER

from .. import DataManagerDep
from ..dependencies import TargetUserId

# region 事件处理函数


async def can_operate_check(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    target_id: TargetUserId,
):
    """检查操作权限：不能操作比自己权限高的用户"""
    if await SUPERUSER(bot, event):
        return  # 超管可以操作任何人

    operator_role = event.sender.role or "member"
    target_info = await bot.get_group_member_info(
        group_id=event.group_id, user_id=target_id
    )
    target_role = target_info.get("role", "member")

    role_priority = {"owner": 3, "admin": 2, "member": 1}
    if role_priority.get(operator_role, 0) <= role_priority.get(target_role, 0):
        await matcher.finish("权限不足，无法操作该用户")


async def ban_user_handler(
    event: GroupMessageEvent,
    matcher: Matcher,
    target_id: TargetUserId,
    dm: DataManagerDep,
):
    """将用户加入当前群的黑名单"""
    group_config = dm.get_group(event.group_id)
    group_config.blacklist.add(str(target_id))
    dm.save_group(event.group_id)
    await matcher.finish(MessageSegment.at(target_id) + "已加入本群jm黑名单")


async def unban_user_handler(
    event: GroupMessageEvent,
    matcher: Matcher,
    target_id: TargetUserId,
    dm: DataManagerDep,
):
    """将用户移出当前群的黑名单"""
    group_config = dm.get_group(event.group_id)
    group_config.blacklist.discard(str(target_id))
    dm.save_group(event.group_id)
    await matcher.finish(MessageSegment.at(target_id) + "已移出本群jm黑名单")


async def list_blacklist_handler(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """列出当前群的黑名单列表"""
    group_config = dm.get_group(event.group_id)
    if not group_config.blacklist:
        await matcher.finish("当前群的jm黑名单列表为空")

    msg = "当前群的jm黑名单列表：\n"
    for user_id in group_config.blacklist:
        msg += MessageSegment.at(user_id)

    await matcher.finish(msg)


# endregion

# region 命令注册

jm_ban_user = on_command(
    "jm拉黑",
    aliases={"JM拉黑"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True,
    handlers=[can_operate_check, ban_user_handler],
)

jm_unban_user = on_command(
    "jm解除拉黑",
    aliases={"JM解除拉黑", "jm移除拉黑", "jm取消拉黑", "JM移除拉黑", "JM取消拉黑"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True,
    handlers=[can_operate_check, unban_user_handler],
)

jm_blacklist = on_command(
    "jm黑名单",
    aliases={"JM黑名单"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True,
    handlers=[list_blacklist_handler],
)

# endregion
