# [TASK011] - Handlers 前置检查模式重构

**Status:** In Progress
**Added:** 2026-02-04
**Updated:** 2026-02-04

## Original Request

使用 NoneBot 的多 handlers 机制来分离鉴权和验证逻辑，将检查逻辑作为独立的 handler 函数，实现关注点分离。

## 最佳实践模式（基于 download.py 实践总结）

### 核心模式

```python
# 1. 辅助函数区域
def build_xxx_message(...) -> str: ...

# 2. 事件处理函数（按执行顺序定义）
async def step1_check(...): ...
async def step2_process(...): ...
async def step3_upload(...): ...

# 3. 命令注册（放在文件最后）
jm_xxx = on_command(
    "jm命令",
    handlers=[step1_check, step2_process, step3_upload],  # 执行顺序一目了然
)
```

### 关键设计决策

1. **依赖可以 finish**：允许在 `Depends` 中调用 `matcher.finish()` 终止流程
2. **Photo 依赖**：合并验证 + API 调用，Depends 缓存确保只调用一次
3. **Union 类型合并**：群聊/私聊事件用 `MessageEvent` 统一处理
4. **handlers=[] 声明式**：移除 `@matcher.handle()` 装饰器
5. **函数先定义，matcher 后注册**：Python 顺序执行要求

### 依赖层次

| 层级          | 模块                         | 职责               | 可否 finish |
| ------------- | ---------------------------- | ------------------ | ----------- |
| params.py     | ArgText, Photo               | 解析 + 验证 + 获取 | ✅ 可以      |
| checks.py     | blacklist_check, limit_check | 业务检查           | ✅ 可以      |
| handlers/*.py | consume_and_notify, upload   | 业务逻辑           | ✅ 可以      |

### 典型 Photo 依赖实现

```python
# params.py
async def get_photo(photo_id: ArgText, matcher: Matcher) -> JmPhotoDetail:
    if not photo_id.isdigit():
        await matcher.finish("请输入有效的jm号")
    try:
        return await jm_service.get_photo(photo_id)
    except MissingAlbumPhotoException:
        await matcher.finish("未查找到本子")
    except Exception:
        await matcher.finish("查询时发生错误")

Photo = Annotated[JmPhotoDetail, Depends(get_photo)]
```

## 待重构 Handler 分析

### query.py（查询命令）
- **当前问题**：使用 `@matcher.handle()` 装饰器，手动解析参数
- **重构方案**：
  - 使用 `Photo` 依赖（复用 download.py 的模式）
  - 移除 `QueryResult` dataclass，改用函数式
  - 合并群聊/私聊发送逻辑

### blacklist.py（黑名单管理）
- **当前问题**：重复的权限检查代码（拉黑/解除拉黑）
- **重构方案**：
  - 创建 `AtTarget` 依赖解析 @ 目标
  - 创建 `at_target_check` 验证 @ 必填
  - 创建 `can_operate_target_check` 验证操作权限
  - `jm黑名单` 无需参数，直接保持简单

### search.py（搜索命令）
- **当前问题**：群聊/私聊逻辑重复，手动解析参数
- **重构方案**：
  - 使用 `ArgText` 依赖
  - 创建 `search_query_check` 验证非空
  - 合并群聊/私聊的搜索逻辑（使用 `MessageEvent`）
  - `jm下一页` 逻辑相对独立，可以类似处理

### content_filter.py（内容过滤）
- **当前问题**：手动解析参数
- **重构方案**：
  - 创建 `PhotoIds` 依赖（解析多个 photo_id）
  - 创建 `Tags` 依赖（解析多个 tag）
  - 创建对应的 check 函数
  - permission=SUPERUSER 已处理权限

### group_control.py（群控制）
- **当前问题**：部分命令使用 `.got()` 交互式
- **重构方案**：
  - 简单命令可以用 handlers=[] 模式
  - `.got()` 交互式的保持现状（这是 NoneBot 的正确用法）
  - permission 已处理权限

## 问题讨论

### 1. query.py 和 download.py 都需要 Photo 吗？

两者都需要获取 JmPhotoDetail：
- download.py：下载需要 photo 详情
- query.py：查询展示 photo 信息

但 query.py 当前使用 `jm_service.get_photo_info()` 返回 tuple，不是 `JmPhotoDetail`。

**问题**：是否统一使用 `Photo` 依赖？还是 query 保持使用不同的 API？

### 2. search.py 的 session 管理

搜索/下一页需要管理 session 状态：
- 搜索创建 session，存入 `sessions`
- 下一页从 `sessions` 获取

这个模式不太适合用 Depends，因为是业务状态管理。

**建议**：handler 内部处理 session，不抽取依赖。

### 3. blacklist.py 的 AtTarget 依赖

需要从 Message 中提取 @ 目标：
```python
async def get_at_target(arg: Message = CommandArg()) -> int | None:
    for seg in arg:
        if seg.type == "at" and seg.data.get("qq") != "all":
            return int(seg.data["qq"])
    return None

AtTarget = Annotated[int | None, Depends(get_at_target)]
```

注意：无法复用 ArgText，因为需要遍历 Message segments。

## Progress Tracking

**Overall Status:** In Progress - 40%

### Subtasks
| ID    | Description                   | Status      | Updated    | Notes                                   |
| ----- | ----------------------------- | ----------- | ---------- | --------------------------------------- |
| 11.1  | 创建 `bot/params.py` 参数依赖 | Complete    | 2026-02-04 | ArgText, Photo                          |
| 11.2  | 创建 `bot/checks.py` 检查模块 | Complete    | 2026-02-04 | blacklist_check, download_limit_check   |
| 11.3  | 重构 blacklist.py             | Not Started | -          | AtTarget 依赖, can_operate_target_check |
| 11.4  | 重构 download.py              | Complete    | 2026-02-04 | handlers=[] 模式，Photo 依赖            |
| 11.5  | 重构 query.py                 | Not Started | -          | 需讨论：复用 Photo 还是保持现状         |
| 11.6  | 重构 search.py                | Not Started | -          | 合并群聊/私聊，session 内部管理         |
| 11.7  | 重构 content_filter.py        | Not Started | -          | PhotoIds, Tags 依赖                     |
| 11.8  | 重构 group_control.py         | Not Started | -          | 保持 .got() 模式，简化其他命令          |
| 11.9  | 更新测试用例                  | Not Started | -          |                                         |
| 11.10 | 文档更新                      | Not Started | -          |                                         |

## Progress Log

### 2026-02-04 (初始设计)
- 任务创建，完成方案设计

### 2026-02-04 (download.py 重构完成)
- 重构 download.py：
  - 移除 `@matcher.handle()` 装饰器，改用 `handlers=[]`
  - 创建 `Photo` 依赖：合并 photo_id 验证 + API 获取
  - 允许在 Depends 中使用 `matcher.finish()`
  - 合并 `group_consume_and_notify` / `private_consume_and_notify` 为 `consume_and_notify`
  - 使用 `MessageEvent` 统一类型
- 更新 params.py：ArgText + Photo 依赖
- 更新 checks.py：移除 photo_id_check（已合并到 Photo 依赖）
- 41 tests passed ✅
- 总结最佳实践模式，准备应用到其他 handler