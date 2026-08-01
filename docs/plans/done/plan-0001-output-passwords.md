# PLAN-0001：ZIP/PDF 输出密码

## 状态

已完成

## 完成时间

2026-08-02

## 最后结果和当前行为

- ZIP 与 PDF 分别使用 `jmcomic_zip_password` 和 `jmcomic_pdf_password`，默认均为 `None`；固定字符串直接作为密码，所有字面 `{id}` 替换为当前 photo 或 album ID。
- 项目复用 jmcomic 自带的 ZIP AES 和 PDF 加密插件。基础 option 不携带请求密码；每次下载深拷贝插件配置并注入本次解析后的密码，避免并发请求污染共享状态。
- 缓存不保存 sidecar 或配置指纹。每次准备发送时用当前密码实际打开 PDF/ZIP；密码改变、加密状态改变或文件损坏时删除旧输出并按需重建。
- 同一输出路径由单独的异步锁串行化，不同路径仍可并行。下载 handler 持有缓存读租约直到 OneBot 上传结束，每日清理取得写锁后再重建缓存目录。
- ZIP 保持 `delete_original_file: false`，由每日缓存清理统一回收源图片。
- 同步 jmcomic、文件验证和目录清理使用标准 `asyncio.to_thread()`；当前运行路径没有额外取消桥、sidecar 或指纹状态机。

## 怎么验证的

- `uv run pytest -q`：177 个测试通过，保留 1 个既有的 pytest 收集警告；
- `uv run ruff check .`、`uv run ruff format --check .`、`uv run basedpyright`：通过；
- `uv lock --check`、`git diff --check` 和 sdist/wheel 构建：通过；
- 使用实际安装的 `jmcomic 2.6.13` 离线运行 photo/album 的 PDF、ZIP 插件：有密码、无密码和选集输出均能生成并通过实际文件验证，源图片按配置保留；
- 回归测试覆盖配置规范化、模板替换、请求 option 隔离、缓存复用与失效、同路径去重、不同路径并行、定时清理等待以及四条上传链路的租约范围。

## 审批与提交

- 用户确认：2026-08-02 确认代码没有阻断问题时整理提交，并创建到 `main` 的 PR；
- Git 提交：长期 repo docs 为 `3ad4654`，业务实现与测试为 `98f2faa`；本完成记录随 PR 分支提交。

## 文档同步到哪里

- [架构总览](../../architecture/overview.md)
- [输出准备与密码流程](../../architecture/flows/output-preparation.md)
- [缓存使用与清理流程](../../architecture/flows/cache-lifecycle.md)
- [JM 服务导览](../../architecture/files/infra-jm-service.md)
- [ADR-0002：用运行时锁协调缓存并采用标准线程调用](../../adr/0002-coordinate-cache-with-runtime-locks.md)

## 已知缺口和后续事项

- 锁仅覆盖单个 Python 进程，多进程共享缓存不受支持；
- 如果未来加入下载超时或主动任务取消，需要重新设计线程与锁的生命周期；
- jmcomic 升级后需要复核 `copy_option()` 和输出插件配置结构；
- 可以后续增加真实 jmcomic 输出插件的自动化薄集成测试，以及下载异常后清理半成品并重试的专项测试；当前版本已完成手工插件验证，源码中的失败清理逻辑也已审查。

## 相关文档

- [ADR 索引](../../adr/README.md)
- [架构阅读入口](../../architecture/README.md)
