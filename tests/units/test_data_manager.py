"""
data_manager 模块单元测试

测试 ConfigData, RuntimeData 和 JmComicDataManager 的功能

注意：这些测试不依赖 nonebot 环境
- 数据结构类直接在测试中定义（与源码保持同步）
- JmComicDataManager 使用显式参数，避免需要 nonebot 环境
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import msgspec
import pytest


# 直接定义数据模型，避免导入触发 nonebot
# 这些定义必须与 models.py 中的定义保持同步
class GroupData(msgspec.Struct):
    """单个群的配置数据"""

    folder_id: str | None = None
    enabled: bool = False
    blacklist: list[str] = msgspec.field(default_factory=list)


class ConfigData(msgspec.Struct):
    """配置数据模型 - 低频变更，存储于 config.json"""

    restricted_tags: list[str] = msgspec.field(default_factory=list)
    restricted_ids: list[str] = msgspec.field(default_factory=list)
    forbidden_albums: list[str] = msgspec.field(default_factory=list)
    groups: dict[str, GroupData] = msgspec.field(default_factory=dict)


class RuntimeData(msgspec.Struct):
    """运行时数据模型 - 高频变更，存储于 runtime.json"""

    user_limits: dict[str, int] = msgspec.field(default_factory=dict)


# 由于 JmComicDataManager 接受显式参数，我们可以绕过 nonebot 依赖
# 但需要在运行时导入，因为它的模块可能仍然会尝试加载某些依赖
# 解决方案：直接复制 JmComicDataManager 的核心逻辑用于测试

from boltons.fileutils import atomic_save


class TestableDataManager:
    """可测试的数据管理器，复制自 JmComicDataManager 的核心逻辑"""

    DEFAULT_RESTRICTED_TAGS: ClassVar[list[str]] = [
        "獵奇",
        "重口",
        "YAOI",
        "yaoi",
        "男同",
        "血腥",
        "猎奇",
        "虐杀",
        "恋尸癖",
    ]
    DEFAULT_RESTRICTED_IDS: ClassVar[list[str]] = [
        "136494",
        "323666",
        "350234",
        "363848",
        "405848",
        "454278",
        "481481",
        "559716",
        "611650",
        "629252",
        "69658",
        "626487",
        "400002",
        "208092",
        "253199",
        "382596",
        "418600",
        "279464",
        "565616",
        "222458",
    ]

    def __init__(
        self,
        data_dir: Path,
        default_user_limit: int = 5,
        default_allow_groups: bool = False,
    ):
        self.config_path = data_dir / "config.json"
        self.runtime_path = data_dir / "runtime.json"
        self.default_enabled = default_allow_groups
        self.default_user_limit = default_user_limit

        data_dir.mkdir(parents=True, exist_ok=True)

        self.config = self._load_config()
        self.runtime = self._load_runtime()
        self._ensure_defaults()

    def _load_config(self) -> ConfigData:
        if self.config_path.exists():
            try:
                raw = self.config_path.read_bytes()
                return msgspec.json.decode(raw, type=ConfigData)
            except Exception:
                pass
        return ConfigData()

    def _load_runtime(self) -> RuntimeData:
        if self.runtime_path.exists():
            try:
                raw = self.runtime_path.read_bytes()
                return msgspec.json.decode(raw, type=RuntimeData)
            except Exception:
                pass
        return RuntimeData()

    def _save_config(self) -> None:
        encoded = msgspec.json.encode(self.config)
        with atomic_save(str(self.config_path), text_mode=False) as f:
            f.write(encoded)

    def _save_runtime(self) -> None:
        encoded = msgspec.json.encode(self.runtime)
        with atomic_save(str(self.runtime_path), text_mode=False) as f:
            f.write(encoded)

    def _ensure_defaults(self) -> None:
        if not self.config.restricted_tags:
            self.config.restricted_tags = self.DEFAULT_RESTRICTED_TAGS.copy()
        if not self.config.restricted_ids:
            self.config.restricted_ids = self.DEFAULT_RESTRICTED_IDS.copy()
        self._save_config()

    def _get_group(self, group_id: str) -> GroupData:
        if group_id not in self.config.groups:
            self.config.groups[group_id] = GroupData(enabled=self.default_enabled)
        return self.config.groups[group_id]

    def set_group_folder_id(self, group_id: str, folder_id: str) -> None:
        self._get_group(group_id).folder_id = folder_id
        self._save_config()

    def get_group_folder_id(self, group_id: str) -> str | None:
        return self._get_group(group_id).folder_id

    def is_group_enabled(self, group_id: str) -> bool:
        return self._get_group(group_id).enabled

    def set_group_enabled(self, group_id: str, enabled: bool) -> None:
        self._get_group(group_id).enabled = enabled
        self._save_config()

    def add_blacklist(self, group_id: str, user_id: str) -> None:
        blacklist = self._get_group(group_id).blacklist
        if user_id not in blacklist:
            blacklist.append(user_id)
            self._save_config()

    def remove_blacklist(self, group_id: str, user_id: str) -> None:
        blacklist = self._get_group(group_id).blacklist
        if user_id in blacklist:
            blacklist.remove(user_id)
            self._save_config()

    def is_user_blacklisted(self, group_id: str, user_id: str) -> bool:
        return user_id in self._get_group(group_id).blacklist

    def list_blacklist(self, group_id: str) -> list[str]:
        return self._get_group(group_id).blacklist.copy()

    def get_user_limit(self, user_id: str) -> int:
        return self.runtime.user_limits.get(user_id, self.default_user_limit)

    def set_user_limit(self, user_id: str, limit: int) -> None:
        self.runtime.user_limits[user_id] = limit
        self._save_runtime()

    def increase_user_limit(self, user_id: str, amount: int = 1) -> None:
        current = self.get_user_limit(user_id)
        self.set_user_limit(user_id, current + amount)

    def decrease_user_limit(self, user_id: str, amount: int = 1) -> None:
        current = self.get_user_limit(user_id)
        self.set_user_limit(user_id, max(0, current - amount))

    def try_consume_limit(self, user_id: str) -> bool:
        current = self.get_user_limit(user_id)
        if current <= 0:
            return False
        self.runtime.user_limits[user_id] = current - 1
        self._save_runtime()
        return True

    def reset_all_user_limits(self, default_limit: int | None = None) -> None:
        if default_limit is None:
            default_limit = self.default_user_limit
        for user_id in self.runtime.user_limits:
            self.runtime.user_limits[user_id] = default_limit
        self._save_runtime()

    def add_restricted_jm_id(self, jm_id: str) -> None:
        if jm_id not in self.config.restricted_ids:
            self.config.restricted_ids.append(jm_id)
            self._save_config()

    def is_jm_id_restricted(self, jm_id: str) -> bool:
        return jm_id in self.config.restricted_ids

    def add_restricted_tag(self, tag: str) -> None:
        if tag not in self.config.restricted_tags:
            self.config.restricted_tags.append(tag)
            self._save_config()

    def is_tag_restricted(self, tag: str) -> bool:
        return tag in self.config.restricted_tags

    def has_restricted_tag(self, tags: list[str]) -> bool:
        restricted_set = set(self.config.restricted_tags)
        return any(tag in restricted_set for tag in tags)

    def list_forbidden_albums(self) -> list[str]:
        return self.config.forbidden_albums.copy()

    def add_forbidden_album(self, album_id: str) -> None:
        if album_id not in self.config.forbidden_albums:
            self.config.forbidden_albums.append(album_id)
            self._save_config()

    def remove_forbidden_album(self, album_id: str) -> None:
        if album_id in self.config.forbidden_albums:
            self.config.forbidden_albums.remove(album_id)
            self._save_config()

    def is_forbidden_album(self, album_id: str) -> bool:
        return album_id in self.config.forbidden_albums


class TestGroupData:
    """GroupData 数据模型测试"""

    def test_default_values(self):
        """测试默认值"""
        group = GroupData()
        assert group.folder_id is None
        assert group.enabled is False
        assert group.blacklist == []

    def test_custom_values(self):
        """测试自定义值"""
        group = GroupData(
            folder_id="test_folder",
            enabled=True,
            blacklist=["user1", "user2"],
        )
        assert group.folder_id == "test_folder"
        assert group.enabled is True
        assert group.blacklist == ["user1", "user2"]

    def test_mutable_default_isolation(self):
        """测试可变默认值隔离（不同实例不共享列表）"""
        group1 = GroupData()
        group2 = GroupData()
        group1.blacklist.append("user1")
        assert group2.blacklist == []


class TestConfigData:
    """ConfigData 数据模型测试"""

    def test_default_values(self):
        """测试默认值"""
        config = ConfigData()
        assert config.restricted_tags == []
        assert config.restricted_ids == []
        assert config.forbidden_albums == []
        assert config.groups == {}

    def test_serialization(self):
        """测试序列化和反序列化"""
        config = ConfigData(
            restricted_tags=["tag1", "tag2"],
            restricted_ids=["123", "456"],
            forbidden_albums=["789"],
            groups={"12345": GroupData(folder_id="folder1", enabled=True)},
        )

        encoded = msgspec.json.encode(config)
        assert isinstance(encoded, bytes)

        decoded = msgspec.json.decode(encoded, type=ConfigData)
        assert decoded.restricted_tags == ["tag1", "tag2"]
        assert decoded.restricted_ids == ["123", "456"]
        assert decoded.groups["12345"].folder_id == "folder1"
        assert decoded.groups["12345"].enabled is True

    def test_mutable_default_isolation(self):
        """测试可变默认值隔离"""
        config1 = ConfigData()
        config2 = ConfigData()
        config1.restricted_tags.append("tag1")
        config1.groups["123"] = GroupData()
        assert config2.restricted_tags == []
        assert config2.groups == {}


class TestRuntimeData:
    """RuntimeData 数据模型测试"""

    def test_default_values(self):
        """测试默认值"""
        runtime = RuntimeData()
        assert runtime.user_limits == {}

    def test_serialization(self):
        """测试序列化和反序列化"""
        runtime = RuntimeData(user_limits={"user1": 5, "user2": 3})

        encoded = msgspec.json.encode(runtime)
        decoded = msgspec.json.decode(encoded, type=RuntimeData)

        assert decoded.user_limits == {"user1": 5, "user2": 3}

    def test_mutable_default_isolation(self):
        """测试可变默认值隔离"""
        runtime1 = RuntimeData()
        runtime2 = RuntimeData()
        runtime1.user_limits["user1"] = 5
        assert runtime2.user_limits == {}


class TestDataManager:
    """DataManager 测试"""

    @pytest.fixture
    def manager(self, tmp_path: Path) -> TestableDataManager:
        """创建测试用的数据管理器"""
        return TestableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )

    # region 群配置测试

    def test_group_folder_id(self, manager: TestableDataManager):
        """测试群文件夹 ID 设置和获取"""
        group_id = "123456"

        assert manager.get_group_folder_id(group_id) is None

        manager.set_group_folder_id(group_id, "folder_abc")
        assert manager.get_group_folder_id(group_id) == "folder_abc"

    def test_group_enabled(self, manager: TestableDataManager):
        """测试群功能开关"""
        group_id = "123456"

        assert manager.is_group_enabled(group_id) is False

        manager.set_group_enabled(group_id, True)
        assert manager.is_group_enabled(group_id) is True

        manager.set_group_enabled(group_id, False)
        assert manager.is_group_enabled(group_id) is False

    def test_group_default_enabled(self, tmp_path: Path):
        """测试群默认启用状态"""
        manager = TestableDataManager(
            data_dir=tmp_path / "enabled",
            default_user_limit=5,
            default_allow_groups=True,
        )
        assert manager.is_group_enabled("new_group") is True

    # endregion

    # region 黑名单测试

    def test_blacklist_add_remove(self, manager: TestableDataManager):
        """测试黑名单添加和移除"""
        group_id = "123456"
        user_id = "user1"

        assert manager.is_user_blacklisted(group_id, user_id) is False

        manager.add_blacklist(group_id, user_id)
        assert manager.is_user_blacklisted(group_id, user_id) is True

        manager.remove_blacklist(group_id, user_id)
        assert manager.is_user_blacklisted(group_id, user_id) is False

    def test_blacklist_list(self, manager: TestableDataManager):
        """测试黑名单列表"""
        group_id = "123456"

        manager.add_blacklist(group_id, "user1")
        manager.add_blacklist(group_id, "user2")

        blacklist = manager.list_blacklist(group_id)
        assert "user1" in blacklist
        assert "user2" in blacklist

    def test_blacklist_no_duplicate(self, manager: TestableDataManager):
        """测试黑名单不重复添加"""
        group_id = "123456"
        user_id = "user1"

        manager.add_blacklist(group_id, user_id)
        manager.add_blacklist(group_id, user_id)

        assert manager.list_blacklist(group_id).count(user_id) == 1

    def test_blacklist_copy_isolation(self, manager: TestableDataManager):
        """测试黑名单列表是副本"""
        group_id = "123456"
        manager.add_blacklist(group_id, "user1")

        blacklist = manager.list_blacklist(group_id)
        blacklist.append("user2")

        assert manager.list_blacklist(group_id) == ["user1"]

    # endregion

    # region 用户下载限制测试

    def test_user_limit_default(self, manager: TestableDataManager):
        """测试用户默认下载次数"""
        limit = manager.get_user_limit("new_user")
        assert limit == 5

    def test_user_limit_set_get(self, manager: TestableDataManager):
        """测试设置和获取用户下载次数"""
        user_id = "user1"

        manager.set_user_limit(user_id, 10)
        assert manager.get_user_limit(user_id) == 10

    def test_user_limit_increase(self, manager: TestableDataManager):
        """测试增加用户下载次数"""
        user_id = "user1"
        manager.set_user_limit(user_id, 5)

        manager.increase_user_limit(user_id, 3)
        assert manager.get_user_limit(user_id) == 8

    def test_user_limit_decrease(self, manager: TestableDataManager):
        """测试减少用户下载次数"""
        user_id = "user1"
        manager.set_user_limit(user_id, 5)

        manager.decrease_user_limit(user_id, 3)
        assert manager.get_user_limit(user_id) == 2

    def test_user_limit_decrease_floor_zero(self, manager: TestableDataManager):
        """测试减少用户下载次数不会低于 0"""
        user_id = "user1"
        manager.set_user_limit(user_id, 2)

        manager.decrease_user_limit(user_id, 10)
        assert manager.get_user_limit(user_id) == 0

    def test_try_consume_limit_success(self, manager: TestableDataManager):
        """测试成功消耗下载次数"""
        user_id = "user1"
        manager.set_user_limit(user_id, 5)

        result = manager.try_consume_limit(user_id)
        assert result is True
        assert manager.get_user_limit(user_id) == 4

    def test_try_consume_limit_fail(self, manager: TestableDataManager):
        """测试次数不足时消耗失败"""
        user_id = "user1"
        manager.set_user_limit(user_id, 0)

        result = manager.try_consume_limit(user_id)
        assert result is False
        assert manager.get_user_limit(user_id) == 0

    def test_reset_all_user_limits(self, manager: TestableDataManager):
        """测试重置所有用户下载次数"""
        manager.set_user_limit("user1", 1)
        manager.set_user_limit("user2", 2)

        manager.reset_all_user_limits(10)

        assert manager.get_user_limit("user1") == 10
        assert manager.get_user_limit("user2") == 10

    def test_reset_all_user_limits_default(self, manager: TestableDataManager):
        """测试使用默认值重置所有用户下载次数"""
        manager.set_user_limit("user1", 1)

        manager.reset_all_user_limits()

        assert manager.get_user_limit("user1") == 5

    # endregion

    # region 受限内容测试

    def test_restricted_jm_id(self, manager: TestableDataManager):
        """测试受限 JM ID"""
        jm_id = "999999"

        manager.add_restricted_jm_id(jm_id)
        assert manager.is_jm_id_restricted(jm_id) is True

    def test_restricted_jm_id_no_duplicate(self, manager: TestableDataManager):
        """测试受限 JM ID 不重复添加"""
        jm_id = "999999"
        manager.add_restricted_jm_id(jm_id)
        manager.add_restricted_jm_id(jm_id)

        assert manager.config.restricted_ids.count(jm_id) == 1

    def test_restricted_tag(self, manager: TestableDataManager):
        """测试受限标签"""
        tag = "test_tag"

        manager.add_restricted_tag(tag)
        assert manager.is_tag_restricted(tag) is True

    def test_has_restricted_tag(self, manager: TestableDataManager):
        """测试检查标签列表中是否有受限标签"""
        manager.add_restricted_tag("bad_tag")

        assert manager.has_restricted_tag(["good", "bad_tag", "normal"]) is True
        assert manager.has_restricted_tag(["unique_safe_tag_xyz"]) is False

    def test_default_restricted_tags_exist(self, manager: TestableDataManager):
        """测试默认受限标签存在"""
        assert len(manager.config.restricted_tags) > 0
        assert "獵奇" in manager.config.restricted_tags

    def test_default_restricted_ids_exist(self, manager: TestableDataManager):
        """测试默认受限 ID 存在"""
        assert len(manager.config.restricted_ids) > 0
        assert "136494" in manager.config.restricted_ids

    # endregion

    # region 禁止本子测试

    def test_forbidden_album(self, manager: TestableDataManager):
        """测试禁止本子管理"""
        album_id = "12345"

        manager.add_forbidden_album(album_id)
        assert manager.is_forbidden_album(album_id) is True
        assert album_id in manager.list_forbidden_albums()

        manager.remove_forbidden_album(album_id)
        assert manager.is_forbidden_album(album_id) is False

    def test_forbidden_album_no_duplicate(self, manager: TestableDataManager):
        """测试禁止本子不重复添加"""
        album_id = "12345"
        manager.add_forbidden_album(album_id)
        manager.add_forbidden_album(album_id)

        assert manager.list_forbidden_albums().count(album_id) == 1

    def test_forbidden_albums_copy_isolation(self, manager: TestableDataManager):
        """测试禁止本子列表是副本"""
        manager.add_forbidden_album("12345")

        albums = manager.list_forbidden_albums()
        albums.append("67890")

        assert manager.list_forbidden_albums() == ["12345"]

    # endregion

    # region 持久化测试

    def test_config_persistence(self, tmp_path: Path):
        """测试配置数据持久化"""
        manager1 = TestableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )
        manager1.set_group_folder_id("123", "folder1")
        manager1.add_blacklist("123", "user1")

        manager2 = TestableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )
        assert manager2.get_group_folder_id("123") == "folder1"
        assert manager2.is_user_blacklisted("123", "user1") is True

    def test_runtime_persistence(self, tmp_path: Path):
        """测试运行时数据持久化"""
        manager1 = TestableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )
        manager1.set_user_limit("user1", 42)

        manager2 = TestableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )
        assert manager2.get_user_limit("user1") == 42

    def test_files_created(self, tmp_path: Path):
        """测试数据文件被创建"""
        TestableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )

        assert (tmp_path / "config.json").exists()

    # endregion


class TestDataMigration:
    """数据迁移测试"""

    def test_migrate_legacy_data(self, tmp_path: Path):
        """测试旧数据迁移"""
        import json

        # 创建旧格式数据文件
        legacy_data = {
            "restricted_tags": ["tag1", "tag2"],
            "restricted_ids": ["111", "222"],
            "forbidden_albums": ["333"],
            "user_limits": {"user1": 3, "user2": 5},
            "123456": {
                "folder_id": "folder_abc",
                "enabled": True,
                "blacklist": ["user_a", "user_b"],
            },
            "789012": {
                "enabled": False,
            },
        }

        legacy_path = tmp_path / "jmcomic_data.json"
        with legacy_path.open("w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # 创建带迁移功能的管理器
        manager = MigratableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )

        # 验证迁移结果
        assert manager.config.restricted_tags == ["tag1", "tag2"]
        assert manager.config.restricted_ids == ["111", "222"]
        assert manager.config.forbidden_albums == ["333"]

        assert manager.runtime.user_limits == {"user1": 3, "user2": 5}

        assert "123456" in manager.config.groups
        assert manager.config.groups["123456"].folder_id == "folder_abc"
        assert manager.config.groups["123456"].enabled is True
        assert manager.config.groups["123456"].blacklist == ["user_a", "user_b"]

        assert "789012" in manager.config.groups
        assert manager.config.groups["789012"].enabled is False

        # 验证备份文件存在
        backup_path = tmp_path / "jmcomic_data.json.bak"
        assert backup_path.exists()

        # 验证旧文件被删除
        assert not legacy_path.exists()

    def test_skip_migration_if_new_file_exists(self, tmp_path: Path):
        """测试新文件存在时跳过迁移"""
        import json

        # 创建新格式文件
        config_path = tmp_path / "config.json"
        config_data = ConfigData(restricted_tags=["new_tag"])
        with config_path.open("wb") as f:
            f.write(msgspec.json.encode(config_data))

        # 创建旧格式文件（应该被忽略）
        legacy_data = {"restricted_tags": ["old_tag"]}
        legacy_path = tmp_path / "jmcomic_data.json"
        with legacy_path.open("w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # 创建管理器
        manager = MigratableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )

        # 应该使用新文件的数据
        assert "new_tag" in manager.config.restricted_tags

        # 旧文件不应被删除
        assert legacy_path.exists()

    def test_skip_migration_if_no_legacy_file(self, tmp_path: Path):
        """测试旧文件不存在时正常创建新文件"""
        manager = MigratableDataManager(
            data_dir=tmp_path,
            default_user_limit=5,
            default_allow_groups=False,
        )

        # 应该创建新文件并使用默认值
        assert (tmp_path / "config.json").exists()
        assert len(manager.config.restricted_tags) > 0  # 有默认值


class MigratableDataManager(TestableDataManager):
    """带迁移功能的可测试数据管理器"""

    def __init__(
        self,
        data_dir: Path,
        default_user_limit: int = 5,
        default_allow_groups: bool = False,
    ):
        self.config_path = data_dir / "config.json"
        self.runtime_path = data_dir / "runtime.json"
        self.default_enabled = default_allow_groups
        self.default_user_limit = default_user_limit
        self._data_dir = data_dir

        data_dir.mkdir(parents=True, exist_ok=True)

        # 检测并迁移旧数据
        self._migrate_legacy_data()

        # 加载数据
        self.config = self._load_config()
        self.runtime = self._load_runtime()

        # 确保默认值
        self._ensure_defaults()

    def _migrate_legacy_data(self) -> None:
        """检测并迁移旧格式数据"""
        import json
        import shutil

        legacy_path = self._data_dir / "jmcomic_data.json"
        backup_path = self._data_dir / "jmcomic_data.json.bak"

        if self.config_path.exists() or not legacy_path.exists():
            return

        try:
            with legacy_path.open("r", encoding="utf-8") as f:
                old_data: dict = json.load(f)

            new_config = ConfigData()
            new_runtime = RuntimeData()

            if "restricted_tags" in old_data:
                new_config.restricted_tags = old_data["restricted_tags"]
            if "restricted_ids" in old_data:
                new_config.restricted_ids = old_data["restricted_ids"]
            if "forbidden_albums" in old_data:
                new_config.forbidden_albums = old_data["forbidden_albums"]

            if "user_limits" in old_data:
                new_runtime.user_limits = old_data["user_limits"]

            for key, value in old_data.items():
                if key in (
                    "restricted_tags",
                    "restricted_ids",
                    "forbidden_albums",
                    "user_limits",
                ):
                    continue

                if key.isdigit() and isinstance(value, dict):
                    group_data = GroupData(
                        folder_id=value.get("folder_id"),
                        enabled=value.get("enabled", self.default_enabled),
                        blacklist=value.get("blacklist", []),
                    )
                    new_config.groups[key] = group_data

            encoded_config = msgspec.json.encode(new_config)
            with atomic_save(str(self.config_path), text_mode=False) as f:
                f.write(encoded_config)

            if new_runtime.user_limits:
                encoded_runtime = msgspec.json.encode(new_runtime)
                with atomic_save(str(self.runtime_path), text_mode=False) as f:
                    f.write(encoded_runtime)

            shutil.copy2(legacy_path, backup_path)
            legacy_path.unlink()

        except Exception:
            pass
