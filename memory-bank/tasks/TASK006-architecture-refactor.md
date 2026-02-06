# [TASK006] - 项目架构重构

**Status:** In Progress
**Added:** 2026-01-30
**Updated:** 2026-01-30

## Original Request

按照分层架构重构项目，将业务逻辑与 NoneBot 框架解耦，提高可测试性和可维护性。

## 目标架构

```
nonebot_plugin_jmdownloader/
├── __init__.py              # 入口
├── config.py                # 插件配置
├── migration.py             # 数据迁移脚本（单独放最外层）
│
├── core/                    # ✅ 核心业务逻辑（领域层）
│   ├── __init__.py
│   ├── models.py            # ✅ 数据模型（GroupConfig, UserData, GlobalConfig）
│   ├── permissions.py       # ✅ 权限规则（纯函数）
│   ├── restriction.py       # ✅ 限制检查逻辑
│   └── session.py           # ✅ 搜索会话管理
│
├── infra/                   # ✅ 基础设施层（外部系统适配）
│   ├── __init__.py
│   ├── jm_service.py        # ✅ JMService 类
│   ├── data_manager.py      # ✅ DataManager 类
│   ├── pdf_utils.py         # ✅ PDF 处理
│   └── image_utils.py       # ✅ 图片处理
│
├── bot/                     # ✅ NoneBot 相关
│   ├── __init__.py
│   ├── dependencies.py      # ✅ 依赖注入
│   │
│   ├── services/            # ✅ 应用服务层（方案 B：返回结果）
│   │   ├── __init__.py
│   │   ├── download_service.py  # ✅ 下载业务流程
│   │   └── query_service.py     # ✅ 查询业务流程
│   │
│   └── handlers/            # ✅ 命令处理器（接口层）
│       ├── __init__.py
│       ├── download.py      # ✅ jm下载
│       ├── query.py         # ✅ jm查询
│       ├── search.py        # ✅ jm搜索、jm下一页
│       ├── blacklist.py     # ✅ 黑名单管理
│       ├── group_control.py # ✅ 群功能控制
│       ├── content_filter.py # ✅ 内容过滤
│       └── scheduled.py     # ✅ 定时任务
```

## 架构原则

### 1. 依赖注入的范围
- `bot/dependencies.py` 只注入 **NoneBot 框架提供的东西**（Bot、Event 等）
- **不要创建业务依赖注入**（如 GroupConfigDep）
- 业务数据（如 GroupConfig）由服务层通过 `data_manager.get_group()` 获取

### 2. infra 层只提供类定义
- `JMService`, `DataManager` 等都是**类定义**，不在模块内实例化
- 实例化在 `bot/dependencies.py` 或应用入口完成
- 确保 infra 层无副作用，可独立测试

### 3. 职责分离
| 层                  | 位置                  | 职责                                 |
| ------------------- | --------------------- | ------------------------------------ |
| **接口层**          | `bot/handlers.py`     | Matcher 定义、参数提取、调用服务     |
| **应用服务层**      | `bot/services/*.py`   | 业务流程编排、跨模块协调             |
| **基础设施层**      | `infra/*.py`          | 外部系统交互的**类定义**             |
| **领域层**          | `core/*.py`           | 纯业务规则、数据模型                 |
| **依赖注入/实例化** | `bot/dependencies.py` | 只实例化 infra 类，注入 NoneBot 相关 |

### 4. 分层依赖规则
```
handlers.py → services/ → core/ + infra/
                ↓
         dependencies.py (实例化 infra 类)
```

## 分层职责（旧版）

| 层                    | 职责                        | 依赖 NoneBot？ | 可单独测试？ |
| --------------------- | --------------------------- | -------------- | ------------ |
| `core/`               | 纯业务规则、数据模型        | ❌              | ✅            |
| `infra/`              | 外部系统适配器（类定义）    | ❌              | ✅            |
| `bot/services/`       | 业务流程编排                | ❌              | ✅            |
| `bot/handlers.py`     | Matcher，参数提取，消息响应 | ✅              | 需 Mock      |
| `bot/dependencies.py` | 实例化 + NoneBot 依赖注入   | ✅              | 需 Mock      |

## Implementation Plan

### Phase 1: 核心领域层 ✅
- [x] 1.1 创建 `core/` 目录
- [x] 1.2 `core/models.py` - 数据模型（GroupConfig, UserData, GlobalConfig）
- [x] 1.3 `core/restriction.py` - 限制检查规则
- [x] 1.4 `core/session.py` - 搜索会话管理

### Phase 2: 基础设施层 ✅
- [x] 2.1 创建 `infra/` 目录
- [x] 2.2 `infra/jm_service.py` - JMService 类
- [x] 2.3 `infra/data_manager.py` - DataManager 类
- [x] 2.4 `infra/pdf_utils.py` - PDF 处理
- [x] 2.5 `infra/image_utils.py` - 图片处理

