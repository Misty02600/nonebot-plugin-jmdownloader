# [TASK012] - 违规下载惩罚配置

**Status:** Pending
**Added:** 2026-02-05
**Updated:** 2026-02-05

## Original Request

添加一个配置参数，控制当用户发送了下载在黑名单的 id 或 tag 的本子时，是否采取禁言和拉黑措施。

## 背景分析

当前在 `download.py` 的 `photo_restriction_check` 函数中，当用户尝试下载被禁止的本子时，会：
1. 禁言用户 24 小时
2. 将用户加入群黑名单
3. 发送提示消息并终止

这个惩罚机制是硬编码的，没有配置选项。有些群可能只想阻止下载，不想惩罚用户。

## Implementation Plan

### 1. 添加配置项

在 `config.py` 中添加：

```python
class Config(BaseSettings):
    # ... 现有配置 ...

    jmcomic_punish_on_violation: bool = True
    """当用户尝试下载违规内容时是否惩罚（禁言+拉黑）"""
```

### 2. 修改 `photo_restriction_check`

```python
async def photo_restriction_check(...):
    if await SUPERUSER(bot, event):
        return

    photo_tags = [str(tag[0]) for tag in photo.tags] if photo.tags else []
    if data_manager.restriction.is_photo_restricted(photo.id, photo_tags):
        if plugin_config.jmcomic_punish_on_violation:
            # 惩罚：禁言 + 黑名单
            group_id = str(event.group_id)
            group = data_manager.get_group(group_id)
            try:
                await bot.set_group_ban(
                    group_id=event.group_id, user_id=event.user_id, duration=86400
                )
            except ActionFailed:
                pass
            group.blacklist.add(str(event.user_id))
            data_manager.save_group(group_id)
            await matcher.finish(
                MessageSegment.at(event.user_id)
                + "该本子（或其tag）被禁止下载！\n你已被加入本群jm黑名单"
            )
        else:
            # 只阻止，不惩罚
            await matcher.finish("该本子（或其tag）被禁止下载！")
```

### 3. 可选：细化配置

如果需要更细粒度的控制：

```python
jmcomic_violation_ban: bool = True      # 是否禁言
jmcomic_violation_blacklist: bool = True # 是否加黑名单
jmcomic_ban_duration: int = 86400       # 禁言时长（秒）
```

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID   | Description  | Status      | Updated | Notes |
| ---- | ------------ | ----------- | ------- | ----- |
| 12.1 | 添加配置项   | Not Started | -       |       |
| 12.2 | 修改检查函数 | Not Started | -       |       |
| 12.3 | 更新文档     | Not Started | -       |       |
| 12.4 | 测试验证     | Not Started | -       |       |

## Progress Log
### 2026-02-05
- 任务创建
