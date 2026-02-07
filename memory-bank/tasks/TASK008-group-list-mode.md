# [TASK008] - 群启用黑白名单模式

**Status:** Completed
**Added:** 2026-02-01
**Updated:** 2026-02-07

## Original Request

`jmcomic_allow_groups` 准备改为黑白名单模式：
- 新增 `jmcomic_group_list_mode` 配置
- 原字段 `jmcomic_allow_groups` 作为别名，`bool` → `GroupListMode` 自动转换
- 黑名单模式：只有显式启用的群能用（`True` 可以，`False` 和 `UNSET` 不能）
- 白名单模式：只有显式禁用的群不能用（`True` 和 `UNSET` 可以，`False` 不能）

## 设计方案

### 1. 枚举定义：`core/enums.py`

```python
class GroupListMode(StrEnum):
    """群列表模式"""
    WHITELIST = "whitelist"  # 白名单：默认允许，显式禁止的不能用
    BLACKLIST = "blacklist"  # 黑名单：默认禁止，显式允许的能用
```

**映射关系：**
| `jmcomic_allow_groups` (旧) | `GroupListMode` (新) | 说明           |
| --------------------------- | -------------------- | -------------- |
| `True`                      | `WHITELIST`          | 默认允许所有群 |
| `False`                     | `BLACKLIST`          | 默认禁止所有群 |

---

### 2. 配置修改：`config.py`

```python
from .core.enums import GroupListMode, OutputFormat

class PluginConfig(BaseModel):
    # 新主配置（优先级高）
    jmcomic_group_list_mode: GroupListMode = Field(
        default=GroupListMode.BLACKLIST,
        description="群列表模式：blacklist（默认禁用） / whitelist（默认启用）"
    )

    # 旧配置作为别名（向后兼容）
    jmcomic_allow_groups: bool | None = Field(
        default=None,
        description="[废弃] 请使用 jmcomic_group_list_mode"
    )

    @model_validator(mode='after')
    def resolve_group_mode(self) -> Self:
        """如果用户设置了旧配置，转换为新配置"""
        if self.jmcomic_allow_groups is not None:
            # 将 bool 转换为 GroupListMode
            self.jmcomic_group_list_mode = (
                GroupListMode.WHITELIST if self.jmcomic_allow_groups
                else GroupListMode.BLACKLIST
            )
        return self
```

**注意**：使用 `model_validator` 而不是 `field_validator`，因为需要在验证后修改字段值。

---

### 3. 数据模型修改：`core/data_models.py`

`GroupConfig.is_enabled()` 方法需要接受新的 `mode` 参数：

```python
class GroupConfig(msgspec.Struct, omit_defaults=True):
    folder_id: str | None = None
    enabled: bool | msgspec.UnsetType = msgspec.UNSET
    blacklist: set[str] = msgspec.field(default_factory=set)

    def is_enabled(self, mode: GroupListMode) -> bool:
        """根据列表模式检查群是否启用功能

        Args:
            mode: 群列表模式（WHITELIST / BLACKLIST）

        Returns:
            是否启用功能
        """
        match (mode, self.enabled):
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

**行为对照表：**
| 模式          | `enabled=True` | `enabled=UNSET` | `enabled=False` |
| ------------- | -------------- | --------------- | --------------- |
| **WHITELIST** | ✅ 启用         | ✅ 启用          | ❌ 禁用          |
| **BLACKLIST** | ✅ 启用         | ❌ 禁用          | ❌ 禁用          |

---

### 4. DataManager 修改：`infra/data_manager.py`

将 `default_enabled: bool` 改为 `group_mode: GroupListMode`：

```python
class DataManager:
    def __init__(
        self,
        data_dir: Path,
        group_mode: GroupListMode,  # 改动
        default_user_limit: int,
    ):
        self.group_mode: GroupListMode = group_mode  # 改动
        ...
```

---

### 5. 依赖注入修改：`bot/dependencies.py`

```python
data_manager = DataManager(
    data_dir=data_dir,
    group_mode=plugin_config.jmcomic_group_list_mode,  # 改动：传入模式
    default_user_limit=plugin_config.jmcomic_user_limits,
)
```

---

### 6. Handler 修改：`bot/handlers/common.py`

```python
async def group_enabled_check(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """群聊启用检查：群未启用则静默终止（仅群聊触发）"""
    group = dm.get_group(event.group_id)
    if not group.is_enabled(dm.group_mode):  # 改动：传入模式而非 bool
        await matcher.finish()
```

---

### 7. 权限控制（已有，无需修改）

| 操作者      | 开启群 | 关闭群 |
| ----------- | ------ | ------ |
| superuser   | ✅      | ✅      |
| 群主/管理员 | ❌      | ✅      |

这个逻辑在 `bot/handlers/group_control.py` 中已经实现。

---

## Implementation Plan

- [ ] 1. **`core/enums.py`**: 添加 `GroupListMode` 枚举

- [ ] 2. **`config.py`**:
  - 添加 `jmcomic_group_list_mode` 配置项
  - 修改 `jmcomic_allow_groups` 为可选（默认 `None`）
  - 添加 `model_validator` 处理向后兼容

- [ ] 3. **`core/data_models.py`**:
  - 修改 `GroupConfig.is_enabled()` 方法签名
  - 使用 `match case` 实现新逻辑

- [ ] 4. **`infra/data_manager.py`**:
  - `default_enabled: bool` → `group_mode: GroupListMode`

- [ ] 5. **`bot/dependencies.py`**:
  - 更新 DataManager 初始化参数

- [ ] 6. **`bot/handlers/common.py`**:
  - 更新 `group_enabled_check` 调用

- [ ] 7. **更新文档和测试**:
  - README 配置说明
  - 单元测试用例

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID  | Description             | Status   | Updated    | Notes               |
| --- | ----------------------- | -------- | ---------- | ------------------- |
| 8.1 | 添加 GroupListMode 枚举 | Complete | 2026-02-07 | `core/enums.py`     |
| 8.2 | 修改 config.py          | Complete | 2026-02-07 | 新配置 + 别名兼容   |
| 8.3 | 修改 data_models.py     | Complete | 2026-02-07 | `is_enabled(mode)`  |
| 8.4 | 修改 data_manager.py    | Complete | 2026-02-07 | `group_mode` 参数   |
| 8.5 | 修改 dependencies.py    | Complete | 2026-02-07 | 初始化参数          |
| 8.6 | 修改 common.py          | Complete | 2026-02-07 | handler 调用        |
| 8.7 | 更新文档和测试          | Complete | 2026-02-07 | README + tests 更新 |

## Progress Log

### 2026-02-01

- 创建任务文件
- 设计黑白名单模式逻辑
- 规划权限控制方案

### 2026-02-07

- 更新设计方案：
  - `jmcomic_allow_groups` 作为 `jmcomic_group_list_mode` 的别名
  - 使用 `model_validator` 处理 `bool` → `GroupListMode` 转换
  - 详细说明每个模块的改动内容
- 简化子任务列表
- **实施完成**：
  - `core/enums.py`: 添加 `GroupListMode` 枚举
  - `config.py`: 新增配置 + model_validator 别名兼容
  - `core/data_models.py`: 使用 match case 实现新逻辑
  - `infra/data_manager.py`: `group_mode` 参数
  - `bot/dependencies.py`: 更新初始化
  - `bot/handlers/common.py`: 更新调用
  - `tests/units/test_data_models.py`: 更新测试用例
  - `README.md`: 更新配置文档
- **任务标记为完成** - 114 tests passed
