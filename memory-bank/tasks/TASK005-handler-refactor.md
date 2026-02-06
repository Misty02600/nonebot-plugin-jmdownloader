# [TASK005] - 重构指令处理函数（按事件类型分离）

**Status:** Completed
**Added:** 2026-01-29
**Updated:** 2026-01-31

## Original Request

重构所有指令，对于以前一个函数同时接受私聊和群聊的，现在全部分别拆成私聊和群聊两个函数。`dependencies.py` 的依赖场景也要定义得更为清晰。

## Phase 1: Matcher 分离 ✅

使用 `permission=GROUP/PRIVATE` 创建独立 matcher，群聊 matcher 应用 `rule=GroupRule`。

| 原名称         | 群聊 Matcher         | 私聊 Matcher           |
| -------------- | -------------------- | ---------------------- |
| `jm_download`  | `jm_download_group`  | `jm_download_private`  |
| `jm_query`     | `jm_query_group`     | `jm_query_private`     |
| `jm_search`    | `jm_search_group`    | `jm_search_private`    |
| `jm_next_page` | `jm_next_page_group` | `jm_next_page_private` |

## Phase 2: 公共代码抽取（进行中）

### jm_download 代码分析

对比群聊和私聊 handler，差异如下：

| 阶段                    | 群聊专有                        | 私聊专有              | 公共                      |
| ----------------------- | ------------------------------- | --------------------- | ------------------------- |
| **参数验证**            |                                 |                       | `photo_id.isdigit()`      |
| **次数限制检查**        | `@at(user_id)`                  | 无 at                 | 检查逻辑相同              |
| **获取 photo**          |                                 |                       | 完全相同                  |
| **禁止检查**            | 禁言 + 加黑名单                 | 简单拒绝              | 检查条件相同              |
| **扣除次数 & 发送提示** |                                 |                       | 逻辑相同，仅 matcher 不同 |
| **下载 PDF**            |                                 |                       | 完全相同                  |
| **MD5 修改**            |                                 |                       | 完全相同                  |
| **上传文件**            | `upload_group_file` + folder_id | `upload_private_file` | 不同                      |

### 抽取方案

将流程拆分为可复用的独立函数：

```python
# 1. 获取并验证 photo
async def fetch_photo(photo_id: str) -> JmPhotoDetail:
    """获取 photo 信息，失败时抛出异常"""
    try:
        photo = await get_photo_info_async(client, photo_id)
    except MissingAlbumPhotoException:
        raise DownloadError("未查找到本子")
    if photo is None:
        raise DownloadError("查询时发生错误")
    return photo

# 2. 检查是否被禁止
def is_photo_restricted(photo: JmPhotoDetail) -> bool:
    """检查 photo 是否在限制列表中"""
    return (
        photo.id in data_manager.global_config.restricted_ids
        or not data_manager.global_config.restricted_tags.isdisjoint(photo.tags)
    )

# 3. 扣除次数并构建消息
def deduct_and_build_message(user_id: int, photo: JmPhotoDetail, is_superuser: bool) -> Message:
    """扣除下载次数并构建开始下载消息"""
    message = Message()
    message += f"jm{photo.id} | {photo.title}\n"
    message += f"🎨 作者: {photo.author}\n"
    message += "🔖 标签: " + " ".join(f"#{tag}" for tag in photo.tags) + "\n"

    if not is_superuser:
        data_manager.users.decrease_limit(str(user_id), 1, data_manager.default_user_limit)
        data_manager.save_users()
        user_limit_new = data_manager.users.get_limit(str(user_id), data_manager.default_user_limit)
        message += f"开始下载...\n你本周还有{user_limit_new}次下载次数！"
    else:
        message += "开始下载..."

    return message

# 4. 准备 PDF 文件（下载 + MD5 修改）
async def prepare_pdf(photo: JmPhotoDetail) -> str:
    """下载并准备 PDF 文件，返回文件路径"""
    pdf_path = f"{cache_dir}/{photo.id}.pdf"

    if not os.path.exists(pdf_path):
        if not await download_photo_async(downloader, photo):
            raise DownloadError("下载失败")

    if plugin_config.jmcomic_modify_real_md5:
        random_suffix = hashlib.md5(str(time.time() + random.random()).encode()).hexdigest()[:8]
        renamed_pdf_path = f"{cache_dir}/{photo.id}_{random_suffix}.pdf"
        modified = await asyncio.to_thread(modify_pdf_md5, pdf_path, renamed_pdf_path)
        if modified:
            pdf_path = renamed_pdf_path

    return pdf_path
```

### 重构后的 handler 结构

