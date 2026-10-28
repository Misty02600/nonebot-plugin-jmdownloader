"""公共前置检查 handlers

提供可复用的前置检查 handler，供其他 handler 模块使用。
通过通用会话信息区分私聊与群组/频道。
"""

from nonebot.matcher import Matcher
from nonebot_plugin_uninfo import Uninfo

from .. import DataManagerDep
from ..dependencies import plugin_config
from ..session import group_key


async def group_scene(session: Uninfo) -> bool:
    """管理命令仅在群组或频道中响应。"""
    return not session.scene.is_private


async def private_enabled_check(session: Uninfo, matcher: Matcher):
    """私聊功能开关检查：私聊功能禁用时终止（仅私聊触发）"""
    if session.scene.is_private and not plugin_config.jmcomic_allow_private:
        await matcher.finish("私聊功能已禁用")


async def group_enabled_check(session: Uninfo, matcher: Matcher, dm: DataManagerDep):
    """群聊启用检查：群未启用时终止（仅群聊触发）"""
    if session.scene.is_private:
        return
    group = dm.get_group(group_key(session))
    if not group.is_enabled(dm.group_mode):
        await matcher.finish("当前群聊未开启该功能")
