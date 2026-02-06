"""Bot 层

NoneBot 相关的依赖注入。
"""

from .dependencies import (
    DataManagerDep,
    JmServiceDep,
    SessionsDep,
    plugin_cache_dir,
)

__all__ = [
    "DataManagerDep",
    "JmServiceDep",
    "SessionsDep",
    "plugin_cache_dir",
]
