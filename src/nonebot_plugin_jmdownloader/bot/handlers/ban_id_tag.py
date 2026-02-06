"""内容过滤命令

jm禁用id、jm禁用tag 命令。
"""

from nonebot import on_command
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER

from .. import DataManagerDep
from ..dependencies import ArgText

# region 事件处理函数


async def forbid_ids_handler(matcher: Matcher, text: ArgText, dm: DataManagerDep):
    """禁用指定的 jm 号"""
    jm_ids = [t for t in text.split() if t.isdigit()]
    if not jm_ids:
        await matcher.finish("请输入有效的jm号。可以用空格隔开多个jm号")

    for jm_id in jm_ids:
        dm.restriction.restricted_ids.add(jm_id)
    dm.save_restriction()

    await matcher.finish("以下jm号已加入禁止下载列表：\n" + " ".join(jm_ids))


async def forbid_tags_handler(matcher: Matcher, text: ArgText, dm: DataManagerDep):
    """禁用指定的 tag"""
    tags = [t for t in text.split() if t]
    if not tags:
        await matcher.finish("请输入有效的tag。可以用空格隔开多个tag")

    for tag in tags:
        dm.restriction.restricted_tags.add(tag)
    dm.save_restriction()

    await matcher.finish("以下tag已加入禁止下载列表：\n" + " ".join(tags))


# endregion

# region 命令注册

jm_forbid_id = on_command(
    "jm禁用id",
    aliases={"JM禁用id"},
    permission=SUPERUSER,
    block=True,
    handlers=[forbid_ids_handler],
)

jm_forbid_tag = on_command(
    "jm禁用tag",
    aliases={"JM禁用tag"},
    permission=SUPERUSER,
    block=True,
    handlers=[forbid_tags_handler],
)

# endregion
