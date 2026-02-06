# [TASK010] - 私聊下载开关配置

**Status:** Pending
**Added:** 2026-02-01
**Updated:** 2026-02-01

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

**方案 A**: 在 handler 中检查

```python
@jm_download_private.handle()
async def handle_private_download(...):
    if not plugin_config.jmcomic_allow_private:
        await jm_download_private.finish("私聊功能已禁用")
    # ...
```

**方案 B**: 使用 Rule（推荐）

```python
# dependencies.py
def PrivateRule() -> bool:
    """私聊功能开关规则"""
    return plugin_config.jmcomic_allow_private

# handlers
jm_download_private = on_command(
    "jm下载",
    permission=PRIVATE,
    rule=PrivateRule,  # 添加规则
    block=True,
)
```

方案 B 更优雅，如果禁用私聊，命令直接不响应。

## Implementation Plan

- [ ] 1. 修改 `config.py`:
  - 添加 `jmcomic_allow_private` 配置项

- [ ] 2. 修改 `bot/dependencies.py`:
  - 添加 `PrivateRule` 规则函数

- [ ] 3. 修改私聊 handlers:
  - `download.py` - `jm_download_private`
  - `search.py` - `jm_search_private`, `jm_next_page_private`
  - `query.py` - `jm_query_private`
  - 为所有私聊命令添加 `rule=PrivateRule`

- [ ] 4. 更新文档

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID   | Description       | Status      | Updated | Notes |
| ---- | ----------------- | ----------- | ------- | ----- |
| 10.1 | 修改 config.py    | Not Started |         |       |
| 10.2 | 添加 PrivateRule  | Not Started |         |       |
| 10.3 | 修改私聊 handlers | Not Started |         |       |
| 10.4 | 更新文档          | Not Started |         |       |

## Progress Log

### 2026-02-01

- 创建任务文件
- 设计实施方案