```python
@jm_download_group.handle()
async def handle_group_download(bot, event, group, arg):
    photo_id = arg.extract_plain_text().strip()
    user_id = event.user_id
    is_superuser = str(user_id) in bot.config.superusers

    # 验证参数
    if not photo_id.isdigit():
        await jm_download_group.finish("请输入要下载的jm号")

    # 检查次数限制
    if not is_superuser and not check_user_limit(user_id):
        await jm_download_group.finish(at(user_id) + "你的下载次数已经用完了！")

    # 获取 photo
    photo = await fetch_photo(photo_id)  # 可能抛出 DownloadError

    # 检查禁止（群聊特有：禁言 + 加黑名单）
    if is_photo_restricted(photo):
        if not is_superuser:
            await punish_user(bot, event, group, user_id)  # 群聊专有
        await jm_download_group.finish("该本子（或其tag）被禁止下载！")

    # 扣除次数并发送消息
    message = deduct_and_build_message(user_id, photo, is_superuser)
    await safe_send(jm_download_group, message)

    # 准备 PDF
    pdf_path = await prepare_pdf(photo)  # 可能抛出 DownloadError

    # 上传文件（群聊专有逻辑）
    await upload_group_file(bot, event, group, photo, pdf_path)
```

### 待抽取的公共函数

| 函数名                          | 职责               | 返回值                   |
| ------------------------------- | ------------------ | ------------------------ |
| `fetch_photo(photo_id)`         | 获取 photo 信息    | `JmPhotoDetail` 或抛异常 |
| `is_photo_restricted(photo)`    | 检查是否在限制列表 | `bool`                   |
| `check_user_limit(user_id)`     | 检查用户下载次数   | `bool`                   |
| `deduct_and_build_message(...)` | 扣除次数并构建消息 | `Message`                |
| `prepare_pdf(photo)`            | 下载并准备 PDF     | `str` (路径)             |

### 群聊专有函数

| 函数名                                                  | 职责            |
| ------------------------------------------------------- | --------------- |
| `punish_restricted_user(bot, event, group, user_id)`    | 禁言 + 加黑名单 |
| `upload_group_file(bot, event, group, photo, pdf_path)` | 上传到群文件    |

### 私聊专有函数

| 函数名                                             | 职责         |
| -------------------------------------------------- | ------------ |
| `upload_private_file(bot, event, photo, pdf_path)` | 上传私聊文件 |

## Phase 3: 接口层/服务层分离（新增）

### 设计目标

`handlers.py` 只作为接口层，定义 matcher 和参数提取，具体业务实现放到 `services/` 目录。

### 目标架构

```
bot/
├── handlers.py             # 接口层：定义 matcher，处理路由和参数
├── dependencies.py         # 依赖注入：只注入 NoneBot 框架相关的东西
├── messaging.py            # 消息工具
├── permissions.py          # 权限检查
│
└── services/               # 🆕 应用服务层：具体业务实现
    ├── __init__.py
    ├── download_service.py # 下载相关流程
    ├── query_service.py    # 查询相关流程
    └── search_service.py   # 搜索相关流程
```

### 架构原则

1. **依赖注入的范围**
   - `dependencies.py` 只注入 NoneBot 框架提供的东西（Bot、Event、Rule 等）
   - **移除 `GroupConfigDep`**：GroupConfig 应由 service 通过 `data_manager.get_group()` 获取
   - 保留：`client`, `downloader`, `data_manager`, `plugin_cache_dir`, `GroupRule`

2. **infra 层只提供类，不实例化**
   - `JMService`, `DataManager` 等都是类定义
   - 实例化在 `bot/dependencies.py` 或应用入口完成

3. **职责分离**
   | 层             | 位置                | 职责                                       |
   | -------------- | ------------------- | ------------------------------------------ |
   | **接口层**     | `bot/handlers.py`   | Matcher 定义、参数提取、调用服务、返回消息 |
   | **应用服务层** | `bot/services/*.py` | 业务流程编排、跨模块协调                   |
   | **基础设施层** | `infra/*.py`        | 外部系统交互（JM API、文件系统）类定义     |
   | **领域层**     | `core/*.py`         | 纯业务规则、数据模型                       |

### handlers.py 重构示例

```python
# handlers.py - 瘦接口层
@jm_download_group.handle()
async def handle_group_download(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    photo_id = arg.extract_plain_text().strip()
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    is_superuser = user_id in bot.config.superusers

    # 调用服务层处理业务逻辑
    result = await download_service.process_download(
        photo_id=photo_id,
        user_id=user_id,
        group_id=group_id,
        is_superuser=is_superuser,
    )

    # 根据结果响应
    if result.error:
        await jm_download_group.finish(result.error_message)

    await jm_download_group.send(result.progress_message)

    # 群聊专有：上传文件
    await bot.upload_group_file(
        group_id=event.group_id,
        file=result.pdf_path,
        name=result.filename,
        folder=result.folder_id,
    )
```

### services/download_service.py 结构

