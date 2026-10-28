"""NoneBot JMComic 插件

JMComic 搜索、下载插件，使用 Alconna 通用消息支持多个平台。
"""

from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_uninfo")

from .config import PluginConfig

__plugin_meta__ = PluginMetadata(
    name="JMComic插件",
    description="跨平台 JMComic 搜索、下载插件，支持全局屏蔽 jm 号和 tag。",
    usage="jm下载 [jm号]：下载指定jm号的本子\n"
    "jm查询 [jm号]：查询指定jm号的本子\n"
    "jm搜索 [关键词]：搜索包含关键词的本子\n"
    "jm设置文件夹 [文件夹名]：设置本群的本子储存文件夹\n",
    type="application",
    homepage="https://github.com/Misty02600/nonebot-plugin-jmdownloader",
    config=PluginConfig,
    supported_adapters=inherit_supported_adapters(
        "nonebot_plugin_alconna", "nonebot_plugin_uninfo"
    ),
    extra={"author": "Misty02600 <xiao02600@gmail.com>"},
)

# 检测并迁移旧数据
from .migration import run_migration

run_migration()

# 导入命令模块以注册所有命令处理器
from .bot.handlers import (  # noqa: F401
    ban_id_tag,
    blacklist,
    download,
    group_control,
    query,
    scheduled,
    search,
)
