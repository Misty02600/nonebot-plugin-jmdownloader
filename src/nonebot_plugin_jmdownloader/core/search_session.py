"""搜索会话核心实体"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchSession:
    """用户搜索会话

    封装搜索状态和翻页逻辑。

    Attributes:
        query: 搜索关键词
        results: 已获取的所有结果 ID
        display_idx: 当前展示起始索引
        api_page: 当前 API 页码
        page_size: 每页显示数量
    """

    query: str
    results: list[str] = field(default_factory=list)
    display_idx: int = 0
    api_page: int = 1
    page_size: int = 20

    # JM API 每页返回的数量（固定值）
    API_PAGE_SIZE: int = 80

    def get_current_page(self) -> list[str]:
        """获取当前页的结果 ID 列表"""
        end_idx = self.display_idx + self.page_size
        return self.results[self.display_idx : end_idx]

    def has_next_page(self) -> bool:
        """检查是否还有下一页（用户视角）"""
        return self._has_more_results() or self._may_have_next_api_page()

    def _has_more_results(self) -> bool:
        """检查是否还有更多缓存结果可显示"""
        return self.display_idx + self.page_size < len(self.results)

    def _may_have_next_api_page(self) -> bool:
        """检查是否可能还有下一个 API 页"""
        return len(self.results) > 0 and len(self.results) % self.API_PAGE_SIZE == 0

    def needs_fetch_more(self) -> bool:
        """检查是否需要获取更多 API 数据"""
        next_end = self.display_idx + self.page_size * 2
        return next_end > len(self.results) and self._may_have_next_api_page()

    def append_results(self, new_ids: list[str]) -> bool:
        """追加新的搜索结果

        Args:
            new_ids: 新的结果 ID 列表

        Returns:
            True 如果成功追加了新结果
        """
        if not new_ids or (self.results and new_ids[-1] == self.results[-1]):
            return False
        self.results.extend(new_ids)
        self.api_page += 1
        return True

    def advance_page(self) -> None:
        """前进到下一页"""
        self.display_idx += self.page_size

    def is_last_page(self) -> bool:
        """检查当前是否是最后一页"""
        return not self.has_next_page()
