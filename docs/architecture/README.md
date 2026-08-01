# 架构导航

这是仓库内长期维护知识的入口。用户安装、配置和命令用法以项目根目录的 [README](../../README.md) 为准；这里说明代码边界、运行时状态和修改时需要守住的不变量。

## 从哪里开始

- [架构总览](overview.md)：插件边界、组件分工、数据位置、外部依赖和主要约束。
- [输出准备与密码流程](flows/output-preparation.md)：从下载命令到可上传 PDF/ZIP 的完整状态流。
- [缓存使用与清理流程](flows/cache-lifecycle.md)：下载、上传与定时清理之间的所有权边界。
- [JMService 文件导读](files/infra-jm-service.md)：下载、输出缓存、密码注入和文件验证的核心实现入口。
- [ADR-0002：用运行时锁协调缓存并采用标准线程调用](../adr/0002-coordinate-cache-with-runtime-locks.md)：当前缓存并发与线程边界的完整决定。
- [当前计划：ZIP/PDF 输出密码](../plans/todo/plan-0001-output-passwords.md)：尚未提交的实施记录、验证结果和剩余审批事项。

## 一句话架构

插件入口注册 OneBot V11 命令；`bot/` 负责依赖组装和消息流程，`core/` 保存无 I/O 的领域模型，`infra/` 封装 JMComic、持久化、缓存和文件处理；业务数据与下载缓存分别交给 `nonebot_plugin_localstore` 管理。

## 文档边界

- 稳定结构和运行事实写入 `docs/architecture/`；
- 跨文件、可复用的状态流写入 `docs/architecture/flows/`；
- 只有复杂且高维护价值的源码才建立 `docs/architecture/files/` 导读；
- 进行中的实施记录留在 `docs/plans/todo/`，经用户验收且成功提交后才移入 `done/`；
- 缓存使用与清理的进程内协调决定记录在 ADR；当前没有复杂到需要 C4 图的部署拓扑，因此不创建占位图。

## 保持同步

修改下列内容时，应同时检查对应文档：

| 改动 | 需要复核 |
|---|---|
| 目录分层、依赖组装、数据目录或定时任务 | [架构总览](overview.md) |
| 输出格式、密码模板、缓存命中或验证 | [输出准备流程](flows/output-preparation.md) 与 [JMService 导读](files/infra-jm-service.md) |
| 下载/上传租约、定时清理、读写锁或线程调用 | [缓存生命周期流程](flows/cache-lifecycle.md)、[ADR-0002](../adr/0002-coordinate-cache-with-runtime-locks.md) 与 [JMService 导读](files/infra-jm-service.md) |
| 当前密码功能的范围、验证和交付状态 | [PLAN-0001](../plans/todo/plan-0001-output-passwords.md) |
