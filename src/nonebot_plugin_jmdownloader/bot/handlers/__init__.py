"""命令模块

所有 NoneBot 命令处理器的统一入口。
通过导入此模块来注册所有命令。
"""

# 导入所有命令模块以注册命令处理器
from . import (
    ban_id_tag,
    blacklist,
    download,
    group_control,
    query,
    scheduled,
    search,
)

__all__ = [
    "ban_id_tag",
    "blacklist",
    "download",
    "group_control",
    "query",
    "scheduled",
    "search",
]
