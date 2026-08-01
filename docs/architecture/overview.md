# 架构总览

## 系统边界

`nonebot-plugin-jmdownloader` 是仅支持 OneBot V11 的 NoneBot 插件。它接收查询、搜索、下载、群配置和限制管理命令，通过 `jmcomic` 获取元数据与图片，将内容转换为 PDF 或 ZIP，再调用 OneBot 文件上传 API 发送到群聊或私聊。

插件自身不实现协议端传输、JM 站点客户端、调度器或平台数据目录；这些能力分别来自 NoneBot OneBot V11 适配器、`jmcomic`、`nonebot_plugin_apscheduler` 和 `nonebot_plugin_localstore`。

## 组件与职责

| 区域 | 主要职责 | 不应承担 |
|---|---|---|
| [`__init__.py`](../../src/nonebot_plugin_jmdownloader/__init__.py) | 插件元数据、启动迁移、导入 handler 完成命令注册 | 业务流程和文件处理 |
| [`config.py`](../../src/nonebot_plugin_jmdownloader/config.py) | Pydantic 配置模型、默认值、兼容字段与输入规范化 | 访问网络或写运行时状态 |
| [`bot/dependencies.py`](../../src/nonebot_plugin_jmdownloader/bot/dependencies.py) | 读取插件配置，组装共享服务，定义 NoneBot 依赖，后台预热 JM client | 下载格式细节 |
| [`bot/handlers/`](../../src/nonebot_plugin_jmdownloader/bot/handlers/) | 命令链、权限和限制检查、面向用户的消息、OneBot 上传 | 直接操作 JM 插件配置或持久化格式 |
| [`core/`](../../src/nonebot_plugin_jmdownloader/core/) | 枚举、群/用户/限制模型、搜索会话翻页规则 | NoneBot、网络和文件 I/O |
| [`infra/data_manager.py`](../../src/nonebot_plugin_jmdownloader/infra/data_manager.py) | msgspec JSON 读写、原子保存、群配置懒加载 | 命令权限判断 |
| [`infra/search_session.py`](../../src/nonebot_plugin_jmdownloader/infra/search_session.py) | 带 TTL 的用户搜索会话缓存 | 持久化历史搜索 |
| [`infra/jm_service.py`](../../src/nonebot_plugin_jmdownloader/infra/jm_service.py) | JM client、搜索/详情/封面，以及输出准备的异步门面 | OneBot 消息与额度扣减 |
| [`infra/jm_option.py`](../../src/nonebot_plugin_jmdownloader/infra/jm_option.py) | 基础 jmcomic option 和请求级密码插件配置 | 缓存生命周期 |
| [`infra/output_cache.py`](../../src/nonebot_plugin_jmdownloader/infra/output_cache.py) | 缓存读写锁、同路径准备锁、复用、重建和清理 | 消息协议和用户策略 |
| [`infra/output_password.py`](../../src/nonebot_plugin_jmdownloader/infra/output_password.py) | 密码模板解析与实际 PDF/ZIP 状态验证 | 下载编排或用户秘密管理 |
| [`infra/image_utils.py`](../../src/nonebot_plugin_jmdownloader/infra/image_utils.py)、[`pdf_utils.py`](../../src/nonebot_plugin_jmdownloader/infra/pdf_utils.py) | 搜索封面模糊与 PDF 唯一 MD5 副本 | 业务授权和缓存决策 |
| [`migration.py`](../../src/nonebot_plugin_jmdownloader/migration.py) | 启动时把旧 JSON 数据迁移到当前布局并保留备份 | 运行期配置变更 |

## 运行时组装

插件导入时依次发生：

1. NoneBot 读取 `PluginConfig`；
2. 旧数据迁移先于 handler 注册执行；
3. `bot/dependencies.py` 使用 localstore 路径构造一个共享 `JMService`、一个 `DataManager` 和一个 `SessionCache`；
4. Bot 启动时后台预热 JM client，不阻塞启动；
5. handler 通过 `Depends` 获取共享服务，按注册顺序执行前置检查，并在共享缓存租约内完成输出准备和上传；
6. apscheduler 每周一 00:00 重置已记录用户的下载次数；每天 03:00 等待已有缓存租约退出后，独占重建插件缓存目录。

同步 `jmcomic` 调用和文件验证通过 `asyncio.to_thread` 离开事件循环。对外接口保持异步，但不假设上游库本身是异步实现。

## 状态与生命周期

### 持久业务数据

由 `nonebot_plugin_localstore.get_plugin_data_dir()` 决定根目录：

