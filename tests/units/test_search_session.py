"""搜索分页的完整流程与终止边界。"""

import pytest

from nonebot_plugin_jmdownloader.core.search_session import SearchSession


@pytest.mark.parametrize(
    ("total", "page_size"),
    [(0, 20), (5, 20), (40, 20), (75, 20), (80, 20), (100, 30), (160, 100)],
)
def test_pagination_displays_all_results(total: int, page_size: int):
    expected = [str(i) for i in range(total)]
    session = SearchSession(query="test", results=expected[:80], page_size=page_size)

    displayed = session.get_current_page()
    session.advance_page(len(displayed))
    while session.has_remaining_results():
        if session.needs_fetch_more():
            offset = session.api_page * 80
            session.append_results(expected[offset : offset + 80])
        current = session.get_current_page()
        if not current:
            assert not session.has_remaining_results()
            break
        displayed.extend(current)
        session.advance_page(len(current))

    assert displayed == expected
    assert session.display_idx == total
    assert not session.can_fetch_more


@pytest.mark.parametrize(
    ("new_ids", "appended"),
    [([], False), (["0", "79"], False), (["new", "79"], True)],
)
def test_append_stops_on_empty_or_repeated_page(new_ids: list[str], appended: bool):
    original = [str(i) for i in range(80)]
    session = SearchSession(query="test", results=original.copy(), display_idx=60)

    assert session.append_results(new_ids) is appended
    assert session.results == original + (new_ids if appended else [])
    assert session.api_page == (2 if appended else 1)
    assert not session.can_fetch_more
    assert session.has_remaining_results()
    assert not session.needs_fetch_more()
