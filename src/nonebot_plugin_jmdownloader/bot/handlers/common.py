"""公共前置检查 handlers

提供可复用的前置检查 handler，供其他 handler 模块使用。
通过参数类型注解（如 GroupMessageEvent / PrivateMessageEvent）控制触发范围。
"""

from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.matcher import Matcher

from .. import DataManagerDep
from ..dependencies import plugin_config


async def private_enabled_check(event: PrivateMessageEvent, matcher: Matcher):
    """私聊功能开关检查：私聊功能禁用时终止（仅私聊触发）"""
    if not plugin_config.jmcomic_allow_private:
        await matcher.finish("私聊功能已禁用")


async def group_enabled_check(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """群聊启用检查：群未启用时终止（仅群聊触发）"""
    group = dm.get_group(event.group_id)
    if not group.is_enabled(dm.group_mode):
        await matcher.finish("当前群聊未开启该功能")
