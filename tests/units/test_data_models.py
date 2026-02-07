"""
core/data_models 单元测试

测试核心数据模型的功能。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import msgspec

# 动态加载 core 子模块，避免触发父包的 __init__.py
_src_dir = Path(__file__).parent.parent.parent / "src" / "nonebot_plugin_jmdownloader"


def _load_module(name: str, file_path: Path):
    """动态加载模块"""
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore
    return module


_enums = _load_module("core_enums", _src_dir / "core" / "enums.py")
_data_models = _load_module("core_data_models", _src_dir / "core" / "data_models.py")

GroupConfig = _data_models.GroupConfig
RestrictionConfig = _data_models.RestrictionConfig
UserData = _data_models.UserData
GroupListMode = _enums.GroupListMode


class TestGroupConfig:
    """GroupConfig 测试"""

    def test_default_values(self):
        """测试默认值"""
        group = GroupConfig()
        assert group.folder_id is None
        assert group.enabled is msgspec.UNSET
        assert group.blacklist == set()

    def test_custom_values(self):
        """测试自定义值"""
        group = GroupConfig(
            folder_id="folder123",
            enabled=True,
            blacklist={"user1", "user2"},
        )
        assert group.folder_id == "folder123"
        assert group.enabled is True
        assert group.blacklist == {"user1", "user2"}

    def test_is_enabled_whitelist_mode(self):
        """测试 is_enabled 白名单模式：True 和 UNSET 可以，False 不能"""
        group_unset = GroupConfig()
        group_enabled = GroupConfig(enabled=True)
        group_disabled = GroupConfig(enabled=False)

        # 白名单模式：默认允许
        assert group_unset.is_enabled(GroupListMode.WHITELIST) is True
        assert group_enabled.is_enabled(GroupListMode.WHITELIST) is True
        assert group_disabled.is_enabled(GroupListMode.WHITELIST) is False

    def test_is_enabled_blacklist_mode(self):
        """测试 is_enabled 黑名单模式：只有 True 可以"""
        group_unset = GroupConfig()
        group_enabled = GroupConfig(enabled=True)
        group_disabled = GroupConfig(enabled=False)

        # 黑名单模式：默认禁止
        assert group_unset.is_enabled(GroupListMode.BLACKLIST) is False
        assert group_enabled.is_enabled(GroupListMode.BLACKLIST) is True
        assert group_disabled.is_enabled(GroupListMode.BLACKLIST) is False

    def test_serialization(self):
        """测试序列化和反序列化"""
        group = GroupConfig(
            folder_id="folder123",
            enabled=True,
            blacklist={"user1", "user2"},
        )
        encoded = msgspec.json.encode(group)
        decoded = msgspec.json.decode(encoded, type=GroupConfig)

        assert decoded.folder_id == "folder123"
        assert decoded.enabled is True
        assert decoded.blacklist == {"user1", "user2"}

    def test_omit_defaults_serialization(self):
        """测试默认值省略序列化"""
        group = GroupConfig()
        encoded = msgspec.json.encode(group)
        # 默认值应该被省略
        assert encoded == b"{}"

    def test_mutable_default_isolation(self):
        """测试可变默认值隔离"""
        group1 = GroupConfig()
        group2 = GroupConfig()
        group1.blacklist.add("user1")
        assert "user1" not in group2.blacklist


class TestRestrictionConfig:
    """RestrictionConfig 测试"""

    def test_default_values(self):
        """测试默认值"""
        config = RestrictionConfig()
        assert config.restricted_tags == set()
        assert config.restricted_ids == set()

    def test_ensure_defaults_empty(self):
        """测试 ensure_defaults 填充默认值"""
        config = RestrictionConfig()
        modified = config.ensure_defaults()

        assert modified is True
        assert len(config.restricted_tags) > 0
        assert len(config.restricted_ids) > 0
        assert "獵奇" in config.restricted_tags
        assert "136494" in config.restricted_ids

    def test_ensure_defaults_already_set(self):
        """测试 ensure_defaults 不覆盖已有值"""
        config = RestrictionConfig(
            restricted_tags={"custom_tag"},
            restricted_ids={"999999"},
        )
        modified = config.ensure_defaults()

        assert modified is False
        assert config.restricted_tags == {"custom_tag"}
        assert config.restricted_ids == {"999999"}

    def test_is_photo_restricted_by_id(self):
        """测试通过 ID 检查受限"""
        config = RestrictionConfig(restricted_ids={"12345", "67890"})

        assert config.is_photo_restricted("12345") is True
        assert config.is_photo_restricted("67890") is True
        assert config.is_photo_restricted("11111") is False

    def test_is_photo_restricted_by_tag(self):
        """测试通过标签检查受限"""
        config = RestrictionConfig(restricted_tags={"bad_tag", "worse_tag"})

        assert config.is_photo_restricted("12345", ["good", "bad_tag"]) is True
        assert config.is_photo_restricted("12345", ["good", "fine"]) is False
        assert config.is_photo_restricted("12345", None) is False
        assert config.is_photo_restricted("12345", []) is False

    def test_is_photo_restricted_both(self):
        """测试 ID 和标签都检查"""
        config = RestrictionConfig(
            restricted_ids={"12345"},
            restricted_tags={"bad_tag"},
        )

        # ID 受限
        assert config.is_photo_restricted("12345", ["good"]) is True
        # 标签受限
        assert config.is_photo_restricted("99999", ["bad_tag"]) is True
        # 两者都不受限
        assert config.is_photo_restricted("99999", ["good"]) is False

    def test_find_restricted_tag(self):
        """测试查找受限标签"""
        config = RestrictionConfig(restricted_tags={"bad1", "bad2"})

        assert config.find_restricted_tag(["good", "bad1", "bad2"]) == "bad1"
        assert config.find_restricted_tag(["good", "fine"]) is None
        assert config.find_restricted_tag(None) is None
        assert config.find_restricted_tag([]) is None

    def test_serialization(self):
        """测试序列化和反序列化"""
        config = RestrictionConfig(
            restricted_tags={"tag1", "tag2"},
            restricted_ids={"111", "222"},
        )
        encoded = msgspec.json.encode(config)
        decoded = msgspec.json.decode(encoded, type=RestrictionConfig)

        assert decoded.restricted_tags == {"tag1", "tag2"}
        assert decoded.restricted_ids == {"111", "222"}

    def test_default_restricted_tags(self):
        """测试默认受限标签常量"""
        assert "獵奇" in RestrictionConfig.DEFAULT_RESTRICTED_TAGS
        assert "重口" in RestrictionConfig.DEFAULT_RESTRICTED_TAGS
        assert "YAOI" in RestrictionConfig.DEFAULT_RESTRICTED_TAGS

    def test_default_restricted_ids(self):
        """测试默认受限 ID 常量"""
        assert "136494" in RestrictionConfig.DEFAULT_RESTRICTED_IDS
        assert "323666" in RestrictionConfig.DEFAULT_RESTRICTED_IDS


class TestUserData:
    """UserData 测试"""

    def test_default_values(self):
        """测试默认值"""
        data = UserData()
        assert data.user_limits == {}

    def test_get_limit_default(self):
        """测试获取默认限制"""
        data = UserData()
        assert data.get_limit("user1") == 5
        assert data.get_limit("user1", default=10) == 10

    def test_get_limit_existing(self):
        """测试获取已存在的限制"""
        data = UserData(user_limits={"user1": 3})
        assert data.get_limit("user1") == 3
        assert data.get_limit("user1", default=10) == 3

    def test_get_limit_int_user_id(self):
        """测试使用 int 类型 user_id"""
        data = UserData(user_limits={"12345": 7})
        assert data.get_limit(12345) == 7

    def test_has_limit(self):
        """测试检查是否有剩余次数"""
        data = UserData(user_limits={"user1": 3, "user2": 0})

        assert data.has_limit("user1") is True
        assert data.has_limit("user2") is False
        assert data.has_limit("user3") is True  # 默认 5

    def test_decrease_limit(self):
        """测试减少限制"""
        data = UserData(user_limits={"user1": 5})

        remaining = data.decrease_limit("user1", 2)
        assert remaining == 3
        assert data.get_limit("user1") == 3

    def test_decrease_limit_floor_zero(self):
        """测试减少限制不低于 0"""
        data = UserData(user_limits={"user1": 2})

        remaining = data.decrease_limit("user1", 10)
        assert remaining == 0
        assert data.get_limit("user1") == 0

    def test_decrease_limit_new_user(self):
        """测试减少新用户的限制（使用默认值）"""
        data = UserData()

        remaining = data.decrease_limit("new_user", 1, default=5)
        assert remaining == 4
        assert data.get_limit("new_user") == 4

    def test_decrease_limit_int_user_id(self):
        """测试使用 int 类型 user_id"""
        data = UserData(user_limits={"12345": 5})

        remaining = data.decrease_limit(12345, 1)
        assert remaining == 4

    def test_reset_all(self):
        """测试重置所有用户"""
        data = UserData(user_limits={"user1": 1, "user2": 2, "user3": 3})

        count = data.reset_all(10)
        assert count == 3
        assert data.get_limit("user1") == 10
        assert data.get_limit("user2") == 10
        assert data.get_limit("user3") == 10

    def test_reset_all_empty(self):
        """测试重置空数据"""
        data = UserData()
        count = data.reset_all(10)
        assert count == 0

    def test_serialization(self):
        """测试序列化和反序列化"""
        data = UserData(user_limits={"user1": 3, "user2": 7})
        encoded = msgspec.json.encode(data)
        decoded = msgspec.json.decode(encoded, type=UserData)

        assert decoded.user_limits == {"user1": 3, "user2": 7}

    def test_mutable_default_isolation(self):
        """测试可变默认值隔离"""
        data1 = UserData()
        data2 = UserData()
        data1.user_limits["user1"] = 5
        assert "user1" not in data2.user_limits
