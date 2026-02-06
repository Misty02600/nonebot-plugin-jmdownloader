"""领域枚举定义"""

from enum import StrEnum


class OutputFormat(StrEnum):
    """输出文件格式"""

    PDF = "pdf"
    ZIP = "zip"
