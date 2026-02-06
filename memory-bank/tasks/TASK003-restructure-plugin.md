# [TASK003] - 重构插件结构

**Status:** Pending
**Added:** 2026-01-28
**Updated:** 2026-01-28

## Original Request

将 `__init__.py` 的处理函数提取到 `handlers.py` 模块，把 `__init__.py` 作为纯粹的入口点（类似 main 函数）。

## Thought Process

### 当前问题

- `__init__.py` 700+ 行，太臃肿
- 初始化逻辑分散在各模块
- 使用延迟初始化和单例模式增加复杂度

### 新架构

```
src/nonebot_plugin_jmdownloader/
├── __init__.py        # 入口：元数据、初始化、导入 handlers
├── handlers.py        # 所有命令处理函数
├── config.py          # 配置
├── data.py            # 数据模型 + 存储（简化，不需要延迟初始化）
├── session.py         # 搜索会话
├── migration.py       # 数据迁移
└── utils.py           # 工具函数
```

### 设计原则

1. **`__init__.py` 作为入口**：所有初始化在这里完成
2. **删除延迟初始化**：不需要 `__getattr__`、单例模式
3. **清晰的依赖关系**：`__init__.py` -> `handlers.py` -> `data.py` / `utils.py`

## Implementation Plan

- [ ] 1. 创建 `handlers.py`，移入所有命令处理函数
- [ ] 2. 简化 `data.py`：
  - 删除 DataManager 类
  - 使用模块级函数：`init()`, `get_group()`, `save_group()`, `save_users()`, `save_global()`
  - 删除延迟初始化（`__getattr__`）
- [ ] 3. 简化 `__init__.py`：
  - 只保留元数据、初始化、导入 handlers
  - 在这里调用 `data.init()`
- [ ] 4. 更新导入方式
- [ ] 5. 运行测试验证

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description      | Status      | Updated | Notes |
| --- | ---------------- | ----------- | ------- | ----- |
| 3.1 | 创建 handlers.py | Not Started | -       | -     |
| 3.2 | 简化 data.py     | Not Started | -       | -     |
| 3.3 | 简化 __init__.py | Not Started | -       | -     |
| 3.4 | 测试验证         | Not Started | -       | -     |

## Progress Log

### 2026-01-28 (下午 9:49)
- **任务创建**：讨论后确定方向
  - 把 `__init__.py` 当作 main 函数
  - 删除延迟初始化和单例模式
  - 提取 handlers 到独立模块
