"""搜索会话管理模块"""

from __future__ import annotations

from cachetools import TTLCache

from ..core.search_session import SearchSession


class SessionCache:
    """用户搜索会话缓存

    基于 TTLCache，预设 maxsize 无限制，默认 TTL 30 分钟。
    超过 TTL 后，条目会在下次访问时自动过期清理。
    """

    def __init__(self, default_page_size: int = 20, ttl: float = 1800):
        self._cache: TTLCache[str, SearchSession] = TTLCache(
            maxsize=float("inf"), ttl=ttl
        )
        self.default_page_size = default_page_size

    def create(
        self, user_id: str | int, query: str, results: list[str]
    ) -> SearchSession:
        """创建并保存新的搜索会话"""
        session = SearchSession(
            query=query, results=results, page_size=self.default_page_size
        )
        self.set(user_id, session)
        return session

    def get(self, user_id: str | int) -> SearchSession | None:
        """获取用户的搜索会话"""
        return self._cache.get(str(user_id))

    def set(self, user_id: str | int, session: SearchSession) -> None:
        """保存用户的搜索会话"""
        self._cache[str(user_id)] = session

    def remove(self, user_id: str | int) -> None:
        """移除用户的搜索会话"""
        self._cache.pop(str(user_id), None)
