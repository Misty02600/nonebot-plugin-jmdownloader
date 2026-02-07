# [TASK014] - 下载失败不扣减额度

**Status:** Completed
**Added:** 2026-02-06
**Updated:** 2026-02-07

## Original Request
下载额度在真正下载/上传前就扣减，失败也会消耗额度。需要修复。

## Problem Analysis

当前流程：
1. `deduct_and_notify` 扣减额度 → 发送进度消息
2. `group_download_and_upload` 下载 PDF
3. 如果下载失败，额度已被扣除 ❌

代码位置：`bot/handlers/download.py`
- Line 130: `dm.users.decrease_limit(user_id, 1, dm.default_user_limit)`
- Line 152-154: `result = await jm.prepare_photo_file(photo)` 可能返回 `None`

## 设计方案

### 核心思路：利用 Handler 链 + finish 特性

```
download_and_upload 成功 → 继续执行 deduct_and_notify_success
download_and_upload 失败（finish）→ 后续 handler 不执行
```

### Handler 链设计

```python
handlers=[
    private_enabled_check,
    group_enabled_check,
    user_blacklist_check,
    download_limit_check,        # 检查是否有额度
    photo_restriction_check,
    send_progress_message,       # ✅ 发送进度消息（不扣额度）
    group_download_and_upload,   # 下载+上传，失败则 finish
    deduct_and_notify_success,   # ✅ 扣减额度 + 完成消息
]
```

### 具体改动

#### 1. 将 `deduct_and_notify` 拆分

**原函数：**
```python
async def deduct_and_notify(...):
    """扣除次数 & 发送进度消息"""
    remaining = dm.users.decrease_limit(...)  # ❌ 先扣
    dm.save_users()
    await matcher.send(build_progress_message(photo, remaining, jm))
```

**拆分为两个 handler：**

```python
async def send_progress_message(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
    jm: JmServiceDep,
):
    """发送进度消息（不扣额度）"""
    is_su = await SUPERUSER(bot, event)
    remaining = None if is_su else dm.users.get_limit(event.user_id, dm.default_user_limit)

    try:
        await matcher.send(build_progress_message(photo, remaining, jm))
    except ActionFailed:
        await matcher.send("本子信息可能被屏蔽，已开始下载")
    except NetworkError as e:
        logger.warning(f"{e}")


async def deduct_limit(
    bot: Bot,
    event: MessageEvent,
    dm: DataManagerDep,
):
    """扣减额度（下载成功后触发，静默）"""
    if await SUPERUSER(bot, event):
        return
    dm.users.decrease_limit(event.user_id, 1, dm.default_user_limit)
    dm.save_users()
```

#### 2. 修改 `build_progress_message`

```python
def build_progress_message(photo, remaining: int | None, jm) -> Message:
    """构建进度消息"""
    if remaining is None:
        limit_text = ""  # 超管不显示
    else:
        limit_text = f"你当前还有 {remaining} 次下载次数，"

    return Message(f"{limit_text}开始下载...\n...")
```

#### 3. 保持 `download_and_upload` 基本不变

只需确保：
- 成功时正常返回（不调用 finish）
- 失败时调用 `matcher.finish("错误信息")`

```python
async def group_download_and_upload(...):
    result = await jm.prepare_photo_file(photo)
    if result is None:
        await matcher.finish("下载失败")  # ❌ 终止，后续不执行

    file_path, ext = result
    try:
        await bot.call_api("upload_group_file", ...)
    except ActionFailed:
        await matcher.finish("发送文件失败")  # ❌ 终止，后续不执行
    # ✅ 成功则自然返回，继续执行 deduct_limit
```

### 用户体验

| 场景     | 消息                                   |
| -------- | -------------------------------------- |
| 进度     | "你当前还有 4 次下载次数，开始下载..." |
| 完成     | （无消息，静默扣减）                   |
| 下载失败 | "下载失败"（额度不扣）                 |
| 上传失败 | "发送文件失败"（额度不扣）             |

### 优势

- ✅ 无需新增辅助函数
- ✅ 符合 NoneBot handler 链设计模式
- ✅ 利用 `finish` 的特性自动控制流程
- ✅ 代码简洁，职责清晰

## Implementation Plan

- [ ] 1. 修改 `build_progress_message` 消息格式
- [ ] 2. 将 `deduct_and_notify` 改为 `send_progress_message`
- [ ] 3. 添加 `deduct_limit` handler
- [ ] 4. 更新 handlers 列表顺序
- [ ] 5. 运行测试确保功能正常

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description                 | Status   | Updated    | Notes            |
| ---- | --------------------------- | -------- | ---------- | ---------------- |
| 14.1 | 修改 build_progress_message | Complete | 2026-02-07 | 新消息格式       |
| 14.2 | 改名 send_progress_message  | Complete | 2026-02-07 | 不扣额度         |
| 14.3 | 添加 deduct_limit           | Complete | 2026-02-07 | 静默扣减         |
| 14.4 | 更新 handlers 列表          | Complete | 2026-02-07 | 顺序调整         |
| 14.5 | 运行测试                    | Complete | 2026-02-07 | 114 tests passed |

## Progress Log
### 2026-02-06
- Created task
- Analyzed current code flow and identified the issue

### 2026-02-07
- 完善实施方案
- 采用 handler 链设计，利用 finish 特性控制扣减时机
- 确定进度消息格式："你当前还有x次下载次数，开始下载..."
- 确定完成消息格式："下载完成，本周剩余次数：x"