```python
@dataclass
class DownloadResult:
    success: bool
    pdf_path: str | None = None
    filename: str | None = None
    folder_id: str | None = None
    progress_message: str | None = None
    error_message: str | None = None
    should_punish: bool = False

class DownloadService:
    def __init__(self, jm_service: JMService, data_manager: DataManager, cache_dir: Path):
        self._jm = jm_service
        self._data = data_manager
        self._cache = cache_dir

    async def process_download(
        self,
        photo_id: str,
        user_id: str,
        group_id: str | None = None,
        is_superuser: bool = False,
    ) -> DownloadResult:
        # 1. 验证参数
        if not photo_id.isdigit():
            return DownloadResult(success=False, error_message="请输入要下载的jm号")

        # 2. 获取群配置（如果是群聊）
        group_config = self._data.get_group(group_id) if group_id else None

        # 3. 检查次数限制
        if not is_superuser and not self._check_limit(user_id):
            return DownloadResult(success=False, error_message="下载次数已用完")

        # 4. 获取 photo
        photo = await self._jm.get_photo(photo_id)
        if photo is None:
            return DownloadResult(success=False, error_message="查询时发生错误")

        # 5. 检查限制
        if self._is_restricted(photo):
            return DownloadResult(
                success=False,
                error_message="该本子被禁止下载",
                should_punish=not is_superuser,
            )

        # 6. 扣除次数
        message = self._deduct_and_build_message(user_id, photo, is_superuser)

        # 7. 下载 PDF
        pdf_path = await self._prepare_pdf(photo)

        return DownloadResult(
            success=True,
            pdf_path=pdf_path,
            filename=f"{photo.id}.pdf",
            folder_id=group_config.folder_id if group_config else None,
            progress_message=message,
        )
```

### 待完成任务

| ID   | Description                 | Status      |
| ---- | --------------------------- | ----------- |
| 5.8  | 创建 `bot/services/` 目录   | Not Started |
| 5.9  | 实现 `DownloadService`      | Not Started |
| 5.10 | 实现 `QueryService`         | Not Started |
| 5.11 | 实现 `SearchService`        | Not Started |
| 5.12 | 重构 `dependencies.py`      | Not Started |
| 5.13 | 重构 `handlers.py` 使用服务 | Not Started |

## Progress Tracking

**Overall Status:** Complete - 100% ✅

### Subtasks
| ID   | Description               | Status   | Updated    | Notes                           |
| ---- | ------------------------- | -------- | ---------- | ------------------------------- |
| 5.1  | Matcher 分离              | Complete | 2026-01-29 | 使用 permission 分流            |
| 5.2  | Rule 应用                 | Complete | 2026-01-29 | 群聊使用 GroupRule              |
| 5.3  | jm_download 公共代码抽取  | Complete | 2026-01-30 | DownloadService                 |
| 5.4  | jm_query 公共代码抽取     | Complete | 2026-01-30 | QueryService                    |
| 5.5  | jm_search 公共代码抽取    | Complete | 2026-01-30 | SearchService                   |
| 5.6  | jm_next_page 公共代码抽取 | Complete | 2026-01-30 | 合并到 SearchService            |
| 5.7  | 测试验证                  | Complete | 2026-01-31 | 41 tests passed                 |
| 5.8  | 创建 services 目录        | Complete | 2026-01-30 | bot/services/                   |
| 5.9  | 实现 DownloadService      | Complete | 2026-01-30 | 方案 B（返回结果）              |
| 5.10 | 重构 dependencies.py      | Complete | 2026-01-30 | 移除 GroupConfigDep             |
| 5.11 | 重构 handlers.py          | Complete | 2026-01-30 | 拆分为 bot/handlers/ 模块       |
| 5.12 | JMService 简化            | Complete | 2026-01-31 | 移除兼容函数，私有化同步方法    |
| 5.13 | 权限模块移至应用层        | Complete | 2026-01-31 | bot/services/permission_service |

## Progress Log

### 2026-01-31 (晚上 10:00)
- ✅ **任务完成**
- TASK006 中实现了所有目标：
  - handlers 拆分为 7 个模块
  - 创建 DownloadService, QueryService, SearchService
  - 移除 GroupConfigDep
  - JMService 简化（移除兼容函数）
  - 权限模块移至应用层
- 41 tests passed ✅

### 2026-01-30 (晚上 7:05)
- 新增 Phase 3：接口层/服务层分离设计
- 确定架构原则：
  - dependencies.py 只注入 NoneBot 框架相关内容
  - 移除 GroupConfigDep，由 service 通过 data_manager 获取
  - infra 层只提供类定义，不实例化
- 设计 services/ 目录结构
- 设计 DownloadService 类接口

### 2026-01-29 (晚上 8:48)
- 分析 jm_download 群聊/私聊差异
- 设计 Phase 2 公共代码抽取方案
- 确定待抽取的函数列表

### 2026-01-29 (晚上 8:35)
- 完成 Phase 1：所有命令使用 permission + rule 分离
- 41 tests passed

### 2026-01-29 (晚上 7:08)
- 创建任务，设计 matcher 分离方案


