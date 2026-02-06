"""
SessionCache 单元测试

测试搜索会话缓存的功能。
"""

from __future__ import annotations

import time

from nonebot_plugin_jmdownloader.infra.search_session import SessionCache


class TestSessionCacheBasic:
    """SessionCache 基础功能测试"""

    def test_default_values(self):
        """测试默认值"""
        cache = SessionCache()
        assert cache.default_page_size == 20

    def test_custom_values(self):
        """测试自定义值"""
        cache = SessionCache(default_page_size=50, ttl=3600)
        assert cache.default_page_size == 50


class TestSessionCacheCreate:
    """SessionCache.create 方法测试"""

    def test_create_session(self):
        """测试创建会话"""
        cache = SessionCache(default_page_size=15)
        session = cache.create(
            user_id="user1",
            query="test query",
            results=["1", "2", "3"],
        )

        assert session.query == "test query"
        assert session.results == ["1", "2", "3"]
        assert session.page_size == 15
        assert session.display_idx == 0
        assert session.api_page == 1

    def test_create_session_auto_saves(self):
        """测试创建会话自动保存"""
        cache = SessionCache()
        session = cache.create(
            user_id="user1",
            query="test",
            results=["1", "2"],
        )

        retrieved = cache.get("user1")
        assert retrieved is session

    def test_create_session_int_user_id(self):
        """测试使用 int 类型 user_id"""
        cache = SessionCache()
        session = cache.create(
            user_id=12345,
            query="test",
            results=["1"],
        )

        assert cache.get(12345) is session
        assert cache.get("12345") is session


class TestSessionCacheGetSet:
    """SessionCache.get/set 方法测试"""

    def test_get_nonexistent(self):
        """测试获取不存在的会话"""
        cache = SessionCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = SessionCache()
        session = cache.create(
            user_id="user1",
            query="test",
            results=[],
        )

        # 修改 session 后重新设置
        session.display_idx = 100
        cache.set("user1", session)

        retrieved = cache.get("user1")
        assert retrieved is not None
        assert retrieved.display_idx == 100

    def test_set_overwrites(self):
        """测试 set 覆盖"""
        cache = SessionCache()
        cache.create("user1", "query1", ["1"])
        session2 = cache.create("user1", "query2", ["2"])

        retrieved = cache.get("user1")
        assert retrieved is session2
        assert retrieved is not None
        assert retrieved.query == "query2"


class TestSessionCacheRemove:
    """SessionCache.remove 方法测试"""

    def test_remove_existing(self):
        """测试移除存在的会话"""
        cache = SessionCache()
        cache.create("user1", "test", [])

        cache.remove("user1")
        assert cache.get("user1") is None

    def test_remove_nonexistent(self):
        """测试移除不存在的会话（不报错）"""
        cache = SessionCache()
        cache.remove("nonexistent")  # 不应该抛出异常

    def test_remove_int_user_id(self):
        """测试使用 int 类型 user_id 移除"""
        cache = SessionCache()
        cache.create(12345, "test", [])

        cache.remove(12345)
        assert cache.get(12345) is None


class TestSessionCacheTTL:
    """SessionCache TTL 功能测试"""

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        # 使用非常短的 TTL
        cache = SessionCache(ttl=0.1)  # 100ms
        cache.create("user1", "test", [])

        assert cache.get("user1") is not None

        # 等待过期
        time.sleep(0.2)

        assert cache.get("user1") is None

    def test_ttl_refresh(self):
        """测试 TTL 不被 get 刷新"""
        cache = SessionCache(ttl=0.2)
        cache.create("user1", "test", [])

        # 在过期前获取
        time.sleep(0.1)
        assert cache.get("user1") is not None

        # 继续等待
        time.sleep(0.15)

        # 应该过期了
        assert cache.get("user1") is None


class TestSessionCacheIsolation:
    """SessionCache 用户隔离测试"""

    def test_user_isolation(self):
        """测试不同用户的会话隔离"""
        cache = SessionCache()
        session1 = cache.create("user1", "query1", ["a", "b"])
        session2 = cache.create("user2", "query2", ["c", "d"])

        assert cache.get("user1") is session1
        assert cache.get("user2") is session2
        assert session1.query == "query1"
        assert session2.query == "query2"

    def test_remove_one_user(self):
        """测试移除一个用户不影响其他用户"""
        cache = SessionCache()
        cache.create("user1", "query1", [])
        cache.create("user2", "query2", [])

        cache.remove("user1")

        assert cache.get("user1") is None
        assert cache.get("user2") is not None
