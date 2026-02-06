# [TASK004] - 依赖注入（简化版）

**Status:** Pending
**Added:** 2026-01-28
**Updated:** 2026-01-28

## Original Request

仅针对 `get_group_config` 采用依赖注入，config 和 data_manager 保持在各自模块实例化。

## Thought Process

### 决策

| 组件               | 处理方式                                |
| ------------------ | --------------------------------------- |
| `config`           | 保持在 `config.py` 模块级实例化         |
| `data_manager`     | 保持在 `__init__.py` 实例化             |
| `get_group_config` | **使用依赖注入**，根据 event 获取群配置 |

### 为什么只对 group_config 用依赖注入？

- `GroupConfig` 需要根据 `event.group_id` 动态获取
- 避免在每个 handler 中重复 `data_manager.get_group(str(event.group_id))`
- 使 handler 函数更简洁

### 依赖函数设计

```python
# dependencies.py

from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.params import Depends

def get_group_config(event: GroupMessageEvent):
    """获取当前群的配置"""
    from . import data_manager
    return data_manager.get_group(str(event.group_id))

# 类型别名，方便使用
GroupConfigDep = Depends(get_group_config)
```

### 使用示例

```python
# handlers.py
from .dependencies import get_group_config, GroupConfigDep

@jm_set_folder.handle()
async def _(
    bot: Bot,
    event: GroupMessageEvent,
    arg: Message = CommandArg(),
    group: GroupConfig = GroupConfigDep,  # 自动注入
):
    # 直接使用 group，不需要 data_manager.get_group()
    group.folder_id = folder_id
    data_manager.save_group(str(event.group_id))
```

## Implementation Plan

- [ ] 1. 创建 `dependencies.py`
  - 只包含 `get_group_config` 依赖函数
- [ ] 2. 更新 `utils.py` 中的 Rule 函数
  - `user_not_in_blacklist` → 使用 `get_group_config` 依赖
  - `group_is_enabled` → 使用 `get_group_config` 依赖
- [ ] 3. 在需要的 handler 中使用依赖注入
  - `jm_set_folder`
  - `jm_ban_user`
  - `jm_unban_user`
  - `jm_blacklist`
  - `jm_enable_here`
  - `jm_disable_here`
- [ ] 4. 运行测试验证

### utils.py Rule 函数改进

**之前：**
```python
async def group_is_enabled(bot: Bot, event: MessageEvent) -> bool:
    if isinstance(event, GroupMessageEvent):
        from . import data_manager
        group = data_manager.get_group(str(event.group_id))  # 重复逻辑
        if not group.is_enabled(data_manager.default_enabled):
            return False
    return True
```

**之后：**
```python
from nonebot.params import Depends
from .dependencies import get_group_config

async def group_is_enabled(
    event: MessageEvent,
    group = Depends(get_group_config),
) -> bool:
    if isinstance(event, GroupMessageEvent):
        from . import data_manager
        if not group.is_enabled(data_manager.default_enabled):
            return False
    return True
```

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description          | Status      | Updated | Notes |
| --- | -------------------- | ----------- | ------- | ----- |
| 4.1 | 创建 dependencies.py | Not Started | -       | -     |
| 4.2 | 更新相关 handlers    | Not Started | -       | -     |
| 4.3 | 测试验证             | Not Started | -       | -     |

## Progress Log

### 2026-01-28 (下午 11:11)
- **范围调整**：用户决定简化范围
  - config 和 data_manager 保持现状
  - 只对 `get_group_config` 使用依赖注入
