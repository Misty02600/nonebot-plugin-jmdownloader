"""数据迁移模块

处理旧版本数据格式的迁移。
插件启动时调用 run_migration() 检测并执行迁移。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import msgspec
from boltons.fileutils import atomic_save

if TYPE_CHECKING:
    from loguru import Logger


def run_migration() -> None:
    """插件启动时运行迁移检测

    自动获取数据目录和 logger，检测并迁移旧数据。
    """
    from nonebot import logger, require

    require("nonebot_plugin_localstore")
    from nonebot_plugin_localstore import get_plugin_data_dir

    data_dir = get_plugin_data_dir()
    groups_dir = data_dir / "groups"
    restriction_path = data_dir / "restriction.json"
    user_path = data_dir / "user.json"

    # 确保目录存在
    data_dir.mkdir(parents=True, exist_ok=True)
    groups_dir.mkdir(parents=True, exist_ok=True)

    migrate_legacy_data(data_dir, groups_dir, restriction_path, user_path, logger)


def migrate_legacy_data(
    data_dir: Path,
    groups_dir: Path,
    restriction_path: Path,
    user_path: Path,
    logger: Logger,
) -> None:
    """检测并迁移旧格式数据

    支持的旧格式：
    - jmcomic_data.json（最旧）
    - config.json / group.json（过渡版本）
    """
    # 导入数据模型（避免循环导入）
    from .core.data_models import GroupConfig, RestrictionConfig, UserData

    # 检查是否已迁移
    if restriction_path.exists() or any(groups_dir.glob("*.json")):
        return

    # 尝试迁移各种旧格式
    legacy_path = data_dir / "jmcomic_data.json"
    if legacy_path.exists():
        _migrate_from_legacy_format(
            legacy_path,
            groups_dir,
            restriction_path,
            user_path,
            logger,
            RestrictionConfig,
            GroupConfig,
            UserData,
        )
        return

    old_group_path = data_dir / "group.json"
    if old_group_path.exists():
        _migrate_from_group_json(
            old_group_path,
            groups_dir,
            restriction_path,
            logger,
            RestrictionConfig,
            GroupConfig,
        )
        return

    old_config_path = data_dir / "config.json"
    if old_config_path.exists():
        _migrate_from_group_json(
            old_config_path,
            groups_dir,
            restriction_path,
            logger,
            RestrictionConfig,
            GroupConfig,
        )


def _migrate_from_legacy_format(
    legacy_path: Path,
    groups_dir: Path,
    restriction_path: Path,
    user_path: Path,
    logger: Logger,
    RestrictionConfig: type,
    GroupConfig: type,
    UserData: type,
) -> None:
    """从最旧格式 jmcomic_data.json 迁移"""
    backup_path = legacy_path.with_suffix(".json.bak")
    logger.info(f"检测到旧数据文件，开始迁移: {legacy_path}")

    try:
        with legacy_path.open("r", encoding="utf-8") as f:
            old_data: dict = json.load(f)

        # 迁移全局配置
        new_global = RestrictionConfig()
        if "restricted_tags" in old_data:
            new_global.restricted_tags = set(old_data["restricted_tags"])
        if "restricted_ids" in old_data:
            new_global.restricted_ids = set(old_data["restricted_ids"])
        # 将旧的 forbidden_albums 合并到 restricted_ids
        if "forbidden_albums" in old_data:
            new_global.restricted_ids.update(old_data["forbidden_albums"])

        encoded = msgspec.json.encode(new_global)
        with atomic_save(str(restriction_path), text_mode=False) as f:
            f.write(encoded)  # type: ignore[arg-type]

        # 迁移用户数据
        new_users = UserData()
        if "user_limits" in old_data:
            new_users.user_limits = old_data["user_limits"]
        if new_users.user_limits:
            encoded = msgspec.json.encode(new_users)
            with atomic_save(str(user_path), text_mode=False) as f:
                f.write(encoded)  # type: ignore[arg-type]

        # 迁移群配置
        group_count = 0
        for key, value in old_data.items():
            if key in (
                "restricted_tags",
                "restricted_ids",
                "forbidden_albums",
                "user_limits",
            ):
                continue
            if key.isdigit() and isinstance(value, dict):
                old_enabled = value.get("enabled")
                group_config = GroupConfig(
                    folder_id=value.get("folder_id"),
                    enabled=old_enabled if old_enabled is not None else msgspec.UNSET,
                    blacklist=set(value.get("blacklist", [])),
                )
                group_path = groups_dir / f"{key}.json"
                encoded = msgspec.json.encode(group_config)
                with atomic_save(str(group_path), text_mode=False) as f:
                    f.write(encoded)  # type: ignore[arg-type]
                group_count += 1

        # 备份旧文件
        shutil.copy2(legacy_path, backup_path)
        legacy_path.unlink()

        logger.info(
            f"数据迁移完成！\n"
            f"  - 群配置数: {group_count}\n"
            f"  - 用户限制数: {len(new_users.user_limits)}\n"
            f"  - 旧文件已备份至: {backup_path}"
        )

    except Exception as e:
        logger.error(f"数据迁移失败: {e}")


def _migrate_from_group_json(
    old_path: Path,
    groups_dir: Path,
    restriction_path: Path,
    logger: Logger,
    RestrictionConfig: type,
    GroupConfig: type,
) -> None:
    """从上一版本 group.json / config.json 迁移"""
    logger.info("检测到上一版本数据文件，开始迁移...")

    try:
        with old_path.open("r", encoding="utf-8") as f:
            old_data: dict = json.load(f)

        # 迁移全局配置
        new_global = RestrictionConfig()
        if "restricted_tags" in old_data:
            new_global.restricted_tags = set(old_data["restricted_tags"])
        if "restricted_ids" in old_data:
            new_global.restricted_ids = set(old_data["restricted_ids"])
        # 将旧的 forbidden_albums 合并到 restricted_ids
        if "forbidden_albums" in old_data:
            new_global.restricted_ids.update(old_data["forbidden_albums"])

        encoded = msgspec.json.encode(new_global)
        with atomic_save(str(restriction_path), text_mode=False) as f:
            f.write(encoded)  # type: ignore[arg-type]

        # 迁移群配置
        groups = old_data.get("groups", {})
        for group_id, group_data in groups.items():
            if isinstance(group_data, dict):
                old_enabled = group_data.get("enabled")
                group_config = GroupConfig(
                    folder_id=group_data.get("folder_id"),
                    enabled=old_enabled if old_enabled is not None else msgspec.UNSET,
                    blacklist=set(group_data.get("blacklist", [])),
                )
                group_path = groups_dir / f"{group_id}.json"
                encoded = msgspec.json.encode(group_config)
                with atomic_save(str(group_path), text_mode=False) as f:
                    f.write(encoded)  # type: ignore[arg-type]

        # 备份旧文件
        shutil.copy2(old_path, old_path.with_suffix(".json.bak"))
        old_path.unlink()

        logger.info("上一版本数据迁移完成！")

    except Exception as e:
        logger.error(f"数据迁移失败: {e}")
