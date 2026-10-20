"""搜索会话核心实体"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class SearchSession:
    """用户搜索会话

    封装搜索状态和翻页逻辑。

    Attributes:
        query: 搜索关键词
        results: 已获取的所有结果 ID
        display_idx: 下一条待展示结果的索引
        api_page: 当前 API 页码
        page_size: 每页显示数量
        can_fetch_more: 是否允许继续取页，取尽、重复页或请求失败后停止
    """

    query: str
    results: list[str] = field(default_factory=list)
    display_idx: int = 0
    api_page: int = 1
    page_size: int = 20
    can_fetch_more: bool = field(init=False)

    # JM API 每页返回的数量（固定值）
    API_PAGE_SIZE: ClassVar[int] = 80

    def __post_init__(self) -> None:
        self.can_fetch_more = len(self.results) >= self.API_PAGE_SIZE

    def get_current_page(self) -> list[str]:
        """获取当前页的结果 ID 列表"""
        end_idx = self.display_idx + self.page_size
        return self.results[self.display_idx : end_idx]

    def has_remaining_results(self) -> bool:
        return self.display_idx < len(self.results) or self.can_fetch_more

    def needs_fetch_more(self) -> bool:
        """检查是否需要获取更多 API 数据"""
        next_end = self.display_idx + self.page_size * 2
        return next_end > len(self.results) and self.can_fetch_more

    def append_results(self, new_ids: list[str]) -> bool:
        """追加成功获取的 API 页，并更新是否允许继续取页。

        Args:
            new_ids: 新的结果 ID 列表

        Returns:
            有新 ID 时追加整页并返回 True；空页或整页 ID 均已缓存时
            返回 False，并停止后续取页。不对部分重叠的结果去重。
        """
        if not new_ids or set(new_ids).issubset(self.results):
            self.can_fetch_more = False
            return False
        self.results.extend(new_ids)
        self.api_page += 1
        self.can_fetch_more = len(new_ids) >= self.API_PAGE_SIZE
        return True

    def advance_page(self, result_count: int) -> None:
        """发送成功后按本次取出的 ID 数量推进，包含详情获取失败的条目。"""
        self.display_idx += result_count
