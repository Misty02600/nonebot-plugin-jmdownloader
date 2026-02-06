# [TASK017] - 合并重复命令 Matcher

**Status:** Completed
**Added:** 2026-02-06
**Updated:** 2026-02-06

## Original Request

解决 `Duplicated prefix rule` 警告。当前采用分离的群聊/私聊 matcher（如 `jm_download_group` 和 `jm_download_private`），由于使用相同的命令名和别名，NoneBot 会产生重复注册警告。

问题在于使用了 `block=True`，如果两个 matcher 匹配相同命令但只有一个能执行（因 permission 限制），另一个不会被触发，可能导致意外行为。

## Thought Process

### 现状分析

当前每个命令都有独立的群聊和私聊 matcher：
- `jm_download_group` + `jm_download_private`
- `jm_query_group` + `jm_query_private`
- `jm_search_group` + `jm_search_private`
- `jm_next_page_group` + `jm_next_page_private`

每对 matcher 使用相同的 `cmd` 和 `aliases`，导致警告。

### 解决方案

合并为单个 matcher，在 handler 内部根据事件类型分发：

1. **统一 Matcher** - 移除 `permission=GROUP/PRIVATE`，使用通用权限
2. **GroupRule** - 不能直接用在 matcher 上，需改为 handler 内部检查
3. **事件类型分发** - 通用 handler 使用 `MessageEvent`，专用 handler 使用具体事件类型

### Handler 设计

```python
from nonebot.matcher import Matcher

# 统一 matcher（不指定 permission）
jm_download = on_command(
    "jm下载",
    aliases={"JM下载"},
    block=True,
)

# 群聊启用检查（仅群聊触发，使用 matcher.finish() 静默终止）
async def group_enabled_check(event: GroupMessageEvent, matcher: Matcher, dm: DataManagerDep):
    """群聊启用检查：群未启用则静默终止"""
    group = dm.get_group(event.group_id)
    if not group.is_enabled(dm.default_enabled):
        await matcher.finish()  # 静默终止，不发消息

# 通用 handler（群聊和私聊都触发）
async def common_handler(event: MessageEvent, ...):
    ...

# 私聊专用 handler（仅私聊触发）
async def private_upload(event: PrivateMessageEvent, ...):
    ...
```

NoneBot 会根据 handler 的参数类型注解自动过滤：
- `GroupMessageEvent` 参数 → 仅群聊触发
- `PrivateMessageEvent` 参数 → 仅私聊触发
- `MessageEvent` 参数 → 两者都触发

**关键点**：`matcher.finish()` 不传参数时不发送消息，直接结束流程。

## Implementation Plan

1. **修改 download.py**
   - 合并 `jm_download_group` 和 `jm_download_private` 为 `jm_download`
   - 将 `GroupRule` 检查改为 `group_enabled_check` handler
   - 调整 handler 参数类型注解实现分发

2. **修改 query.py**
   - 合并 `jm_query_group` 和 `jm_query_private`

3. **修改 search.py**
   - 合并 `jm_search_group` 和 `jm_search_private`
   - 合并 `jm_next_page_group` 和 `jm_next_page_private`

4. **更新 dependencies.py**
   - 移除或重构 `GroupRule`（改为 handler 函数）

5. **验证**
   - 运行测试确保功能正常
   - 确认警告消失

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description                   | Status   | Updated    | Notes                                        |
| ---- | ----------------------------- | -------- | ---------- | -------------------------------------------- |
| 17.1 | 修改 download.py 合并 matcher | Complete | 2026-02-06 | 合并为 jm_download，添加 group_enabled_check |
| 17.2 | 修改 query.py 合并 matcher    | Complete | 2026-02-06 | 合并为 jm_query                              |
| 17.3 | 修改 search.py 合并 matcher   | Complete | 2026-02-06 | 合并为 jm_search 和 jm_next_page             |
| 17.4 | 更新 dependencies.py          | Complete | 2026-02-06 | 移除 GroupRule 及相关函数                    |
| 17.5 | 运行测试验证                  | Complete | 2026-02-06 | 114 tests passed                             |

## Progress Log

### 2026-02-06
- 任务创建
- 分析了问题原因和解决方案
- 确定使用 handler 参数类型注解实现自动分发
- 更新设计：使用 `matcher.finish()` 静默终止替代 `SkipException`
- **开始执行**
- 修改 download.py：
  - 合并 `jm_download_group` 和 `jm_download_private` 为 `jm_download`
  - 添加 `group_enabled_check` handler
  - 移除 `permission=GROUP/PRIVATE` 和 `rule=GroupRule`
- 修改 query.py：合并为 `jm_query`
- 修改 search.py：合并为 `jm_search` 和 `jm_next_page`
- 更新 dependencies.py：移除 `GroupRule` 及相关函数
- 更新 bot/__init__.py：移除 `GroupRule` 导出
- 更新测试文件 tests/plugin_test.py
- **测试通过：114 passed**
- **任务完成**