### Phase 3: Bot 层 ✅
- [x] 3.1 创建 `bot/` 目录
- [x] 3.2 `bot/dependencies.py` - 依赖注入
- [x] 3.3 `bot/messaging.py` - 消息发送
- [x] 3.4 `bot/permissions.py` - 权限检查

### Phase 4: 应用服务层 🔜
- [ ] 4.1 创建 `bot/services/` 目录
- [ ] 4.2 `bot/services/download_service.py` - 下载业务流程
- [ ] 4.3 `bot/services/query_service.py` - 查询业务流程
- [ ] 4.4 `bot/services/search_service.py` - 搜索业务流程

### Phase 5: 接口层重构 🔜
- [ ] 5.1 重构 `handlers.py` 为瘦接口层
- [ ] 5.2 移除 `GroupConfigDep`，由 service 获取
- [ ] 5.3 更新 `__init__.py` 导入

### Phase 6: 测试与验证
- [ ] 6.1 运行现有测试验证功能
- [ ] 6.2 手动测试关键功能

## 已完成的 core/ 模块

### core/jm_service.py

```python
class JMService:
    """JM 业务服务（无 NoneBot 依赖）"""

    def __init__(self, client: JmcomicClient, downloader: JmDownloader):
        self.client = client
        self.downloader = downloader

    async def get_photo(self, photo_id: str) -> JmPhotoDetail | None:
        """异步获取 photo 信息"""

    async def download_photo(self, photo: JmPhotoDetail) -> bool:
        """异步下载 photo"""

    async def search(self, query: str, page: int = 1):
        """异步搜索本子"""

    @staticmethod
    async def download_avatar(photo_id: int | str) -> BytesIO | None:
        """下载本子封面"""
```

### core/restriction.py

```python
@dataclass
class RestrictedTagIds:
    """受限标签 ID 集合"""
    tag_ids: frozenset[str]

def is_photo_restricted(photo, banned_photo_ids, banned_tag_ids) -> bool:
    """检查 photo 是否受限"""

def find_restricted_tag(photo, banned_tag_ids) -> str | None:
    """查找第一个受限标签"""
```

### core/pdf_service.py

```python
def modify_pdf_md5(original_pdf_path: str, output_path: str) -> bool:
    """修改 PDF 文件的 MD5 值"""
```

### core/image_utils.py

```python
def blur_image(image_bytes: BytesIO) -> BytesIO:
    """对图片进行模糊处理"""

async def blur_image_async(image_bytes: BytesIO) -> BytesIO:
    """异步对图片进行模糊处理"""
```

## 迁移策略

1. **渐进式迁移**：每个 Phase 完成后运行测试验证
2. **保持向后兼容**：在迁移过程中保留旧代码，确保功能正常
3. **模块化导入**：使用 `__init__.py` 统一导出，对外接口不变

## Progress Tracking

**Overall Status:** Complete - 100% ✅

### Subtasks
| ID   | Description          | Status   | Updated    | Notes                            |
| ---- | -------------------- | -------- | ---------- | -------------------------------- |
| 6.1  | Phase 1: 核心领域层  | Complete | 2026-01-30 | core/models.py ✅                 |
| 6.2a | Phase 2a: 核心业务层 | Complete | 2026-01-30 | core/ ✅                          |
| 6.2b | Phase 2b: 基础设施层 | Complete | 2026-01-30 | infra/ ✅                         |
| 6.3  | Phase 3: Bot 层重组  | Complete | 2026-01-30 | bot/ ✅                           |
| 6.4  | Phase 4: 应用服务层  | Complete | 2026-01-30 | DownloadService + QueryService ✅ |
| 6.5  | Phase 5: 接口层重构  | Complete | 2026-01-30 | handlers → bot/commands/ ✅       |
| 6.6  | Phase 6: 测试与验证  | Complete | 2026-01-30 | 41 tests passed ✅                |

## Progress Log

### 2026-01-31 (晚上 9:55)
- ✅ JMService 方法私有化
  - 同步方法加 `_` 前缀：`_get_photo_sync`, `_download_photo_sync`, `_search_sync`
  - 移除无意义的 property 封装
  - 只暴露异步公共方法
- ✅ DataManager 属性重命名
  - `global_config` → `restriction`
  - 数据文件 `global.json` → `restriction.json`
- ✅ GlobalConfig 类重命名
  - `GlobalConfig` → `RestrictionConfig`（内容限制配置）
  - 限制检查方法移入类中：`is_photo_restricted()`, `find_restricted_tag()`
  - 删除 `photo_restriction.py`（逻辑已合并）
- ✅ 权限模块移至应用层
  - `core/permissions.py` → `bot/services/permission_service.py`
  - 修复 core 层模块导入路径（models→data_models, restriction→photo_restriction, session→search_session）
- ✅ JMService 兼容函数移除
  - 删除 `get_photo_info_async`, `download_photo_async`, `search_album_async` 等
  - 统一使用 `jm_service.search()`, `jm_service.get_photo()` 等实例方法
- 运行测试：41 passed ✅

