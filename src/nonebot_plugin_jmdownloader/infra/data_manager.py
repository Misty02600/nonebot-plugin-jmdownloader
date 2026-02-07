"""数据持久化管理器"""

from __future__ import annotations

from pathlib import Path

import msgspec
from boltons.fileutils import atomic_save

from ..core.data_models import GroupConfig, RestrictionConfig, UserData
from ..core.enums import GroupListMode


class DataManager:
    """插件数据管理器

    职责：
    - 管理数据文件路径
    - 序列化/反序列化
    - 群配置懒加载 + 缓存

    """

    def __init__(
        self,
        data_dir: Path,
        default_user_limit: int,
        group_mode: GroupListMode,
    ):
        """初始化数据管理器

        Args:
            data_dir: 数据目录路径
            default_user_limit: 默认用户下载次数
            group_mode: 群列表模式（WHITELIST / BLACKLIST）
        """
        self._data_dir: Path = data_dir
        self._groups_dir: Path = data_dir / "groups"
        self._restriction_path: Path = data_dir / "restriction.json"
        self._user_path: Path = data_dir / "user.json"
        self.default_user_limit: int = default_user_limit
        self.group_mode: GroupListMode = group_mode

        # 确保目录存在
        data_dir.mkdir(exist_ok=True)
        self._groups_dir.mkdir(exist_ok=True)

        # 群配置缓存
        self._groups_cache: dict[str, GroupConfig] = {}

        # 加载数据
        self.restriction: RestrictionConfig = self._load(
            self._restriction_path, RestrictionConfig
        )
        self.users: UserData = self._load(self._user_path, UserData)

        # 确保默认值
        if self.restriction.ensure_defaults():
            self.save_restriction()

    # region 序列化/反序列化

    def _load(self, path: Path, cls: type):
        """加载数据文件"""
        if path.exists():
            return msgspec.json.decode(path.read_bytes(), type=cls)
        return cls()

    def _save(self, path: Path, data) -> None:
        """原子保存数据文件"""
        with atomic_save(str(path), text_mode=False) as f:
            f.write(msgspec.json.encode(data))  # pyright: ignore[reportOptionalMemberAccess]

    # endregion

    # region 群配置（懒加载）

    def get_group(self, group_id: str | int) -> GroupConfig:
        """获取群配置（懒加载）"""
        group_id = str(group_id)
        if group_id not in self._groups_cache:
            path = self._groups_dir / f"{group_id}.json"
            self._groups_cache[group_id] = self._load(path, GroupConfig)
        return self._groups_cache[group_id]

    def save_group(self, group_id: str | int) -> None:
        """保存群配置"""
        group_id = str(group_id)
        config = self.get_group(group_id)
        path = self._groups_dir / f"{group_id}.json"
        self._save(path, config)

    # endregion

    # region 保存方法

    def save_restriction(self) -> None:
        """保存限制配置"""
        self._save(self._restriction_path, self.restriction)

    def save_users(self) -> None:
        """保存用户数据"""
        self._save(self._user_path, self.users)

    # endregion
