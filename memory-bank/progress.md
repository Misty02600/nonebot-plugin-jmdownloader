# Progress

## 项目完成状态

### ✅ 已完成功能

#### 核心功能
- [x] JM 漫画搜索 (`jm搜索`)
- [x] JM 漫画查询 (`jm查询`)
- [x] JM 漫画下载 (`jm下载`)
- [x] 搜索结果分页 (`jm下一页`)

#### 用户管理
- [x] 用户下载次数限制
- [x] 每周自动重置次数
- [x] 群黑名单管理
- [x] 黑名单添加/移除/查看

#### 群管理
- [x] 群功能启用/禁用
- [x] 群文件夹设置
- [x] 超级用户批量管理群

#### 内容过滤
- [x] JM 号屏蔽列表
- [x] 标签屏蔽列表
- [x] 预置敏感内容过滤
- [x] 违规自动惩罚
- [x] 惩罚配置开关 (`jmcomic_punish_on_violation`)
- [x] 特权用户免惩罚（超管/管理员/群主）

#### 系统功能
- [x] 定时缓存清理
- [x] PDF MD5 修改（可选）
- [x] 代理配置支持
- [x] 多线程下载
- [x] JM 账号登录支持

#### 架构重构 (2026-01-31)
- [x] msgspec + boltons 数据管理
- [x] TTLCache 搜索状态管理
- [x] 旧数据自动迁移
- [x] 分层架构重构 (core/ + infra/ + bot/)
- [x] Service 设计模式 - 方案 B（返回结果）
- [x] 数据与行为统一：`RestrictionConfig` 包含限制检查方法
- [x] JMService 简化：移除兼容函数，只暴露异步公共 API

#### Handlers 重构 (2026-02-05)
- [x] 创建 `bot/nonebot_utils.py`：通用工具函数
- [x] 创建 `bot/handlers/dependencies.py`：参数解析依赖 + GroupRule
- [x] 创建 `bot/handlers/common_handlers.py`：前置检查 handler
- [x] 重构所有 handlers：函数式风格 + handlers 前置检查
- [x] `format_photo_info` 移入 JMService 类
- [x] 日志格式统一

#### ZIP 格式支持 (2026-02-06, TASK009)
- [x] `OutputFormat` StrEnum 移至 `core/enums.py`（PDF/ZIP，7z 已移除）
- [x] `jmcomic_zip_password` 配置项 + YAML encrypt 条件生成
- [x] `pyzipper>=0.3.6` 依赖（AES 加密）
- [x] 修复 `download_success_dict` 状态泄漏（关联 TASK015）
- [x] 下载后输出文件存在性验证（检测插件静默失败）
- [x] ZipPlugin 错误行为调研：`call_all_plugin(safe=True)` 吞异常

#### Bug 修复与代码清理 (2026-02-06)
- [x] 移除 `JMCOMIC_BLOCKED_MESSAGE` 配置项
- [x] 移除 `yaml` 依赖，改用手动 `quote()` 函数
- [x] 迁移文件名不匹配 (`global.json` → `restriction.json`)
- [x] Tags 处理逻辑错误 (`tag[0]` → `list(photo.tags)`)
- [x] YAML 特殊字符注入（添加 `quote()` 函数）
- [x] DataManager 类型注解优化
- [x] 删除死配置 `forbidden_albums`（合并到 `restricted_ids`）
- [x] 添加 `RandomNickname` 依赖
- [x] infra 层依赖注入改进（logger 参数化）

#### 违规惩罚配置 (2026-02-07, TASK012)
- [x] `jmcomic_punish_on_violation` 配置项控制惩罚开关
- [x] 所有用户（包括超管）都受内容限制
- [x] 特权用户免惩罚（超管/管理员/群主）
- [x] 使用 NoneBot 内置 `GROUP_ADMIN | GROUP_OWNER` 权限检查

### 📋 待改进/可选功能
- [ ] TASK013: 群启用检查改为事件处理
- [ ] TASK014: 下载失败不扣减额度
- [ ] TASK015: JmDownloader 单例状态泄漏
- [ ] TASK016: 数据文件损坏容错处理
- [ ] 真实环境功能回归测试
- [ ] 支持更多协议适配器
- [ ] 并发请求防护（请求锁、下载去重）

## 已知问题

1. **文件发送超时**: 大文件发送时可能因协议端超时而误报错误
   - 状态: 已添加异常捕获，不影响实际功能

2. **封面下载失败**: 部分漫画封面可能无法获取
   - 状态: 已添加多域名重试机制

3. **下载额度提前扣减**: 额度在下载前扣减，失败也消耗
   - 状态: TASK014 待修复

4. **JmDownloader 状态累积**: 单例复用导致内存泄漏
   - 状态: TASK015 待修复（已部分缓解：download_success_dict.clear()）

5. **数据文件损坏无容错**: 损坏时插件启动失败
   - 状态: TASK016 待修复

## 当前版本

**v1.0.4** - 稳定版本

## 版本历史概要

- **1.0.4**: 数据管理架构重构 + 分层架构 + Handlers 重构 + Bug 修复
  - 使用 msgspec 高性能序列化
  - 使用 boltons 原子写入
  - 完整分层架构 (core/infra/bot)
  - 方案 B Service 设计模式
  - Handlers 前置检查模式
  - 模块结构优化
  - 多个 Bug 修复

- 1.0.x: 初始稳定版本，完整功能实现
  - 支持搜索、查询、下载完整流程
  - 完善的用户和内容管理机制

## 技术债务

- [x] ~~`data_source.py` 样板代码过多~~ → 已重构
- [x] ~~`__init__.py` 文件较大~~ → 已拆分
- [x] ~~权限检查耦合 NoneBot~~ → 已移至应用层
- [x] ~~JMService 兼容函数~~ → 已删除
- [x] ~~params.py/checks.py/utils.py 分散~~ → 已整合
- [x] ~~forbidden_albums 死配置~~ → 已删除
- [ ] 部分异常处理可以更细化
- [ ] 测试覆盖率可以提升

## 文档状态

- [x] README 文档完整
- [x] 配置说明完整
- [x] 命令使用说明完整
- [x] Memory Bank 初始化完成
- [x] systemPatterns.md 更新至最新架构
- [x] Service 设计模式文档 (方案 A 与方案 B)
