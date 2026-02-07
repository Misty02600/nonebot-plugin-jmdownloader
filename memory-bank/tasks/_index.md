# Tasks Index

任务管理索引文件，记录所有任务的状态。

## In Progress
*当前没有进行中的任务*

## Pending
- [TASK016] 数据文件损坏时的容错处理 - 备份损坏文件并返回默认值
- [TASK015] JmDownloader 单例状态泄漏 - 每次下载创建新实例避免内存泄漏（已部分缓解：download_success_dict.clear()）
- [TASK007] 群级别内容屏蔽 - 将全局屏蔽改为群独立配置

## Completed
- [TASK014] 下载失败不扣减额度 - 完成于 2026-02-07
  - 利用 handler 链 + finish 特性：下载成功后才扣减
  - `send_progress_message` 查询但不扣减
  - `deduct_limit` 静默扣减
- [TASK013] 群启用检查改为事件处理 - 完成于 2026-02-07
  - `group_enabled_check` 添加提示消息 "当前群聊未开启该功能"
  - `private_enabled_check` 添加提示消息 "私聊功能已禁用"
- [TASK008] 群启用黑白名单模式 - 完成于 2026-02-07
  - `jmcomic_group_list_mode` 配置项（blacklist/whitelist）
  - `jmcomic_allow_groups` 作为别名向后兼容
  - `GroupConfig.is_enabled(mode)` 使用 match case
  - 114 tests passed
- [TASK012] 违规下载惩罚配置 - 完成于 2026-02-07
  - `jmcomic_punish_on_violation` 配置项控制是否惩罚
  - 所有用户（包括超管）都受内容限制
  - 超管/管理员/群主免惩罚，使用 `GROUP_ADMIN | GROUP_OWNER` 检查
  - 114 tests passed
- [TASK010] 私聊下载开关配置 - 完成于 2026-02-06
  - `jmcomic_allow_private` 配置项
  - `private_enabled_check` handler 检查
  - 所有私聊命令已集成检查
- [TASK009] 支持压缩包格式下载 - 完成于 2026-02-06
  - `OutputFormat` StrEnum (pdf/zip)，7z 已移除（jmcomic bug）
  - `core/enums.py` 独立模块，`jmcomic_zip_password` 配置，`pyzipper>=0.3.6`
  - 修复 download_success_dict 泄漏 + 输出文件存在性验证
  - ZipPlugin 错误行为调研完成（safe=True 吞异常）
  - 114 tests passed
- [TASK017] 合并重复命令 Matcher - 完成于 2026-02-06
  - 合并群聊/私聊 matcher 为单一 matcher
  - 使用 handler 参数类型注解实现自动分发
  - 移除 GroupRule，改用 `matcher.finish()` 静默终止
  - 114 tests passed
- [TASK011] Handlers 前置检查模式重构 - 完成于 2026-02-05
  - 删除 `bot/params.py`、`bot/checks.py`、`bot/utils.py`
  - 创建 `bot/nonebot_utils.py`：通用工具函数
  - 创建 `bot/handlers/dependencies.py`：参数解析依赖 + GroupRule
  - 创建 `bot/handlers/common_handlers.py`：前置检查 handler
  - `format_photo_info` 移入 JMService 类
  - 日志格式统一
  - All checks passed
- [TASK006] 项目架构重构 - 完成于 2026-01-31
  - 分层架构 (core/infra/bot)
  - Service 设计模式（方案 B）
  - `GlobalConfig` → `RestrictionConfig` 重命名
  - JMService 简化（移除兼容函数）
  - 权限模块移至应用层
  - 41 tests passed
- [TASK005] 重构指令处理函数 - 完成于 2026-01-29
  - 拆分群聊/私聊 handler（jm_download, jm_query, jm_search, jm_next_page）
  - 提取公共逻辑到辅助函数
  - 41 tests passed
- [TASK004] 依赖注入系统 - 完成于 2026-01-29
  - 创建 `dependencies.py` 集中管理实例化和依赖
  - 实现 `GroupConfigDep` 和 `GroupRule`
  - 41 tests passed
- [TASK003] 重构插件结构 - 完成于 2026-01-28
  - 创建 `handlers.py` 模块（709 行）
  - `__init__.py` 简化为入口点（76 行）
  - 41 tests passed
- [TASK002] 重构翻页缓存 - 完成于 2026-01-28
  - 创建 `session.py` 模块
  - `SearchSession` 封装翻页逻辑
  - `SessionManager` 使用 TTLCache 管理会话
  - 41 tests passed
- [TASK001] 重构数据管理器 - 完成于 2026-01-28
  - 使用 msgspec 进行序列化
  - 使用 boltons.fileutils.atomic_save 确保原子写入
  - 简化 DataManager，删除便捷方法
  - 使用 @cache 装饰 get_group
  - 41 tests passed

## Abandoned
- [TASK018] 简化解除拉黑权限 - 废弃于 2026-02-07（TASK012 已解决相关问题）

---

## 任务创建指南

使用 **add task** 或 **create task** 命令创建新任务时，将自动：
1. 在 `tasks/` 文件夹中创建任务文件
2. 更新此索引文件

### 任务状态说明
- **In Progress**: 正在进行中的任务
- **Pending**: 等待开始的任务
- **Completed**: 已完成的任务
- **Abandoned**: 已废弃的任务

### 任务 ID 格式
`TASK001`, `TASK002`, ... (三位数字编号)
