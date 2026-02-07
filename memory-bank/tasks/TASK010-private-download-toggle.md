# [TASK010] - 私聊下载开关配置

**Status:** Completed
**Added:** 2026-02-01
**Updated:** 2026-02-06

## Original Request

新增一个配置字段，用于控制是否允许私聊下载。

## Thought Process

### 当前状态

目前私聊功能默认启用，没有开关控制：
- `jm_download_private` - 私聊下载命令
- `jm_search_private` - 私聊搜索命令
- `jm_query_private` - 私聊查询命令

### 设计方案

#### 1. 新增配置字段

```python
class Config(BaseModel):
    # 新增
    jmcomic_allow_private: bool = Field(
        default=True,
        description="是否允许私聊使用功能"
    )
```

#### 2. 实现方式

**方案 B**: 使用 Handler 参数类型注解（已实现）

```python
# common.py
async def private_enabled_check(event: PrivateMessageEvent, matcher: Matcher):
    """私聊功能开关检查：私聊功能禁用时静默终止（仅私聊触发）"""
    if not plugin_config.jmcomic_allow_private:
        await matcher.finish()

# handlers - 在命令的 handlers 列表中添加
jm_download = on_command(
    "jm下载",
    block=True,
    handlers=[
        private_enabled_check,  # 1. 私聊功能开关检查（仅私聊，禁用时静默终止）
        # ...
    ],
)
```

通过参数类型注解 `PrivateMessageEvent`，该 handler 仅在私聊时触发。

## Implementation Plan

- [x] 1. 修改 `config.py`:
  - 添加 `jmcomic_allow_private` 配置项

- [x] 2. 创建 `bot/handlers/common.py`:
  - 添加 `private_enabled_check` handler 函数

- [x] 3. 修改 handlers:
  - `download.py` - `jm_download`
  - `search.py` - `jm_search`, `jm_next_page`
  - `query.py` - `jm_query`
  - 为所有命令添加 `private_enabled_check` handler

- [x] 4. 更新文档

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description                | Status   | Updated    | Notes                   |
| ---- | -------------------------- | -------- | ---------- | ----------------------- |
| 10.1 | 修改 config.py             | Complete | 2026-02-06 | `jmcomic_allow_private` |
| 10.2 | 添加 private_enabled_check | Complete | 2026-02-06 | 在 common.py 中         |
| 10.3 | 修改私聊 handlers          | Complete | 2026-02-06 | 所有命令已集成检查      |
| 10.4 | 更新文档                   | Complete | 2026-02-06 |                         |

## Progress Log

### 2026-02-01

- 创建任务文件
- 设计实施方案

### 2026-02-06

- 确认代码实现已完成
- `jmcomic_allow_private` 配置项已添加到 config.py (Line 30)
- `private_enabled_check` handler 已在 common.py 中实现 (Line 14-17)
- 所有命令（jm下载、jm搜索、jm下一页、jm查询）已集成 private_enabled_check
- 采用方案 B（Handler 参数类型注解），通过 `PrivateMessageEvent` 类型注解控制触发范围
- 任务标记为完成
