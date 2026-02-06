"""
SearchSession 单元测试

测试搜索会话的翻页逻辑、状态管理等功能。
"""

from __future__ import annotations

from nonebot_plugin_jmdownloader.core.search_session import SearchSession


class TestSearchSessionBasic:
    """SearchSession 基础功能测试"""

    def test_default_values(self):
        """测试默认值"""
        session = SearchSession(query="test")
        assert session.query == "test"
        assert session.results == []
        assert session.display_idx == 0
        assert session.api_page == 1
        assert session.page_size == 20

    def test_custom_values(self):
        """测试自定义值"""
        results = ["1", "2", "3"]
        session = SearchSession(
            query="custom",
            results=results,
            display_idx=10,
            api_page=2,
            page_size=5,
        )
        assert session.query == "custom"
        assert session.results == results
        assert session.display_idx == 10
        assert session.api_page == 2
        assert session.page_size == 5


class TestGetCurrentPage:
    """get_current_page 方法测试"""

    def test_empty_results(self):
        """测试空结果"""
        session = SearchSession(query="test")
        assert session.get_current_page() == []

    def test_first_page(self):
        """测试获取第一页"""
        results = [str(i) for i in range(50)]
        session = SearchSession(query="test", results=results, page_size=10)
        current = session.get_current_page()
        assert current == [str(i) for i in range(10)]

    def test_middle_page(self):
        """测试获取中间页"""
        results = [str(i) for i in range(50)]
        session = SearchSession(
            query="test", results=results, display_idx=20, page_size=10
        )
        current = session.get_current_page()
        assert current == [str(i) for i in range(20, 30)]

    def test_last_partial_page(self):
        """测试获取最后一页（不完整）"""
        results = [str(i) for i in range(25)]
        session = SearchSession(
            query="test", results=results, display_idx=20, page_size=10
        )
        current = session.get_current_page()
        assert current == [str(i) for i in range(20, 25)]

    def test_beyond_results(self):
        """测试超出结果范围"""
        results = [str(i) for i in range(10)]
        session = SearchSession(
            query="test", results=results, display_idx=100, page_size=10
        )
        assert session.get_current_page() == []


class TestHasNextPage:
    """has_next_page 方法测试"""

    def test_empty_results(self):
        """测试空结果没有下一页"""
        session = SearchSession(query="test")
        assert session.has_next_page() is False

    def test_has_more_cached_results(self):
        """测试有更多缓存结果"""
        results = [str(i) for i in range(30)]
        session = SearchSession(query="test", results=results, page_size=10)
        assert session.has_next_page() is True

    def test_no_more_cached_results_partial(self):
        """测试没有更多缓存结果（不完整的 API 页）"""
        # 25 个结果，不是 80 的倍数，说明 API 已返回全部
        results = [str(i) for i in range(25)]
        session = SearchSession(
            query="test", results=results, display_idx=20, page_size=10
        )
        assert session.has_next_page() is False

    def test_may_have_more_api_pages(self):
        """测试可能有更多 API 页"""
        # 80 个结果（恰好一个 API 页），可能还有下一页
        results = [str(i) for i in range(80)]
        session = SearchSession(
            query="test", results=results, display_idx=70, page_size=10
        )
        assert session.has_next_page() is True

    def test_exactly_at_page_boundary(self):
        """测试恰好在页边界"""
        results = [str(i) for i in range(20)]
        session = SearchSession(
            query="test", results=results, display_idx=10, page_size=10
        )
        # 还有 10 个结果可显示
        assert session.has_next_page() is False  # 20 不是 80 的倍数

    def test_multiple_api_pages(self):
        """测试多个 API 页"""
        results = [str(i) for i in range(160)]  # 2 个 API 页
        session = SearchSession(
            query="test", results=results, display_idx=150, page_size=10
        )
        assert session.has_next_page() is True  # 160 是 80 的倍数


class TestNeedsFetchMore:
    """needs_fetch_more 方法测试"""

    def test_empty_results(self):
        """测试空结果不需要获取更多"""
        session = SearchSession(query="test")
        assert session.needs_fetch_more() is False

    def test_enough_cached_results(self):
        """测试有足够缓存结果"""
        results = [str(i) for i in range(100)]
        session = SearchSession(query="test", results=results, page_size=10)
        # display_idx=0, 需要 0+10*2=20 个结果，有 100 个，足够
        assert session.needs_fetch_more() is False

    def test_needs_more_and_may_have_more(self):
        """测试需要更多且可能有更多 API 页"""
        results = [str(i) for i in range(80)]  # 恰好 1 个 API 页
        session = SearchSession(
            query="test", results=results, display_idx=70, page_size=10
        )
        # 需要 70+10*2=90，只有 80，且 80 是 80 的倍数
        assert session.needs_fetch_more() is True

    def test_needs_more_but_no_more_api_pages(self):
        """测试需要更多但没有更多 API 页"""
        results = [str(i) for i in range(75)]  # 不是 80 的倍数
        session = SearchSession(
            query="test", results=results, display_idx=70, page_size=10
        )
        # 需要 90，只有 75，但 75 不是 80 的倍数
        assert session.needs_fetch_more() is False


