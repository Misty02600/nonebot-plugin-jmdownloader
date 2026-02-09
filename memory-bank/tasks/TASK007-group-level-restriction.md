# [TASK007] - 群级别内容屏蔽

**Status:** Pending
**Added:** 2026-02-01
**Updated:** 2026-02-07

## Original Request

取消全局的 tag 和本子屏蔽，改成每个群都有各自的屏蔽 ID 和 tag，可以由各群管理添加，初始值和现在一致。

---

## jmcomic 库内部实现调研

### 关键实体类（jm_entity.py）

```python
class JmPhotoDetail(DetailEntity, Downloadable):
    """章节详情（单个下载单元）"""
    photo_id: str           # 章节 ID
    name: str               # 章节标题
    _tags: str              # 原始标签字符串
    from_album: JmAlbumDetail | None  # 所属本子

    @property
    def tags(self) -> List[str]:
        """标签列表（优先使用 from_album.tags）"""
        if self.from_album is not None:
            return self.from_album.tags
        # 解析 _tags...

class JmAlbumDetail(DetailEntity, Downloadable):
    """本子详情"""
    album_id: str
    name: str
    tags: List[str]         # 标签列表（直接是 list）
    authors: List[str]      # 作者列表
    episode_list: list      # 章节列表
```

### 下载流程（jm_downloader.py）

```python
class JmDownloader:
    def __init__(self, option: JmOption):
        self.option = option
        self.client = option.build_jm_client()
        # 状态累积（需要每次清理）
        self.download_success_dict: Dict = {}
        self.download_failed_image: List = []
        self.download_failed_photo: List = []

    def download_by_photo_detail(self, photo: JmPhotoDetail):
        self.client.check_photo(photo)  # 补充 photo 信息（含 tags）
        self.before_photo(photo)
        # 下载图片...
        self.after_photo(photo)
```

### 搜索结果（jm_entity.py）

```python
class JmSearchPage(JmPageContent):
    """搜索结果页"""
    content: List[Tuple[str, Dict]]  # [(album_id, {name, tags, ...}), ...]

    def iter_id_title_tag(self) -> Generator[Tuple[str, str, List[str]]]:
        """返回 album_id, album_title, album_tags 的迭代器"""
        for aid, ainfo in self.content:
            ainfo.setdefault('tags', [])
            yield aid, ainfo['name'], ainfo['tags']
```

### 关键发现

| 属性                 | 来源                  | 说明                                         |
| -------------------- | --------------------- | -------------------------------------------- |
| `JmPhotoDetail.tags` | 动态属性              | 优先使用 `from_album.tags`，否则解析 `_tags` |
| `JmPhotoDetail.id`   | 属性                  | 返回 `photo_id`                              |
| `JmAlbumDetail.tags` | 实例字段              | 直接是 `List[str]`                           |
| 搜索结果 tags        | `iter_id_title_tag()` | 在结果中可直接获取                           |

### 对 TASK007 的影响

1. **tags 类型**：
   - `JmPhotoDetail.tags` 返回 `List[str]`
   - `JmAlbumDetail.tags` 是 `List[str]`
   - 我们的 `restricted_tags` 是 `set[str]`
   - ✅ 无需转换，直接用 `tag in restricted_tags` 判断

2. **ID 类型**：
   - `JmPhotoDetail.id` 返回 `str`
   - 我们的 `restricted_ids` 是 `set[str]`
   - ✅ 类型一致

3. **搜索结果过滤**：
   - 可以用 `iter_id_title_tag()` 获取 tags
   - 或直接用 `photo.tags`（当前实现）
   - ✅ 当前实现正确

---
## 当前架构分析

### 数据模型

