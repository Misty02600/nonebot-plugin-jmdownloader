"""定时任务

包含定时执行的任务，如重置用户下载次数和清理缓存。
"""

import shutil

from nonebot import logger, require

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

from ..dependencies import _data_manager, plugin_cache_dir


@scheduler.scheduled_job(
    "cron", day_of_week="mon", hour=0, minute=0, id="reset_user_limits"
)
async def reset_user_limits():
    """每周一凌晨0点重置所有用户的下载次数"""
    try:
        count = _data_manager.users.reset_all(_data_manager.default_user_limit)
        _data_manager.save_users()
        logger.info(f"已重置 {count} 个用户的下载次数")
    except Exception as e:
        logger.error(f"刷新用户下载次数时出错：{e}")


@scheduler.scheduled_job("cron", hour=3, minute=0)
async def clear_cache_dir():
    """每天凌晨3点清理缓存文件夹"""
    try:
        if plugin_cache_dir.exists():
            shutil.rmtree(plugin_cache_dir)
            plugin_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"已成功清理缓存目录：{plugin_cache_dir}")
    except Exception as e:
        logger.error(f"清理缓存目录失败：{e}")
