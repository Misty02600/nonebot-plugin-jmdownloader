"""群功能控制命令

jm启用群、jm禁用群、开启jm、关闭jm、jm设置文件夹 命令。
"""

from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import (
    GROUP_ADMIN,
    GROUP_OWNER,
    ActionFailed,
    Bot,
    GroupMessageEvent,
    MessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText
from nonebot.permission import SUPERUSER

from .. import DataManagerDep
from ..dependencies import ArgText

# region 事件处理函数


async def set_folder_handler(
    bot: Bot,
    event: GroupMessageEvent,
    matcher: Matcher,
    folder_name: ArgText,
    dm: DataManagerDep,
):
    """设置本子储存文件夹"""
    if not folder_name:
        await matcher.finish("请输入要设置的文件夹名称")

    group_config = dm.get_group(event.group_id)
    group_id = event.group_id
    found_folder_id = None

    try:
        root_data = await bot.call_api("get_group_root_files", group_id=group_id)
        for folder_item in root_data.get("folders", []):
            if folder_item.get("folder_name") == folder_name:
                found_folder_id = folder_item.get("folder_id")
                break
    except ActionFailed as e:
        logger.warning(f"获取群根目录文件夹信息失败：{e}")

    if found_folder_id:
        group_config.folder_id = found_folder_id
        dm.save_group(group_id)
        await matcher.finish("已设置本子储存文件夹")
    else:
        try:
            create_result = await bot.call_api(
                "create_group_file_folder", group_id=group_id, folder_name=folder_name
            )
            ret_code = create_result["result"]["retCode"]
            if ret_code != 0:
                await matcher.finish("未找到该文件夹,主动创建文件夹失败")

            folder_id = create_result["groupItem"]["folderInfo"]["folderId"]
            group_config.folder_id = folder_id
            dm.save_group(group_id)
            await matcher.finish("已设置本子储存文件夹")
        except ActionFailed:
            logger.warning("创建文件夹失败")
            await matcher.finish("未找到该文件夹,主动创建文件夹失败")


async def enable_groups_handler(
    event: MessageEvent, matcher: Matcher, text: ArgText, dm: DataManagerDep
):
    """启用指定群号，可用空格隔开多个群"""
    group_ids = [g for g in text.split() if g.isdigit()]
    if not group_ids:
        await matcher.finish("请输入有效的群号。可以用空格隔开多个群")

    for group_id_str in group_ids:
        dm.get_group(group_id_str).enabled = True
        dm.save_group(group_id_str)

    await matcher.finish("以下群已启用jm插件功能：\n" + " ".join(group_ids))


async def disable_groups_handler(
    event: MessageEvent, matcher: Matcher, text: ArgText, dm: DataManagerDep
):
    """禁用指定群号，可用空格隔开多个群"""
    group_ids = [g for g in text.split() if g.isdigit()]
    if not group_ids:
        await matcher.finish("请输入有效的群号。可以用空格隔开多个群")

    for group_id_str in group_ids:
        dm.get_group(group_id_str).enabled = False
        dm.save_group(group_id_str)

    await matcher.finish("以下群已禁用jm插件功能：\n" + " ".join(group_ids))


async def enable_here_handler(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """启用当前群"""
    group = dm.get_group(event.group_id)
    group.enabled = True
    dm.save_group(event.group_id)
    await matcher.finish("已启用本群jm功能！")


async def disable_here_handler(
    event: GroupMessageEvent,
    dm: DataManagerDep,
    confirm: str = ArgPlainText(),
):
    group = dm.get_group(event.group_id)
    if confirm == "确认":
        group.enabled = False
        dm.save_group(event.group_id)
        await jm_disable_here.finish("已禁用本群jm功能！")


# endregion

# region 命令注册

jm_set_folder = on_command(
    "jm设置文件夹",
    aliases={"JM设置文件夹"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True,
    handlers=[set_folder_handler],
)

jm_enable_group = on_command(
    "jm启用群",
    aliases={"JM启用群", "jm开启群", "JM开启群"},
    permission=SUPERUSER,
    block=True,
    handlers=[enable_groups_handler],
)

jm_disable_group = on_command(
    "jm禁用群",
    permission=SUPERUSER,
    block=True,
    handlers=[disable_groups_handler],
)

jm_enable_here = on_command(
    "开启jm",
    aliases={"开启JM"},
    permission=SUPERUSER,
    block=True,
    handlers=[enable_here_handler],
)

jm_disable_here = on_command(
    "关闭jm",
    aliases={"关闭JM"},
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    block=True,
)


jm_disable_here.got(
    "confirm",
    prompt="禁用后只能请求神秘存在再次开启该功能！发送'确认'关闭",
)(disable_here_handler)


# endregion