### 2026-01-30 (晚上 9:10)
- ✅ 权限规则重构

### 2026-01-30 (晚上 8:10)
- ✅ 添加 Service 设计模式文档到 `systemPatterns.md`
- 记录方案 A（send 回调）和方案 B（返回结果）
- 确定项目统一采用方案 B

### 2026-01-30 (晚上 8:04)
- ✅ 移除 `bot/messaging.py`
- 更新 handlers 直接调用对应 API：
  - 群聊：`send_group_forward_msg`
  - 私聊：`send_private_forward_msg`
- 运行测试：41 passed ✅

### 2026-01-30 (晚上 7:48)
- ✅ 将 `handlers.py` 拆分为多个命令模块
- 创建 `bot/commands/` 目录：
  - `download.py` - jm下载命令
  - `query.py` - jm查询命令
  - `search.py` - jm搜索、jm下一页命令
  - `blacklist.py` - 黑名单管理命令
  - `group_control.py` - 群功能控制命令
  - `content_filter.py` - 内容过滤命令
  - `scheduled.py` - 定时任务
- 删除旧的 `handlers.py`
- 更新 `__init__.py` 导入新的 commands 模块
- 更新测试导入路径
- 运行测试：41 passed ✅

### 2026-01-30 (晚上 7:34)
- ✅ 创建 `QueryService` 封装查询业务逻辑
- ✅ 创建 `SearchService` 封装搜索业务逻辑（含会话管理）
- ✅ 重构 `handle_group_query` 使用 QueryService
- ✅ 重构 `handle_private_query` 使用 QueryService
- 在 `dependencies.py` 中实例化 QueryService 和 SearchService
- 运行测试：41 passed ✅

### 2026-01-30 (晚上 7:22)
- ✅ 创建 `bot/services/` 应用服务层
- ✅ 创建 `DownloadService` 封装下载业务流程
- ✅ 重构 `handle_group_download` 使用 DownloadService
- ✅ 重构 `handle_private_download` 使用 DownloadService
- 移除 `GroupConfigDep`，改为 `data_manager.get_group()`
- 清理未使用的导入
- 运行测试：41 passed ✅

### 2026-01-30 (晚上 7:05)
- 确定架构原则：
  - dependencies.py 只注入 NoneBot 框架相关内容
  - 移除 GroupConfigDep，由 service 通过 data_manager 获取
  - infra 层只提供类定义，不实例化
- 更新 TASK005 和 TASK006 记录这些原则

### 2026-01-30 (晚上 6:35)
- ✅ 创建 `infra/jm_service.py`：将 JM 相关函数封装为 JMService 类
- 保留兼容层函数（get_photo_info_async 等）
- 删除旧的 `jm_compat.py`
- 运行测试：41 passed ✅

### 2026-01-30 (晚上 5:45)
- ✅ 删除 `utils.py`
- 创建 `infra/jm_compat.py` 迁移 JM API 兼容函数
- 运行测试：41 passed ✅

### 2026-01-30 (下午 5:20)
- ✅ 创建 `bot/` 目录
- 迁移 `dependencies.py` 到 `bot/dependencies.py`
- 创建 `bot/messaging.py`（send_forward_message）
- 创建 `bot/permissions.py`（check_permission）
- 删除旧的 `dependencies.py`
- 运行测试：41 passed ✅

### 2026-01-30 (下午 5:05)
- ✅ 删除 `data.py`（已拆分）
- 删除 `domain/` 目录
- 更新 `migration.py` 导入路径
- 运行测试：41 passed ✅

### 2026-01-30 (下午 4:45)
- ✅ 创建 `core/models.py`（数据模型）
- ✅ 创建 `infra/data_manager.py`（DataManager）
- 更新 `dependencies.py` 导入路径
- 运行测试：41 passed ✅

### 2026-01-30 (下午 3:58)
- ✅ 创建 `infra/` 基础设施层
- 将外部系统适配器从 `core/` 移至 `infra/`：
  - `jm_adapter.py` - JMAdapter 类（原 jm_service.py）
  - `pdf_utils.py` - modify_pdf_md5 函数
  - `image_utils.py` - blur_image, blur_image_async
- `session.py` 移入 `core/`
- 更新 `handlers.py` 导入路径
- 运行测试：41 passed ✅

### 2026-01-30 (下午 3:17)
- ✅ 完成 Phase 2: 核心业务层创建
- 创建 `core/` 目录，包含 4 个模块：
  - `jm_service.py` - JMService 类，封装 jmcomic 操作
  - `pdf_service.py` - modify_pdf_md5 函数
  - `restriction.py` - RestrictedTagIds, is_photo_restricted, find_restricted_tag
  - `image_utils.py` - blur_image, blur_image_async
- 所有模块无 NoneBot 依赖，可独立测试
- 运行测试：41 passed ✅

### 2026-01-30 (下午 3:12)
- 创建任务
- 设计目标架构
- 制定详细实施计划
- 设计核心服务接口

