"""领域枚举定义"""

import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        """StrEnum backport for Python < 3.11"""

        def __str__(self) -> str:
            return self.value


class OutputFormat(StrEnum):
    """输出文件格式"""

    PDF = "pdf"
    ZIP = "zip"


class GroupListMode(StrEnum):
    """群列表模式"""

    WHITELIST = "whitelist"  # 默认允许，显式禁止的不能用
    BLACKLIST = "blacklist"  # 默认禁止，显式允许的能用