```python
# 全局屏蔽配置（restriction.json）
class RestrictionConfig(msgspec.Struct):
    DEFAULT_RESTRICTED_TAGS: ClassVar[frozenset[str]]  # 默认屏蔽标签（类变量）
    DEFAULT_RESTRICTED_IDS: ClassVar[frozenset[str]]   # 默认屏蔽 ID（类变量）
    restricted_tags: set[str]   # 实例字段，可变
    restricted_ids: set[str]    # 实例字段，可变

    def ensure_defaults()       # 首次加载时从 ClassVar 复制到实例
    def is_photo_restricted()   # 检查是否受限

# 群配置（groups/{group_id}.json）
class GroupConfig(msgspec.Struct):
    folder_id: str | None
    enabled: bool | msgspec.UnsetType
    blacklist: set[str]         # 用户黑名单
```

### 使用位置

| 文件            | 位置 | 用途                                          |
| --------------- | ---- | --------------------------------------------- |
| `download.py`   | L79  | `dm.restriction.is_photo_restricted()`        |
| `search.py`     | L50  | `dm.restriction.restricted_tags.isdisjoint()` |
| `ban_id_tag.py` | L23  | `dm.restriction.restricted_ids.add()`         |
| `ban_id_tag.py` | L36  | `dm.restriction.restricted_tags.add()`        |

### ⚠️ 关键问题：私聊目前无屏蔽检查

**现状**：
- `photo_restriction_check` 只接收 `GroupMessageEvent`（download.py L67-69）
- 私聊时该 handler 不触发，**私聊无任何屏蔽保护！**
- 这是一个独立于 TASK007 的 bug，需要一并修复

---

## 推荐方案：全局 + 群级别完全覆盖

### 核心设计

```
┌─────────────────────────────────────────────────┐
│              全局配置 (restriction.json)         │
│  RestrictionConfig                              │
│  - DEFAULT_RESTRICTED_TAGS (ClassVar)           │
│  - DEFAULT_RESTRICTED_IDS (ClassVar)            │
│  - restricted_tags: set[str]                    │
│  - restricted_ids: set[str]                     │
└─────────────────────────────────────────────────┘
           ↓ 私聊直接使用
           ↓ 群聊作为 fallback
┌─────────────────────────────────────────────────┐
│              群级别配置 (groups/{id}.json)       │
│  GroupConfig.restricted_tags: set[str] | None   │
│  GroupConfig.restricted_ids: set[str] | None    │
│  - None: 使用全局配置                           │
│  - set(): 自定义（可为空，表示不屏蔽任何）        │
└─────────────────────────────────────────────────┘
```

### 数据模型变更

```python
class GroupConfig(msgspec.Struct, omit_defaults=True):
    folder_id: str | None = None
    enabled: bool | msgspec.UnsetType = msgspec.UNSET
    blacklist: set[str] = msgspec.field(default_factory=set)
    # 新增：None 表示使用全局默认
    restricted_tags: set[str] | None = None
    restricted_ids: set[str] | None = None

    # ========== 只读访问（仅用于检查） ==========

    def get_effective_tags(self, fallback: set[str]) -> set[str]:
        """获取生效的屏蔽标签（仅用于检查）

        ⚠️ 返回值是引用，不要直接 .add()/.remove()！
        使用下方的 add_*/remove_* 方法进行修改。
        """
        return self.restricted_tags if self.restricted_tags is not None else fallback

    def get_effective_ids(self, fallback: set[str]) -> set[str]:
        """获取生效的屏蔽 ID（仅用于检查）"""
        return self.restricted_ids if self.restricted_ids is not None else fallback

    def is_photo_restricted(
        self,
        photo_id: str,
        photo_tags: list[str] | None,
        fallback_ids: set[str],
        fallback_tags: set[str],
    ) -> bool:
        """检查 photo 是否受限"""
        ids = self.get_effective_ids(fallback_ids)
        tags = self.get_effective_tags(fallback_tags)

        if str(photo_id) in ids:
            return True
        if photo_tags:
            for tag in photo_tags:
                if tag in tags:
                    return True
        return False

    # ========== 修改操作（自动初始化，避免污染全局） ==========

    def add_restricted_tag(self, tag: str, default_tags: set[str]) -> None:
        """添加屏蔽标签（首次添加时从全局复制）"""
        if self.restricted_tags is None:
            self.restricted_tags = set(default_tags)  # 复制一份
        self.restricted_tags.add(tag)

    def remove_restricted_tag(self, tag: str, default_tags: set[str]) -> bool:
        """删除屏蔽标签"""
        if self.restricted_tags is None:
            self.restricted_tags = set(default_tags)
        if tag in self.restricted_tags:
            self.restricted_tags.discard(tag)
            return True
        return False

    def add_restricted_id(self, photo_id: str, default_ids: set[str]) -> None:
        """添加屏蔽 ID"""
        if self.restricted_ids is None:
            self.restricted_ids = set(default_ids)
        self.restricted_ids.add(photo_id)

    def remove_restricted_id(self, photo_id: str, default_ids: set[str]) -> bool:
        """删除屏蔽 ID"""
        if self.restricted_ids is None:
            self.restricted_ids = set(default_ids)
        if photo_id in self.restricted_ids:
            self.restricted_ids.discard(photo_id)
            return True
        return False

    def reset_restrictions_to_default(self) -> None:
        """重置为使用全局默认"""
        self.restricted_tags = None
        self.restricted_ids = None
```