class TestAppendResults:
    """append_results 方法测试"""

    def test_append_new_results(self):
        """测试追加新结果"""
        session = SearchSession(query="test", results=["1", "2", "3"])
        result = session.append_results(["4", "5", "6"])
        assert result is True
        assert session.results == ["1", "2", "3", "4", "5", "6"]
        assert session.api_page == 2

    def test_append_empty_list(self):
        """测试追加空列表"""
        session = SearchSession(query="test", results=["1", "2", "3"])
        result = session.append_results([])
        assert result is False
        assert session.results == ["1", "2", "3"]
        assert session.api_page == 1

    def test_append_duplicate_last_id(self):
        """测试追加重复的最后一个 ID（API 返回重复数据）"""
        session = SearchSession(query="test", results=["1", "2", "3"])
        result = session.append_results(["4", "5", "3"])  # 最后一个和已有的最后一个相同
        assert result is False
        assert session.results == ["1", "2", "3"]
        assert session.api_page == 1

    def test_append_to_empty_session(self):
        """测试追加到空会话"""
        session = SearchSession(query="test")
        result = session.append_results(["1", "2", "3"])
        assert result is True
        assert session.results == ["1", "2", "3"]
        assert session.api_page == 2


class TestAdvancePage:
    """advance_page 方法测试"""

    def test_advance_from_start(self):
        """测试从起始位置前进"""
        session = SearchSession(query="test", page_size=10)
        session.advance_page()
        assert session.display_idx == 10

    def test_advance_multiple_times(self):
        """测试多次前进"""
        session = SearchSession(query="test", page_size=10)
        session.advance_page()
        session.advance_page()
        session.advance_page()
        assert session.display_idx == 30


class TestIsLastPage:
    """is_last_page 方法测试"""

    def test_empty_is_last(self):
        """测试空结果是最后一页"""
        session = SearchSession(query="test")
        assert session.is_last_page() is True

    def test_not_last_page(self):
        """测试不是最后一页"""
        results = [str(i) for i in range(30)]
        session = SearchSession(query="test", results=results, page_size=10)
        assert session.is_last_page() is False

    def test_is_last_page(self):
        """测试是最后一页"""
        results = [str(i) for i in range(25)]  # 不是 80 的倍数
        session = SearchSession(
            query="test", results=results, display_idx=20, page_size=10
        )
        assert session.is_last_page() is True


class TestPaginationWorkflow:
    """完整的翻页工作流测试"""

    def test_full_pagination_workflow(self):
        """测试完整的翻页流程"""
        # 模拟搜索返回 75 个结果（不完整的 API 页，表示没有更多）
        results = [str(i) for i in range(75)]
        session = SearchSession(query="test", results=results, page_size=20)

        # 第一页
        page1 = session.get_current_page()
        assert len(page1) == 20
        assert page1[0] == "0"
        assert session.has_next_page() is True

        session.advance_page()

        # 第二页
        page2 = session.get_current_page()
        assert len(page2) == 20
        assert page2[0] == "20"
        assert session.has_next_page() is True

        session.advance_page()

        # 第三页
        page3 = session.get_current_page()
        assert len(page3) == 20
        assert page3[0] == "40"
        assert session.has_next_page() is True

        session.advance_page()

        # 第四页（最后一页，只有 15 条）
        page4 = session.get_current_page()
        assert len(page4) == 15
        assert page4[0] == "60"
        # 75 不是 80 的倍数，所以没有更多 API 页
        assert session.has_next_page() is False
        assert session.is_last_page() is True

    def test_pagination_with_api_fetch(self):
        """测试带 API 获取的翻页流程"""
        # 初始 80 个结果
        initial_results = [str(i) for i in range(80)]
        session = SearchSession(query="test", results=initial_results, page_size=20)

        # 浏览到需要获取更多的位置
        session.advance_page()  # 20
        session.advance_page()  # 40
        session.advance_page()  # 60

        # 检查是否需要获取更多
        assert session.needs_fetch_more() is True

        # 模拟获取第二页 API 结果
        second_page_results = [str(i) for i in range(80, 160)]
        success = session.append_results(second_page_results)
        assert success is True
        assert len(session.results) == 160
        assert session.api_page == 2

        # 继续翻页
        session.advance_page()  # 80
        page = session.get_current_page()
        assert len(page) == 20
        assert page[0] == "80"
