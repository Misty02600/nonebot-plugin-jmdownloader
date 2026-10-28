"""群功能控制命令

jm启用群、jm禁用群、开启jm、关闭jm、jm设置文件夹 命令。
"""

from nonebot import logger, on_command
from nonebot.adapters import Bot
from nonebot.exception import ActionFailed, NetworkError
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText
from nonebot.permission import SUPERUSER
from nonebot_plugin_uninfo import ADMIN, Uninfo

from .. import DataManagerDep
from ..dependencies import ArgText
from ..session import group_key, is_onebot_v11
from .common import group_scene

# region 事件处理函数


async def set_folder_handler(
    bot: Bot,
    session: Uninfo,
    matcher: Matcher,
    folder_name: ArgText,
    dm: DataManagerDep,
):
    """设置本子储存文件夹"""
    if not is_onebot_v11(session):
        await matcher.finish("指定文件夹上传仅支持 OneBot V11 群文件")
    if not folder_name:
        await matcher.finish("请输入要设置的文件夹名称")

    group_config = dm.get_group(group_key(session))
    group_id = int(session.scene.id)
    found_folder_id = None

    try:
        root_data = await bot.call_api("get_group_root_files", group_id=group_id)
        for folder_item in root_data.get("folders", []):
            if folder_item.get("folder_name") == folder_name:
                found_folder_id = folder_item.get("folder_id")
                break
    except (ActionFailed, NetworkError) as e:
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
        except (ActionFailed, NetworkError):
            logger.warning("创建文件夹失败")
            await matcher.finish("未找到该文件夹,主动创建文件夹失败")


async def enable_groups_handler(
    session: Uninfo, matcher: Matcher, text: ArgText, dm: DataManagerDep
):
    """启用指定群号，可用空格隔开多个群"""
    group_ids = [g for g in text.split() if not is_onebot_v11(session) or g.isdigit()]
    if not group_ids:
        await matcher.finish("请输入有效的群号。可以用空格隔开多个群")

    for group_id_str in group_ids:
        key = group_key(session, group_id_str)
        dm.get_group(key).enabled = True
        dm.save_group(key)

    await matcher.finish("以下群已启用jm插件功能：\n" + " ".join(group_ids))


async def disable_groups_handler(
    session: Uninfo, matcher: Matcher, text: ArgText, dm: DataManagerDep
):
    """禁用指定群号，可用空格隔开多个群"""
    group_ids = [g for g in text.split() if not is_onebot_v11(session) or g.isdigit()]
    if not group_ids:
        await matcher.finish("请输入有效的群号。可以用空格隔开多个群")

    for group_id_str in group_ids:
        key = group_key(session, group_id_str)
        dm.get_group(key).enabled = False
        dm.save_group(key)

    await matcher.finish("以下群已禁用jm插件功能：\n" + " ".join(group_ids))


async def enable_here_handler(session: Uninfo, matcher: Matcher, dm: DataManagerDep):
    """启用当前群"""
    group = dm.get_group(group_key(session))
    group.enabled = True
    dm.save_group(group_key(session))
    await matcher.finish("已启用本群jm功能！")


async def disable_here_handler(
    session: Uninfo,
    dm: DataManagerDep,
    confirm: str = ArgPlainText(),
):
    group = dm.get_group(group_key(session))
    if confirm == "确认":
        group.enabled = False
        dm.save_group(group_key(session))
        await jm_disable_here.finish("已禁用本群jm功能！")


# endregion

# region 命令注册

jm_set_folder = on_command(
    "jm设置文件夹",
    aliases={"JM设置文件夹"},
    rule=group_scene,
    permission=SUPERUSER | ADMIN(),
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
    rule=group_scene,
    permission=SUPERUSER,
    block=True,
    handlers=[enable_here_handler],
)

jm_disable_here = on_command(
    "关闭jm",
    aliases={"关闭JM"},
    rule=group_scene,
    permission=SUPERUSER | ADMIN(),
    block=True,
)


jm_disable_here.got(
    "confirm",
    prompt="禁用后只能请求神秘存在再次开启该功能！发送'确认'关闭",
)(disable_here_handler)


# endregion