```text
data_dir/
├── groups/<group_id>.json   # 群启用状态、文件夹和群黑名单
├── restriction.json        # 全局受限 ID 与 tag
└── user.json               # 已记录用户的剩余下载次数
```

`DataManager` 启动时加载全局限制和用户数据，群配置按需加载到内存。所有写入使用原子替换。旧版 `jmcomic_data.json`、`group.json` 或 `config.json` 只在当前布局不存在时迁移，并保留 `.bak`。

### 临时缓存

由 `nonebot_plugin_localstore.get_plugin_cache_dir()` 决定根目录，包含 JM 图片目录、最终 PDF/ZIP 和可选的唯一 MD5 PDF 副本。ZIP 打包完成后保留原图片供重叠请求复用；缓存每天 03:00 被整体删除并重新创建。清理会等待进行中的下载和上传结束，并阻止新请求在重建期间进入，但缓存仍是可丢弃状态，不得存放业务持久数据。

缓存不保存额外密码状态文件。每次准备时直接用当前密码打开目标 PDF/ZIP；密码、加密开关或文件内容不匹配都会触发按需重建。详细规则见 [输出准备流程](flows/output-preparation.md)。

### 内存状态

- 搜索会话以用户 ID 为 key，默认 TTL 30 分钟；
- `DataManager` 缓存已访问的群配置；
- `JMService` 持有基础 photo/album option 和由它们建立的 client 缓存；
- `JMService` 持有一把进程内异步读写锁：下载/上传共享读取，定时清理独占写入；
- 输出路径锁只在准备过程有使用者时存在，完成后从锁表清理。

这些状态都只在单个 Bot 进程内协调。若未来部署多个进程或多个实例，同一路径锁、搜索会话和群配置缓存不会跨进程同步。

## 关键运行流

- 查询：命令参数 → `JMService.get_photo/get_album` → 格式化信息 → OneBot 消息；
- 搜索：JM 搜索页 → `SearchSession` 缓存 ID 与翻页位置 → 并发获取详情/封面 → 过滤限制 tag → 合并转发消息；
- 下载：权限/额度/内容检查 → 取得[缓存共享租约](flows/cache-lifecycle.md) → [准备并验证输出](flows/output-preparation.md) → OneBot 群或私聊文件上传 → 释放租约 → handler 链继续执行；
- 管理：群开关、文件夹、黑名单和全局限制命令 → `DataManager` → 原子 JSON 写入；
- 定时维护：每周重置下载次数；每天取得缓存独占权后删除并重建下载缓存。

## 质量目标和约束

- 配置升级默认不改变现有输出：ZIP/PDF 密码均默认关闭；
- 要求加密时不能静默降级为明文，生成后必须实际打开文件验证；
- 同一最终输出路径的准备由进程内锁串行化；不同最终路径不会互相等待，但该锁不判断它们是否共享上游 photo 工作目录；
- 输出路径从准备开始到 OneBot 上传完成一直受缓存共享租约保护；独占清理不会删除正在使用的文件；
- 同步 jmcomic 与文件操作通过标准 `asyncio.to_thread()` 执行；当前不提供主动下载取消或超时语义；
- 基础 `JmOption` 不携带请求密码，避免共享状态污染；
- 业务数据写入必须原子化，下载缓存允许每日清理；
- 内容限制、下载额度和上传 API 留在 handler 层，JM 服务只返回可上传文件或失败；
- `{id}` 密码是轻量防探测措施，不等同于秘密或访问控制。

## 外部依赖风险

- `jmcomic` 的插件配置结构和 `copy_option()` 复制语义是输出流程的关键兼容点；
- 当前 `Bd_Pid` 目录规则会让内容重叠的请求共享 photo 工作目录，最终输出路径锁不负责协调该资源；
- ZIP 输出显式关闭上游 `delete_original_file`，避免一个请求完成打包后删除其他请求仍可能使用的图片；
- PDF/ZIP 的实际加密兼容性由上游插件及 `pikepdf`、`pyzipper` 决定；
- OneBot 实现对群文件夹、私聊文件和大文件超时的行为可能不同；
- 多进程部署没有分布式锁或共享会话，当前设计面向单进程插件实例；
- `aiorwlock` 和输出路径锁都只在一个事件循环进程内生效；多进程共享缓存不在当前支持范围内。

缓存协调决定见 [ADR-0002](../adr/0002-coordinate-cache-with-runtime-locks.md)。输出密码功能的最终范围、验证和后续事项见 [PLAN-0001](../plans/done/plan-0001-output-passwords.md)。
