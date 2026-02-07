# [TASK012] - 违规下载惩罚配置

**Status:** Completed
**Added:** 2026-02-05
**Updated:** 2026-02-07

## Original Request

添加一个配置参数，控制当用户发送了下载在黑名单的 id 或 tag 的本子时，是否采取禁言和拉黑措施。

**重要补充**：无论配置如何，都应该避免对群管理员和群主的惩罚（禁言+拉黑）。

## 背景分析

当前在 `download.py` 的 `photo_restriction_check` 函数中，当用户尝试下载被禁止的本子时，会：
1. 禁言用户 24 小时
2. 将用户加入群黑名单
3. 发送提示消息并终止

**问题**：
1. 惩罚机制是硬编码的，没有配置选项。有些群可能只想阻止下载，不想惩罚用户。
2. 没有对群管理员/群主的豁免机制，可能误伤管理人员。

## Implementation Plan

### 1. 添加配置项

在 `config.py` 中添加：

```python
class Config(BaseSettings):
    # ... 现有配置 ...

    jmcomic_punish_on_violation: bool = True
    """当用户尝试下载违规内容时是否惩罚（禁言+拉黑）"""
```

### 2. 使用内置权限检查器

NoneBot OneBot V11 适配器提供了现成的权限检查器，无需自定义函数：

```python
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER

# 合并权限检查器
GROUP_ADMIN_OR_OWNER = GROUP_ADMIN | GROUP_OWNER

# 使用方式
is_admin_or_owner = await GROUP_ADMIN_OR_OWNER(bot, event)
```

### 3. 修改 `photo_restriction_check`

```python
from nonebot.adapters.onebot.v11.permission import GROUP_ADMIN, GROUP_OWNER
from nonebot.permission import SUPERUSER

async def photo_restriction_check(...):
    photo_tags = [str(tag[0]) for tag in photo.tags] if photo.tags else []
    if not dm.restriction.is_photo_restricted(photo.id, photo_tags):
        return  # 未被限制，允许下载

    # 检查是否应该惩罚
    should_punish = plugin_config.jmcomic_punish_on_violation

    # 超管/管理员/群主免惩罚（无论配置如何）
    if should_punish:
        is_privileged = await SUPERUSER(bot, event) or await (GROUP_ADMIN | GROUP_OWNER)(bot, event)
        if is_privileged:
            should_punish = False

    if should_punish:
        # 惩罚：禁言 + 黑名单
        group_id = str(event.group_id)
        group = dm.get_group(group_id)
        try:
            await bot.set_group_ban(
                group_id=event.group_id, user_id=event.user_id, duration=86400
            )
        except ActionFailed:
            pass
        group.blacklist.add(str(event.user_id))
        dm.save_group(group_id)
        await matcher.finish(
            MessageSegment.at(event.user_id)
            + "该本子（或其tag）被禁止下载！\n你已被加入本群jm黑名单"
        )
    else:
        # 只阻止，不惩罚（超管/管理员/群主 或 配置关闭惩罚）
        await matcher.finish("该本子（或其tag）被禁止下载！")
```

### 4. 可选：细化配置

如果需要更细粒度的控制：

```python
jmcomic_violation_ban: bool = True      # 是否禁言
jmcomic_violation_blacklist: bool = True # 是否加黑名单
jmcomic_ban_duration: int = 86400       # 禁言时长（秒）
```

## 关键设计决策

1. **所有用户都受内容限制**：包括超管、管理员、群主，违规内容一律不允许下载
2. **特权用户免惩罚**：超管、管理员、群主不会被禁言或加黑名单（无论配置如何）
3. **普通用户可配置惩罚**：通过 `jmcomic_punish_on_violation` 控制是否惩罚普通用户

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description  | Status   | Updated    | Notes                           |
| ---- | ------------ | -------- | ---------- | ------------------------------- |
| 12.1 | 添加配置项   | Complete | 2026-02-07 | `jmcomic_punish_on_violation`   |
| 12.2 | 修改检查函数 | Complete | 2026-02-07 | 集成特权用户豁免逻辑 + 配置检查 |
| 12.3 | 更新文档     | Complete | 2026-02-07 | README 已更新                   |
| 12.4 | 测试验证     | Complete | 2026-02-07 | 114 tests passed                |

## Progress Log
### 2026-02-05
- 任务创建

### 2026-02-06
- 更新需求：添加管理员/群主免惩罚机制
- 更新实现方案：使用 NoneBot 内置 `GROUP_ADMIN | GROUP_OWNER` 权限检查器
- 移除自定义 `is_group_admin_or_owner` 函数（使用框架内置功能更简洁）

### 2026-02-07
- **重大设计变更**：超管也受内容限制，不再跳过检查
- 统一特权用户处理：超管、管理员、群主都会被阻止下载违规内容，但免于惩罚
- 实现完成：
  - `config.py`: 添加 `jmcomic_punish_on_violation` 配置项
  - `download.py`: 重构 `photo_restriction_check` 函数
  - `README.md`: 更新配置文档和使用说明
- **任务标记为完成** - 114 tests passed
