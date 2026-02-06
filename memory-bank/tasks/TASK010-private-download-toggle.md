# [TASK010] - 私聊下载开关配置

**Status:** Completed
**Added:** 2026-02-01
**Updated:** 2026-02-06

## Original Request

新增一个配置字段，用于控制是否允许私聊下载。

## Thought Process

### 当前状态（重构后）

代码已重构为**统一 Matcher + handlers 前置检查模式**：
- 群聊和私聊共用同一个 matcher（如 `jm_download`）
- 通过 handler 函数的参数类型注解实现自动分发
  - `GroupMessageEvent` - 仅群聊触发
  - `PrivateMessageEvent` - 仅私聊触发
  - `MessageEvent` - 群聊和私聊都触发

### 设计方案

#### 1. 新增配置字段

```python
# config.py
class PluginConfig(BaseModel):
    jmcomic_allow_private: bool = Field(
        default=True,
        description="是否允许私聊使用功能"
    )
```

#### 2. 实现方式

**方案 A**: 添加前置检查 handler（推荐）

符合当前架构的统一模式：

```python
# 在各 handler 文件中添加前置检查
async def private_enabled_check(
    event: PrivateMessageEvent, matcher: Matcher
):
    """私聊功能开关检查：私聊功能禁用时静默终止（仅私聊触发）"""
    if not plugin_config.jmcomic_allow_private:
        await matcher.finish()

# 命令注册
jm_download = on_command(
    "jm下载",
    handlers=[
        group_enabled_check,       # 群聊启用检查
        private_enabled_check,     # 私聊功能开关检查 <- 新增
        user_blacklist_check,
        download_limit_check,
        # ...
    ],
)
```

**方案 B**: 使用 Rule

```python
# bot/dependencies.py
def private_allowed() -> bool:
    return plugin_config.jmcomic_allow_private

PrivateAllowed = Rule(private_allowed)

# 需要修改 matcher 定义
jm_download = on_command(
    "jm下载",
    rule=PrivateAllowed,  # 但这会影响群聊...
)
```

方案 B 的问题：Rule 对群聊和私聊都生效。需要复杂的组合逻辑。

**结论**：采用**方案 A**，与现有架构一致。

#### 3. 检查插入位置

私聊检查应放在 handlers 列表的**最前面**，这样私聊禁用时可以立即终止：

```python
handlers=[
    private_enabled_check,     # 1. 私聊功能开关（仅私聊）
    group_enabled_check,       # 2. 群聊启用检查（仅群聊）
    user_blacklist_check,      # 3. 群聊黑名单检查（仅群聊）
    ...
]
```

## Implementation Plan

- [ ] 1. 修改 `config.py`:
  - 添加 `jmcomic_allow_private: bool = True` 配置项

- [ ] 2. 在各 handler 文件中添加 `private_enabled_check` 函数:
  - `download.py`
  - `search.py`
  - `query.py`
  - 函数需要从 `bot/dependencies.py` 获取 `plugin_config`

- [ ] 3. 更新各命令的 handlers 列表:
  - 在列表开头添加 `private_enabled_check`
  - 涉及命令: `jm_download`, `jm_search`, `jm_query`, `jm_next_page`

- [ ] 4. 更新 README.md:
  - 在配置表中添加 `jmcomic_allow_private`
  - 在示例配置中添加说明

- [ ] 5. 更新 Memory Bank:
  - techContext.md 配置表

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description                | Status   | Updated    | Notes                          |
| ---- | -------------------------- | -------- | ---------- | ------------------------------ |
| 10.1 | 修改 config.py             | Complete | 2026-02-06 |                                |
| 10.2 | 添加 private_enabled_check | Complete | 2026-02-06 | 在 download/search/query.py 中 |
| 10.3 | 更新 handlers 列表         | Complete | 2026-02-06 | 4 个命令                       |
| 10.4 | 更新 README.md             | Complete | 2026-02-06 |                                |
| 10.5 | 更新 Memory Bank           | Complete | 2026-02-06 |                                |

## Progress Log

### 2026-02-01

- 创建任务文件
- 设计实施方案

### 2026-02-06

- 更新实现方案以适配重构后的代码架构
- 采用 handlers 前置检查模式（方案 A）
- 更新 subtasks 列表
- ✅ 实施完成：
  - 添加 `jmcomic_allow_private` 配置项到 config.py
  - 在 download.py, search.py, query.py 中添加 `private_enabled_check` 函数
  - 更新 4 个命令的 handlers 列表（jm_download, jm_search, jm_query, jm_next_page）
  - 更新 README.md 配置表和示例
  - 更新 techContext.md 配置表
  - 114 tests passed ✅
