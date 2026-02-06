# [TASK014] - 下载失败不扣减额度

**Status:** Pending
**Added:** 2026-02-06
**Updated:** 2026-02-06

## Original Request
下载额度在真正下载/上传前就扣减，失败也会消耗额度。需要修复。

## Problem Analysis

当前流程：
1. `deduct_and_notify` 扣减额度 → 发送进度消息
2. `group_download_and_upload` 下载 PDF
3. 如果下载失败，额度已被扣除 ❌

代码位置：`bot/handlers/download.py`
- Line 112: `dm.users.decrease_limit(user_id, 1, dm.default_user_limit)`
- Line 134-136: `pdf_path = await jm.prepare_photo_pdf(photo)` 可能返回 `None`

## Thought Process

### 方案 A：下载成功后再扣减
- 将扣减逻辑移到下载和上传都成功之后
- 需要修改函数调用顺序
- 进度消息可能需要调整（因为此时不知道剩余次数）

### 方案 B：失败时回滚额度
- 下载失败或上传失败时，调用 `increase_limit` 回滚
- 需要在多个错误处理点添加回滚逻辑
- 代码更分散，容易遗漏

### 推荐方案：A
下载成功后再扣减更符合"按结果付费"的逻辑，代码也更简洁。

## Implementation Plan
- [ ] 1. 将 `deduct_and_notify` 拆分为 `send_progress_message` 和 `deduct_limit`
- [ ] 2. 将扣减逻辑移到下载和上传都成功之后
- [ ] 3. 更新进度消息（先不显示剩余次数，或显示"扣减后剩余 X 次"）
- [ ] 4. 测试各种失败场景确保额度不被错误扣减

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description            | Status      | Updated | Notes |
| --- | ---------------------- | ----------- | ------- | ----- |
| 1.1 | 拆分 deduct_and_notify | Not Started | -       | -     |
| 1.2 | 调整扣减时机           | Not Started | -       | -     |
| 1.3 | 更新进度消息           | Not Started | -       | -     |
| 1.4 | 测试失败场景           | Not Started | -       | -     |

## Progress Log
### 2026-02-06
- Created task
- Analyzed current code flow and identified the issue
