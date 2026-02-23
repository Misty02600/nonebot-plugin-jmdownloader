"""依赖注入模块

提供服务实例化和依赖注入。NoneBot 的 Depends 会缓存结果，
同一请求中相同依赖只执行一次。

注意：部分依赖可能调用 matcher.finish() 终止流程，这是允许的。
"""

import asyncio
from typing import Annotated

from jmcomic import JmcomicException, JmPhotoDetail, MissingAlbumPhotoException
from nonebot import get_driver, get_plugin_config, logger, require
from nonebot.adapters.onebot.v11 import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg, Depends

from ..config import PluginConfig
from ..infra.data_manager import DataManager
from ..infra.jm_service import JMConfig, JMService, create_jm_service
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

plugin_cache_dir = get_plugin_cache_dir()
_cache_dir = plugin_cache_dir.as_posix()

_jm_service: JMService | None = None


@get_driver().on_startup
async def _init_jm_service():
    """启动时初始化 JM 客户端

    延迟到 on_startup 阶段，避免加载插件时就发起网络请求。
    create_jm_service 内部会通过 build_jm_client() 发起同步网络请求
    （获取最新 API 域名、登录等），因此使用 asyncio.to_thread 避免阻塞事件循环。
    """
    global _jm_service
    try:
        _jm_service = await asyncio.to_thread(
            create_jm_service,
            JMConfig(
                cache_dir=_cache_dir,
                logger=logger,
                output_format=plugin_config.jmcomic_output_format,
                zip_password=plugin_config.jmcomic_zip_password,
                log=plugin_config.jmcomic_log,
                proxies=plugin_config.jmcomic_proxies,
                thread_count=plugin_config.jmcomic_thread_count,
                username=plugin_config.jmcomic_username,
                password=plugin_config.jmcomic_password,
                modify_md5=plugin_config.jmcomic_modify_real_md5,
            ),
        )
        logger.info("JM 客户端初始化成功")
    except JmcomicException as e:
        logger.error(f"初始化 JM 客户端失败: {e}")
        raise


def get_jm_service() -> JMService:
    """获取 JMService 实例"""
    if _jm_service is None:
        raise RuntimeError("JM 客户端尚未初始化，请等待启动完成")
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
        await matcher.finish("查询时发生错误")


Photo = Annotated[JmPhotoDetail, Depends(get_photo)]

# endregion
