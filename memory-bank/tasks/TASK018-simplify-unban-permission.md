# [TASK018] - 简化解除拉黑权限

**Status:** Abandoned
**Added:** 2026-02-06
**Updated:** 2026-02-07

## Original Request

解除拉黑的权限可以交给任意群主和管理，移除当前的繁琐逻辑。

## Thought Process

### 现状分析

当前 `blacklist.py` 中 `jm解除拉黑` 命令使用了 `can_operate_check` handler：

```python
async def can_operate_check(...):
    """检查操作权限：不能操作比自己权限高的用户"""
    # 获取目标用户的角色 (owner/admin/member)
    # 比较操作者和目标用户的角色优先级
    # 如果操作者权限不够，则 finish
```

这个逻辑对于**拉黑**操作是合理的（防止管理员拉黑群主），但对于**解除拉黑**操作来说过于繁琐：

- 解除拉黑是帮助用户恢复正常使用
- 群主/管理员应该可以无条件解除任何人的拉黑状态
- 不需要判断目标用户的角色

### 解决方案

1. `jm解除拉黑` 移除 `can_operate_check` handler
2. `jm拉黑` 保留 `can_operate_check` handler（防止拉黑高权限用户）
3. 两个命令都保留 `permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER`

### 代码改动

```python
# 改动前
jm_unban_user = on_command(
    "jm解除拉黑",
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    handlers=[can_operate_check, unban_user_handler],  # 有权限检查
)

# 改动后
jm_unban_user = on_command(
    "jm解除拉黑",
    permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER,
    handlers=[unban_user_handler],  # 移除权限检查
)
```

## Implementation Plan

1. **修改 blacklist.py**
   - `jm_unban_user` 的 handlers 列表中移除 `can_operate_check`

2. **验证**
   - 确认拉黑逻辑不变（保留权限检查）
   - 确认解除拉黑逻辑简化（移除权限检查）

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID   | Description                     | Status      | Updated    | Notes |
| ---- | ------------------------------- | ----------- | ---------- | ----- |
| 18.1 | 修改 jm_unban_user 移除权限检查 | Not Started | 2026-02-06 |       |
| 18.2 | 验证功能                        | Not Started | 2026-02-06 |       |

## Progress Log

### 2026-02-06
- 任务创建
- 分析了问题原因和解决方案

### 2026-02-07
- **任务废弃**
- 原因：TASK012 已实现群主/管理员免惩罚机制，不会再被自动拉黑
- 手动拉黑已有权限检查（`can_operate_check`），管理员无法拉黑群主
- 此任务不再需要
