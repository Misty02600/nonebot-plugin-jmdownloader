"""领域枚举定义"""

from enum import StrEnum


class OutputFormat(StrEnum):
    """输出文件格式"""

    PDF = "pdf"
    ZIP = "zip"


class GroupListMode(StrEnum):
    """群列表模式"""

    WHITELIST = "whitelist"  # 默认允许，显式禁止的不能用
    BLACKLIST = "blacklist"  # 默认禁止，显式允许的能用
