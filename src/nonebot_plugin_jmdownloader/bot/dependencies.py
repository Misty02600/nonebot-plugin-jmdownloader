"""依赖注入模块

提供服务实例化和依赖注入。NoneBot 的 Depends 会缓存结果，
同一请求中相同依赖只执行一次。

注意：部分依赖可能调用 matcher.finish() 终止流程，这是允许的。
"""

import asyncio
from typing import Annotated

from jmcomic import JmAlbumDetail, JmPhotoDetail, MissingAlbumPhotoException
from nonebot import get_driver, get_plugin_config, logger, require
from nonebot.adapters.onebot.v11 import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, Depends

from ..config import PluginConfig
from ..infra.data_manager import DataManager
from ..infra.jm_service import (
    JMOptionContext,
    JMService,
)
from ..infra.search_session import SessionCache

# 确保依赖插件已加载
require("nonebot_plugin_localstore")

from nonebot_plugin_localstore import get_plugin_cache_dir, get_plugin_data_dir

plugin_config = get_plugin_config(PluginConfig)
driver_config = get_driver().config
# region Nonebot依赖


def get_random_nickname() -> str:
    """获取一个随机机器人昵称"""
    import random

    nicknames = getattr(driver_config, "nickname", set()) or {"猫猫"}
    return random.choice(tuple(nicknames))


RandomNickname = Annotated[str, Depends(get_random_nickname)]

# endregion


# region onev11通用依赖


async def target_user_id(matcher: Matcher, arg: Message = CommandArg()) -> int:
    """解析并验证 @ 目标必填"""
    for seg in arg:
        if seg.type == "at" and seg.data.get("qq") and seg.data["qq"] != "all":
            return int(seg.data["qq"])
    await matcher.finish("请使用@指定目标用户")


TargetUserId = Annotated[int, Depends(target_user_id)]

# endregion


# region JMService

_cache_dir = get_plugin_cache_dir().as_posix()

_jm_option_config = JMOptionContext(
    cache_dir=_cache_dir,
    output_format=plugin_config.jmcomic_output_format,
    zip_password=plugin_config.jmcomic_zip_password,
    log=plugin_config.jmcomic_log,
    proxies=plugin_config.jmcomic_proxies,
    thread_count=plugin_config.jmcomic_thread_count,
    username=plugin_config.jmcomic_username,
    password=plugin_config.jmcomic_password,
    modify_md5=plugin_config.jmcomic_modify_real_md5,
)
_jm_service = JMService(_jm_option_config, logger)


_background_tasks: set[asyncio.Task[bool]] = set()


@get_driver().on_startup
async def _warmup_jm_client():
    """启动时调度后台预热，不阻塞 Bot 启动。"""
    task = asyncio.create_task(_jm_service.warmup())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def get_jm_service() -> JMService:
    """获取共享的 JMService。"""
    return _jm_service


JmServiceDep = Annotated[JMService, Depends(get_jm_service)]

# endregion

# region DataManager

_data_manager = DataManager(
    data_dir=get_plugin_data_dir(),
    default_user_limit=plugin_config.jmcomic_user_limits,
    group_mode=plugin_config.jmcomic_group_list_mode,
)


def get_data_manager() -> DataManager:
    """获取 DataManager 实例"""
    return _data_manager


DataManagerDep = Annotated[DataManager, Depends(get_data_manager)]

# endregion

# region Sessions

_sessions = SessionCache(
    default_page_size=plugin_config.jmcomic_results_per_page,
)


def get_sessions() -> SessionCache:
    """获取 SessionCache 实例"""
    return _sessions


SessionsDep = Annotated[SessionCache, Depends(get_sessions)]

# endregion

# region ArgText


async def get_arg_text(arg: Message = CommandArg()) -> str:
    """提取命令参数的纯文本

    NoneBot 的 EventPlainText() 是整条消息的文本（包含命令），
    而 CommandArg() 是去掉命令后的参数部分，但是 Message 类型。
    这个依赖提供命令参数的纯文本形式，并自动 strip。
    """
    return arg.extract_plain_text().strip()


ArgText = Annotated[str, Depends(get_arg_text)]

# endregion

# region Photo


async def get_photo(
    photo_id: ArgText, matcher: Matcher, jm: JmServiceDep
) -> JmPhotoDetail:
    """从命令参数获取 Photo（验证 + API 调用）

    1. 验证 photo_id 格式（必须是数字）
    2. 调用 API 获取 photo 详情
    3. 失败时 finish 并提示用户
    """
    if not photo_id.isdigit():
        await matcher.finish("请输入有效的jm号")
    try:
        return await jm.get_photo(photo_id)
    except MissingAlbumPhotoException:
        await matcher.finish("未查找到本子")
    except Exception:
        logger.warning(f"获取本子信息失败: photo_id={photo_id}", exc_info=True)
        await matcher.finish("查询时发生错误")


Photo = Annotated[JmPhotoDetail, Depends(get_photo)]

# endregion

# region Album


def parse_episode_selection(text: str, total: int) -> list[int]:
    """解析章节选择字符串，返回从0开始的索引列表。

    支持格式：
    - "1-5" → [0,1,2,3,4]
    - "1,3,5" → [0,2,4]
    - "1-3,5,7" → [0,1,2,4,6]

    Raises:
        ValueError: 格式无效或章节号越界
    """
    indices: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            if not start_s.isdigit() or not end_s.isdigit():
                raise ValueError(f"无效的范围格式: {part}")
            start, end = int(start_s), int(end_s)
            if start < 1 or end > total or start > end:
                raise ValueError(f"章节范围 {start}-{end} 超出范围(共{total}话)")
            indices.update(range(start - 1, end))
        elif part.isdigit():
            num = int(part)
            if num < 1 or num > total:
                raise ValueError(f"章节 {num} 超出范围(共{total}话)")
            indices.add(num - 1)
        else:
            raise ValueError(f"无效的章节格式: {part}")
    return sorted(indices)


async def get_album_with_selection(
    arg: ArgText, matcher: Matcher, jm: JmServiceDep
) -> tuple[JmAlbumDetail, list[int] | None]:
    """从命令参数获取 Album 和可选的章节选择。

    参数格式：
    - "123456" → 全部章节
    - "123456 1-5" → 第1到第5话
    - "123456 1,3,5" → 第1、3、5话
    """
    parts = arg.split(maxsplit=1)
    if not parts:
        await matcher.finish("请输入有效的jm号")

    album_id = parts[0]
    if not album_id.isdigit():
        await matcher.finish("请输入有效的jm号")

    try:
        album = await jm.get_album(album_id)
    except MissingAlbumPhotoException:
        await matcher.finish("未查找到本子集")
    except Exception:
        logger.warning(f"获取本子集信息失败: album_id={album_id}", exc_info=True)
        await matcher.finish("查询时发生错误")

    episodes: list[int] | None = None
    if len(parts) > 1:
        try:
            episodes = parse_episode_selection(parts[1], len(album.episode_list))
        except ValueError as e:
            await matcher.finish(str(e))

    return album, episodes


AlbumWithSelection = Annotated[
    tuple[JmAlbumDetail, list[int] | None], Depends(get_album_with_selection)
]

# endregion
