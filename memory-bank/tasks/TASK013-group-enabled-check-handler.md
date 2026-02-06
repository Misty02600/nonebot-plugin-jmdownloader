# [TASK013] - 群启用检查改为事件处理

**Status:** Pending
**Added:** 2026-02-05
**Updated:** 2026-02-05

## Original Request

`group_is_enabled` 不放在 `GroupRule` 里检查，而是作为一个事件处理，当群未启用功能时，发送提示词。

## Background

当前实现中，`GroupRule` 包含两个检查：
1. `group_is_enabled` - 检查群是否启用插件功能
2. `group_user_not_in_blacklist` - 检查用户是否在群黑名单中

```python
GroupRule = Rule(group_is_enabled) & Rule(group_user_not_in_blacklist)
```

问题：当 `group_is_enabled` 返回 `False` 时，命令被静默忽略，用户不知道为什么命令没有响应。

## Thought Process

### 方案分析

**方案 A：使用前置 handler 检查**
- 将 `group_is_enabled` 检查移至 `checks.py`，作为一个前置检查函数
- 在需要群启用检查的命令中添加此前置 handler
- 检查失败时发送提示信息并 `matcher.finish()`

**方案 B：使用 NoneBot 的 permission 机制**
- 创建自定义 Permission 类
- 不适合，因为 permission 无法发送消息

**推荐：方案 A**
- 与现有的 `user_blacklist_check`、`download_limit_check` 模式一致
- 可以自定义提示信息
- 灵活控制哪些命令需要此检查

### 设计细节

1. 在 `checks.py` 中添加 `group_enabled_check` 函数
2. 从 `GroupRule` 中移除 `group_is_enabled`
3. 在群聊命令中添加 `group_enabled_check` 作为第一个前置 handler
4. 提示词可配置（考虑添加配置项或直接硬编码）

### 提示词建议

- "本群未启用此功能"
- "请联系管理员启用本插件功能"

## Implementation Plan

- [ ] 1. 在 `checks.py` 中添加 `group_enabled_check` 函数
- [ ] 2. 修改 `dependencies.py`，从 `GroupRule` 中移除 `group_is_enabled`
- [ ] 3. 更新所有使用 `GroupRule` 的群聊命令，添加 `group_enabled_check` 前置 handler
  - [ ] `search.py` - `jm_search_group`, `jm_next_page_group`
  - [ ] `query.py` - `jm_query_group`
  - [ ] `download.py` - `jm_download_group`
  - [ ] `scheduled.py` - 检查是否需要
  - [ ] `group_control.py` - 管理命令可能不需要此检查
- [ ] 4. 运行测试确保功能正常
- [ ] 5. 更新文档（如有必要）

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID   | Description                   | Status      | Updated    | Notes |
| ---- | ----------------------------- | ----------- | ---------- | ----- |
| 13.1 | 添加 group_enabled_check 函数 | Not Started | 2026-02-05 |       |
| 13.2 | 修改 GroupRule                | Not Started | 2026-02-05 |       |
| 13.3 | 更新 search.py                | Not Started | 2026-02-05 |       |
| 13.4 | 更新 query.py                 | Not Started | 2026-02-05 |       |
| 13.5 | 更新 download.py              | Not Started | 2026-02-05 |       |
| 13.6 | 检查并更新其他 handlers       | Not Started | 2026-02-05 |       |
| 13.7 | 运行测试                      | Not Started | 2026-02-05 |       |

## Progress Log

### 2026-02-05
- 创建任务文件
- 分析当前实现和改进方案
- 确定使用前置 handler 模式（与现有检查函数一致）
