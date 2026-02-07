# [TASK013] - 群启用检查改为事件处理

**Status:** Completed
**Added:** 2026-02-05
**Updated:** 2026-02-07

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

1. 在 `common.py` 中的 `group_enabled_check` 函数添加提示消息
2. 用户未启用功能时发送 "当前群聊未开启该功能"
3. 私聊功能禁用时发送 "私聊功能已禁用"

## Implementation

已实施的改动（2026-02-07）：

```python
# bot/handlers/common.py

async def private_enabled_check(event: PrivateMessageEvent, matcher: Matcher):
    """私聊功能开关检查：私聊功能禁用时终止（仅私聊触发）"""
    if not plugin_config.jmcomic_allow_private:
        await matcher.finish("私聊功能已禁用")


async def group_enabled_check(
    event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep
):
    """群聊启用检查：群未启用时终止（仅群聊触发）"""
    group = dm.get_group(event.group_id)
    if not group.is_enabled(dm.group_mode):
        await matcher.finish("当前群聊未开启该功能")
```

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description                   | Status   | Updated    | Notes                      |
| ---- | ----------------------------- | -------- | ---------- | -------------------------- |
| 13.1 | 添加 group_enabled_check 函数 | Complete | 2026-02-05 | 在 TASK011 中已实现        |
| 13.2 | 修改 GroupRule                | Complete | 2026-02-05 | 在 TASK017 中已移除        |
| 13.3 | 更新 search.py                | Complete | 2026-02-05 | 已集成 group_enabled_check |
| 13.4 | 更新 query.py                 | Complete | 2026-02-05 | 已集成 group_enabled_check |
| 13.5 | 更新 download.py              | Complete | 2026-02-05 | 已集成 group_enabled_check |
| 13.6 | 添加用户提示消息              | Complete | 2026-02-07 | "当前群聊未开启该功能"     |
| 13.7 | 运行测试                      | Complete | 2026-02-07 | 114 tests passed           |

## Progress Log

### 2026-02-05
- 创建任务文件
- 分析当前实现和改进方案
- 确定使用前置 handler 模式（与现有检查函数一致）

### 2026-02-07
- 修改 `group_enabled_check`：添加提示消息 "当前群聊未开启该功能"
- 修改 `private_enabled_check`：添加提示消息 "私聊功能已禁用"
- **任务标记为完成**
