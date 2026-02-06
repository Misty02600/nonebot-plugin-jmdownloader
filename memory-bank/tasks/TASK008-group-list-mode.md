# [TASK008] - 群启用黑白名单模式

**Status:** Pending
**Added:** 2026-02-01
**Updated:** 2026-02-01

## Original Request

`jmcomic_allow_groups` 准备改为黑白名单模式：
- 新增一个配置用于判断黑白名单模式
- 原有配置字段保留以向后兼容（`True` 为白名单）
- 黑名单模式：只有开启的群聊能使用功能（`False` 和 `UNSET` 不能）
- 白名单模式：只有关闭的群聊不能使用功能（`True` 和 `UNSET` 可以）
- 使用 `match case` 实现逻辑
- 权限：superuser 可以任意设置群聊开关，群主和管理员只能关不能开

## Thought Process

### 当前状态

```python
# config.py
jmcomic_allow_groups: bool = Field(default=False, description="是否默认启用所有群")

# GroupConfig
enabled: bool | msgspec.UnsetType = msgspec.UNSET

# is_enabled 方法
def is_enabled(self, default: bool = False) -> bool:
    if self.enabled is msgspec.UNSET:
        return default
    return self.enabled
```

### 设计方案

#### 1. 新增配置字段

```python
from enum import StrEnum

class GroupListMode(StrEnum):
    WHITELIST = "whitelist"  # 白名单模式（默认允许，显式禁止的不能用）
    BLACKLIST = "blacklist"  # 黑名单模式（默认禁止，显式允许的能用）

class Config(BaseModel):
    # 保留原字段用于向后兼容
    jmcomic_allow_groups: bool = Field(default=False)
    # 新增模式字段
    jmcomic_group_list_mode: GroupListMode | None = Field(default=None)
```

#### 2. 模式推断逻辑

```python
def get_list_mode(self) -> GroupListMode:
    """获取列表模式，优先使用新配置，否则从 allow_groups 推断"""
    if self.jmcomic_group_list_mode is not None:
        return self.jmcomic_group_list_mode
    # 向后兼容：allow_groups=True 相当于白名单模式
    return GroupListMode.WHITELIST if self.jmcomic_allow_groups else GroupListMode.BLACKLIST
```

#### 3. 群启用判断逻辑 (match case)

```python
def is_group_enabled(group_enabled: bool | UnsetType, mode: GroupListMode) -> bool:
    match (mode, group_enabled):
        # 白名单模式：True 和 UNSET 可以，False 不能
        case (GroupListMode.WHITELIST, False):
            return False
        case (GroupListMode.WHITELIST, _):  # True or UNSET
            return True
        # 黑名单模式：只有 True 可以
        case (GroupListMode.BLACKLIST, True):
            return True
        case (GroupListMode.BLACKLIST, _):  # False or UNSET
            return False
```

#### 4. 权限控制

| 操作者      | 开启群 | 关闭群 |
| ----------- | ------ | ------ |
| superuser   | ✅      | ✅      |
| 群主/管理员 | ❌      | ✅      |

```python
async def handle_set_group_enabled(event, target_enabled: bool):
    is_su = str(event.user_id) in superusers

    if target_enabled and not is_su:
        await matcher.finish("只有超级用户可以开启群功能")

    # 允许操作
    group.enabled = target_enabled
```

## Implementation Plan

- [ ] 1. 创建 `GroupListMode` 枚举（在 `core/data_models.py` 或 `config.py`）

- [ ] 2. 修改 `config.py`:
  - 添加 `jmcomic_group_list_mode` 配置
  - 添加 `get_list_mode()` 方法或属性

- [ ] 3. 修改 `core/data_models.py`:
  - 修改 `GroupConfig.is_enabled()` 方法，接受 mode 参数
  - 使用 `match case` 实现新逻辑

- [ ] 4. 修改 `bot/dependencies.py`:
  - 更新 `GroupRule`，使用新的判断逻辑

- [ ] 5. 创建或修改群开关命令 handler:
  - 添加权限检查（superuser 可开可关，管理员只能关）
  - 或在现有命令中添加检查

- [ ] 6. 更新文档和测试

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description             | Status      | Updated | Notes |
| --- | ----------------------- | ----------- | ------- | ----- |
| 8.1 | 创建 GroupListMode 枚举 | Not Started |         |       |
| 8.2 | 修改 config.py          | Not Started |         |       |
| 8.3 | 修改 data_models.py     | Not Started |         |       |
| 8.4 | 修改 dependencies.py    | Not Started |         |       |
| 8.5 | 修改群开关命令权限      | Not Started |         |       |
| 8.6 | 更新测试                | Not Started |         |       |

## Progress Log

### 2026-02-01

- 创建任务文件
- 设计黑白名单模式逻辑
- 规划权限控制方案
