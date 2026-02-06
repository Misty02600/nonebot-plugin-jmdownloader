# [TASK007] - 群级别内容屏蔽

**Status:** Pending
**Added:** 2026-02-01
**Updated:** 2026-02-01

## Original Request

取消全局的 tag 和本子屏蔽，改成每个群都有各自的屏蔽 ID 和 tag，可以由各群管理添加，初始值和现在一致。

## Thought Process

### 当前状态

1. **RestrictionConfig** 是全局配置，存储在 `restriction.json`
   - `restricted_tags`: 全局屏蔽标签
   - `restricted_ids`: 全局屏蔽本子 ID
   - `forbidden_albums`: 全局禁止下载列表

2. **使用位置**:
   - `search.py`: 搜索结果中检查 `data_manager.restriction.restricted_tags`
   - `content_filter.py`: 添加屏蔽标签
   - `download_service.py`: 下载时检查限制

### 设计方案

1. **将 RestrictionConfig 字段移入 GroupConfig**:
   ```python
   class GroupConfig(msgspec.Struct):
       folder_id: str | None = None
       enabled: bool | msgspec.UnsetType = msgspec.UNSET
       blacklist: set[str] = msgspec.field(default_factory=set)
       # 新增
       restricted_tags: set[str] = msgspec.field(default_factory=set)
       restricted_ids: set[str] = msgspec.field(default_factory=set)
   ```

2. **初始值处理**:
   - 新群首次使用时，自动填充 `DEFAULT_RESTRICTED_TAGS` 和 `DEFAULT_RESTRICTED_IDS`
   - 保留默认值常量在 `GroupConfig` 中

3. **迁移策略**:
   - 读取旧的 `restriction.json`
   - 将全局配置复制到所有现有群配置中
   - 删除 `restriction.json`

4. **命令更新**:
   - 屏蔽命令改为群级别操作
   - 只有群管理员可以操作本群屏蔽列表
   - 超级用户可以操作任意群

5. **私聊行为**:
   - 私聊时不做屏蔽检查（无群上下文）
   - 或使用一个默认的屏蔽列表

## Implementation Plan

- [ ] 1. 修改 `core/data_models.py`:
  - 移除 `RestrictionConfig` 类
  - 将 `restricted_tags` 和 `restricted_ids` 字段添加到 `GroupConfig`
  - 添加 `ensure_restriction_defaults()` 方法

- [ ] 2. 修改 `infra/data_manager.py`:
  - 移除 `restriction` 属性和相关加载/保存逻辑
  - 修改 `get_group()` 方法，在获取时自动填充默认屏蔽值

- [ ] 3. 添加数据迁移:
  - 在 `migration.py` 中添加 `restriction.json` → GroupConfig 迁移逻辑

- [ ] 4. 修改 `bot/handlers/search.py`:
  - 从 `data_manager.restriction` 改为 `data_manager.get_group(group_id).restricted_tags`

- [ ] 5. 修改 `bot/handlers/content_filter.py`:
  - 屏蔽命令改为操作群配置
  - 添加权限检查（群管理员 / 超级用户）

- [ ] 6. 修改 `bot/services/download_service.py`:
  - 下载时检查群级别屏蔽（如果有 group_id）

- [ ] 7. 处理私聊场景:
  - 决定私聊时的屏蔽策略

- [ ] 8. 更新测试用例

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description              | Status      | Updated | Notes |
| --- | ------------------------ | ----------- | ------- | ----- |
| 7.1 | 修改 data_models.py      | Not Started |         |       |
| 7.2 | 修改 data_manager.py     | Not Started |         |       |
| 7.3 | 添加数据迁移             | Not Started |         |       |
| 7.4 | 修改 search.py           | Not Started |         |       |
| 7.5 | 修改 content_filter.py   | Not Started |         |       |
| 7.6 | 修改 download_service.py | Not Started |         |       |
| 7.7 | 处理私聊场景             | Not Started |         |       |
| 7.8 | 更新测试                 | Not Started |         |       |

## Progress Log

### 2026-02-01

- 创建任务文件
- 分析当前架构
- 设计实施方案
