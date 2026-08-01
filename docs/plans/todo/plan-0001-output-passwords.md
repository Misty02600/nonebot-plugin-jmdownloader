# PLAN-0001：ZIP/PDF 输出密码

## 状态

进行中

## 最后更新

2026-08-01

## 目标和成功标准

为 ZIP 和 PDF 分别提供固定密码或 `{id}` 模板密码，默认均为 `None`，并让密码变化后的缓存只在下一次准备发送时按需重建。

- ZIP/PDF 密码可以独立配置和关闭；
- photo 使用 `photo.id`，完整或部分 album 使用 `album.id`；
- 并发请求不会覆盖共享 option 的密码；
- 要求加密时不能静默发送明文；
- 缓存清理不删除正在下载或上传的文件；
- PDF 修改 MD5 后保持原密码状态；
- README、长期架构文档、测试和静态检查同步更新。

关联 Issue：[#60](https://github.com/Misty02600/nonebot-plugin-jmdownloader/issues/60)

## 已确认的产品规则

| 配置值 | ID 为 `123` 时 | 语义 |
|---|---|---|
| `None` 或空字符串 | 无密码 | 关闭对应格式加密 |
| `{id}` | `123` | 使用当前下载对象 ID |
| `jm-{id}` | `jm-123` | 自定义模板 |
| `fixed-password` | `fixed-password` | 固定密码 |

模板只执行 `str.replace("{id}", id)`，不调用 Python `format()`。其他花括号保持原样。本功能定位是降低文件被直接预览或自动探测的概率，不提供秘密管理或强机密性。

## 当前方案

### 配置与上游插件

- `jmcomic_zip_password`、`jmcomic_pdf_password` 均为 `str | None = None`；
- 当前格式只读取自己的密码配置；
- 复用 jmcomic 的 `zip` 和 `img2pdf` 插件，通过 `encrypt.password` 实际加密；
- `jmcomic>=2.6.13`，并直接声明验证 PDF 使用的 `pikepdf>=10.3.0`；
- ZIP 设置 `delete_original_file: false`，避免内容重叠请求删除共享图片。

### 请求隔离

- 基础 photo/album option 不携带请求密码；
- 每次下载复制 option，并显式深拷贝 `plugins.src_dict`；
- 密码为 `None` 时删除整个 `encrypt` 配置；
- album 使用对象副本承载章节选择和输出名，不修改调用方传入对象。

显式深拷贝必须保留：当前 jmcomic `copy_option()` 会继续共享嵌套插件字典。

### 缓存和验证

- handler 从准备前到 OneBot 上传结束持有 `aiorwlock` 读锁；
- 每日清理取得写锁，等待活动读者退出后删除并重建缓存目录；
- 同一最终路径使用独立锁覆盖“验证 → 删除失效文件 → 下载 → 新文件验证”；
- 缓存不维护 sidecar 或密码指纹，直接用当前密码打开 PDF/ZIP；
- 密码、加密开关或文件内容不匹配时，下次准备删除旧文件并重新生成；
- 同密码且文件仍有效时直接复用，不因实现标识变化单独刷新；
- 同步 jmcomic 和文件操作使用标准 `asyncio.to_thread()`，当前不额外实现任务取消语义；
- PDF 的唯一 MD5 副本再次执行相同密码验证。

长期行为见 [输出准备与密码流程](../../architecture/flows/output-preparation.md) 和 [缓存使用与清理流程](../../architecture/flows/cache-lifecycle.md)，当前锁与线程决定见 [ADR-0002](../../adr/0002-coordinate-cache-with-runtime-locks.md)。

## 现在做到哪里

- [x] 配置、README 和依赖组装；
- [x] photo/album 请求级密码注入；
- [x] ZIP/PDF 实际文件验证与按需缓存失效；
- [x] 同路径并发去重与锁表回收；
- [x] 下载/上传与每日清理的读写锁协调；
- [x] 删除无实际触发源的自定义取消桥；
- [x] 删除重复的 sidecar/指纹状态；
- [x] 拆分 `jm_option.py`、`output_cache.py`、`output_password.py`，保持 `JMService` 为门面；
- [x] 同步架构、流程、ADR 和本计划；
- [ ] 用户最终验收；
- [ ] 用户明确授权后再决定提交、推送和关闭 Issue。

## 涉及文件

- [`config.py`](../../../src/nonebot_plugin_jmdownloader/config.py)
- [`bot/dependencies.py`](../../../src/nonebot_plugin_jmdownloader/bot/dependencies.py)
- [`bot/handlers/download.py`](../../../src/nonebot_plugin_jmdownloader/bot/handlers/download.py)
- [`bot/handlers/scheduled.py`](../../../src/nonebot_plugin_jmdownloader/bot/handlers/scheduled.py)
- [`infra/jm_option.py`](../../../src/nonebot_plugin_jmdownloader/infra/jm_option.py)
- [`infra/jm_service.py`](../../../src/nonebot_plugin_jmdownloader/infra/jm_service.py)
- [`infra/output_cache.py`](../../../src/nonebot_plugin_jmdownloader/infra/output_cache.py)
- [`infra/output_password.py`](../../../src/nonebot_plugin_jmdownloader/infra/output_password.py)
- [`infra/pdf_utils.py`](../../../src/nonebot_plugin_jmdownloader/infra/pdf_utils.py)
- [`README.md`](../../../README.md)

## 怎么验证

2026-08-01 当前工作区已执行：

```powershell
uv run pytest -q
uv run ruff check src tests
uv run ruff format --check src tests
uv run basedpyright
git diff --check
```

结果：

- 177 项测试通过；
- Ruff、BasedPyright、格式和 diff 检查通过；
- 保留 1 个既有的 `TestableDataManager` pytest 收集警告；
- 覆盖无密码、固定密码、`{id}`、空字符串、密码变化、损坏缓存和 PDF MD5；
- 覆盖同路径只下载一次、不同路径并行、清理等待读者并阻止新读者；
- 覆盖四条下载 handler 的租约从准备持续到上传结束。

## 审批与提交

- 用户确认：已确认实施方向，尚未最终验收业务实现；
- Git 提交：长期 repo docs 已获准单独提交到 `main`；业务代码和测试仍未提交。

代码与验证已经完成，但按仓库文档规则，在业务实现最终确认且提交成功前，本计划继续留在 `plans/todo/` 并保持“进行中”。

## 进展记录

### 2026-08-01

- 核查 NoneBot、APScheduler 与 AnyIO 的实际取消路径，确认当前下载流程没有需要自定义取消桥的触发源；
- 删除 `run_sync_to_completion()`、取消清理分支和专项测试，恢复标准 `asyncio.to_thread()`；
- 复核密码变化检测，确认实际打开文件已经能判断当前密码与加密状态；删除 sidecar、指纹、原子状态写入和重复 ZIP 验证；
- 简化输出锁注册表，保留同路径去重、不同路径并行和锁条目回收；
- 全量测试和静态检查通过；
- 根据最新要求恢复 repo docs 的长期维护与 Git 跟踪。

### 2026-07-31

- 完成 ZIP/PDF 密码、请求 option 隔离、实际文件验证和按需缓存重建；
- 设置 `delete_original_file: false`；
- 使用 `aiorwlock` 协调下载/上传与每日缓存清理；
- 完成首次代码审查与结构拆分。

## 已知边界

- 锁仅覆盖单个 Python 进程，多进程共享缓存不受支持；
- 强制结束进程或断电可能留下半成品，下次准备会通过实际验证识别并重建；
- 若未来加入下载超时或主动任务取消，必须先重新设计线程与锁的生命周期；
- 上游 jmcomic 升级时需复核 `copy_option()` 和输出插件配置结构。