### ⚠️ 可变引用风险

**问题场景**：
```python
# 危险！！！
group.restricted_tags = None  # 使用全局
tags = group.get_effective_tags(dm.restriction.restricted_tags)
tags.add("new_tag")  # ❌ 直接修改了全局配置！
```

**解决方案**：
1. `get_effective_*()` 只用于检查，命名强调 "effective"
2. `add_*/remove_*` 方法自动处理初始化，首次操作时复制全局
3. 代码审查时禁止直接操作 getter 返回值

---

## Handler 改动

### download.py - 拆分屏蔽检查

**原代码**（仅群聊触发）：
```python
async def photo_restriction_check(
    bot: Bot,
    event: GroupMessageEvent,  # ❌ 私聊不触发
    ...
):
    if not dm.restriction.is_photo_restricted(photo.id, photo_tags):
        return
    # 惩罚逻辑...
```

**新代码**（拆分为两个 handler）：
```python
async def group_restriction_check(
    bot: Bot,
    event: GroupMessageEvent,  # 仅群聊触发
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
):
    """群聊内容限制检查（使用群配置或全局 fallback）"""
    group = dm.get_group(event.group_id)
    if not group.is_photo_restricted(
        photo.id,
        list(photo.tags or []),
        dm.restriction.restricted_ids,
        dm.restriction.restricted_tags,
    ):
        return
    # ... 惩罚逻辑（禁言+拉黑）...


async def private_restriction_check(
    event: PrivateMessageEvent,  # 仅私聊触发
    matcher: Matcher,
    photo: Photo,
    dm: DataManagerDep,
):
    """私聊内容限制检查（使用全局配置，无惩罚）"""
    if not dm.restriction.is_photo_restricted(photo.id, list(photo.tags or [])):
        return
    # 私聊只阻止，不惩罚
    await matcher.finish("该本子（或其tag）被禁止下载！")
```

**Handler 链更新**：
```python
handlers=[
    private_enabled_check,
    group_enabled_check,
    user_blacklist_check,
    download_limit_check,
    group_restriction_check,    # 群聊屏蔽（群配置）
    private_restriction_check,  # 私聊屏蔽（全局配置）✅ 新增
    send_progress_message,
    group_download_and_upload,
    private_download_and_upload,
    deduct_limit,
]
```

### search.py - 区分群聊/私聊

**原代码**：
```python
if not dm.restriction.restricted_tags.isdisjoint(photo.tags):
    # 显示屏蔽消息
```

**新代码**：
```python
def get_restricted_tags_for_event(event: MessageEvent, dm: DataManagerDep) -> set[str]:
    """根据事件类型获取生效的屏蔽标签"""
    if isinstance(event, GroupMessageEvent):
        group = dm.get_group(event.group_id)
        return group.get_effective_tags(dm.restriction.restricted_tags)
    else:
        return dm.restriction.restricted_tags

# 使用
restricted_tags = get_restricted_tags_for_event(event, dm)
if not restricted_tags.isdisjoint(photo.tags):
    # 显示屏蔽消息
```

### ban_id_tag.py - 改为操作群配置

**原代码**：
```python
async def forbid_ids_handler(...):
    dm.restriction.restricted_ids.add(jm_id)  # ❌ 操作全局
    dm.save_restriction()
```

**新代码**：
```python
async def forbid_ids_handler(
    event: GroupMessageEvent,  # 仅群聊触发
    matcher: Matcher,
    text: ArgText,
    dm: DataManagerDep,
):
    """禁用指定的 jm 号（群级别）"""
    group = dm.get_group(event.group_id)

    for jm_id in jm_ids:
        group.add_restricted_id(jm_id, dm.restriction.restricted_ids)
    dm.save_group(event.group_id)

    await matcher.finish("以下jm号已加入本群禁止下载列表：\n" + " ".join(jm_ids))
```

**权限变更**：
- 原：`permission=SUPERUSER`
- 新：`permission=SUPERUSER | GROUP_ADMIN | GROUP_OWNER`（群管理员可操作本群）

---

## 私聊行为设计

| 场景         | 行为                     |
| ------------ | ------------------------ |
| 私聊下载     | 使用全局屏蔽检查         |
| 私聊搜索     | 使用全局屏蔽过滤结果     |
| 私聊添加屏蔽 | **不支持**（无群上下文） |
| 私聊删除屏蔽 | **不支持**               |

> 全局配置（restriction.json）需手动编辑，或通过其他管理方式操作。

---

## Implementation Plan

- [ ] 1. **修改 GroupConfig**
  - [ ] 1.1 添加 `restricted_tags: set[str] | None = None`
  - [ ] 1.2 添加 `restricted_ids: set[str] | None = None`
  - [ ] 1.3 添加 `get_effective_tags/ids()` 只读方法
  - [ ] 1.4 添加 `add_*/remove_*` 修改方法（自动初始化）
  - [ ] 1.5 添加 `is_photo_restricted()` 方法
  - [ ] 1.6 添加 `reset_restrictions_to_default()` 方法

- [ ] 2. **修改 download.py**
  - [ ] 2.1 拆分 `photo_restriction_check` 为 `group_restriction_check`
  - [ ] 2.2 新增 `private_restriction_check`（修复私聊无检查 bug）
  - [ ] 2.3 更新 handler 链

- [ ] 3. **修改 search.py**
  - [ ] 3.1 添加 `get_restricted_tags_for_event()` 辅助函数
  - [ ] 3.2 修改 `build_search_result_messages()` 使用群配置

- [ ] 4. **修改 ban_id_tag.py**
  - [ ] 4.1 改为操作 `GroupConfig.add_restricted_*`
  - [ ] 4.2 更新权限：允许群管理员操作
  - [ ] 4.3 仅群聊可用（私聊不支持）

- [ ] 5. **更新测试用例**

---

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description            | Status      | Updated | Notes                  |
| --- | ---------------------- | ----------- | ------- | ---------------------- |
| 7.1 | 修改 GroupConfig       | Not Started | -       | 添加 restricted_* 字段 |
| 7.2 | 拆分 restriction_check | Not Started | -       | group + private 两个   |
| 7.3 | 修复私聊无检查 bug     | Not Started | -       | ⚠️ 独立问题，一并修复   |
| 7.4 | 修改 search.py         | Not Started | -       | 区分群聊/私聊          |
| 7.5 | 修改 ban_id_tag.py     | Not Started | -       | 群级别 + 权限变更      |
| 7.6 | 更新测试               | Not Started | -       | -                      |

---

## Progress Log

### 2026-02-01
- 创建任务文件
- 分析当前架构

### 2026-02-07
- 详细分析当前实现代码
- 发现私聊无屏蔽检查 bug
- 设计可变引用风险解决方案（add_*/remove_* 自动初始化）
- 细化 handler 拆分方案
- 更新 Implementation Plan
