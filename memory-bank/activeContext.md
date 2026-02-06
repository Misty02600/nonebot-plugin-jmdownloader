# Active Context

## 当前工作重点

**代码清理与优化** - 2026-02-06 进行配置精简和依赖清理。

## 最近变更

- **2026-02-06**: TASK009 深度优化 + Bug 修复
  - ✅ `OutputFormat` 移至 `core/enums.py`（领域概念独立）
  - ✅ 移除 `SEVENZIP`（jmcomic `open_zip_file` 在无 encrypt 时用 zipfile 而非 py7zr）
  - ✅ 添加 `jmcomic_zip_password` 配置 + YAML encrypt 块条件生成
  - ✅ 添加 `pyzipper>=0.3.6` 依赖（轻量 AES 加密）
  - ✅ 修复 `download_success_dict` 状态泄漏（每次下载前 `.clear()`）
  - ✅ 修复下载后不验证输出文件（`file_path.exists()` 检查）
  - ✅ 完成 ZipPlugin 错误行为调研（`call_all_plugin(safe=True)` 吞异常）

- **2026-02-06**: 代码清理与配置精简
  - ✅ 移除 `JMCOMIC_BLOCKED_MESSAGE` 配置项
  - ✅ 移除 `yaml` 依赖，改用手动字符串引用函数
  - ✅ 更新 README 添加升级提示
  - ✅ 修复迁移文件名不匹配 (`global.json` → `restriction.json`)
  - ✅ 修复 Tags 处理逻辑错误 (`tag[0]` → `list(photo.tags)`)
  - ✅ 修复 YAML 特殊字符注入（添加 `quote()` 函数）
  - ✅ 优化 DataManager 类型注解
  - ✅ 删除死配置 `forbidden_albums`（合并到 `restricted_ids`）
  - ✅ 添加 `RandomNickname` 依赖
  - ✅ 移除 infra 层对 NoneBot logger 的直接依赖（依赖注入）
  - 创建 3 个新任务：TASK014/015/016

- **2026-02-05**: TASK011 完成 - Handlers 前置检查模式重构
  - 删除 `bot/params.py`、`bot/checks.py`、`bot/utils.py`
  - 创建 `bot/nonebot_utils.py`、`handlers/dependencies.py`、`handlers/common_handlers.py`

## 当前状态

- 项目版本: 1.0.4
- 分支: dev
- 状态: Bug 修复完成
- 测试: 113 passed ✅

## 待处理任务

### 高优先级
- [TASK014] 下载失败不扣减额度 - 额度应在下载成功后才扣减

### 中优先级
- [TASK016] 数据文件损坏时的容错处理 - 备份损坏文件并返回默认值
- [TASK015] JmDownloader 单例状态泄漏 - 已部分缓解(clear dict)，仍需新实例化方案

### 低优先级
- [TASK013] 群启用检查改为事件处理
- [TASK012] 违规下载惩罚配置
- [TASK010] 私聊下载开关配置
- 其他...

## 活跃决策

### 技术要点

1. **JmPhotoDetail.tags 类型**: `List[str]`，元素是标签名（如 "獵奇"），不是标签 ID
2. **限制逻辑**: 按**标签名**统一比较
3. **YAML 安全**: 使用手动 `quote()` 函数（单引号包裹 + 转义）替代 yaml 依赖
4. **依赖注入**: infra 层通过参数接收 logger，不直接导入 NoneBot

5. **jmcomic 插件异常处理**: `call_all_plugin(safe=True)` 吞掉所有异常（仅 traceback），
   插件失败不会抛到调用方。检测失败的唯一方式是验证输出文件存在性。
6. **ZIP 加密**: 通过 `pyzipper` 实现 AES-128，jmcomic `ZipPlugin.open_zip_file()` 在有 `encrypt_dict` 时自动使用

### 已确定的设计决策

1. **模块结构** (2026-02-05)
   - `bot/nonebot_utils.py`：纯 NoneBot 工具函数
   - `bot/handlers/dependencies.py`：参数解析依赖 + GroupRule
   - `bot/handlers/common_handlers.py`：前置检查 handler

2. **Handlers 前置检查模式**
   - 使用 `handlers=[]` 参数声明前置检查
   - 四层分工：permission → Depends → Check Handler → Business Handler

3. **Service 设计模式 - 方案 B（返回结果）**
   - Service 只返回结果数据结构
   - Handler 负责发送消息

4. **ID 统一 str 类型**: group_id、user_id 全部使用 str

## 下一步计划

1. 实施 TASK014：下载成功后才扣减额度
2. 实施 TASK016：数据文件损坏容错
3. 实施 TASK015：JmDownloader 实例化改进

## 相关文件

- 参数依赖: [handlers/dependencies.py](../src/nonebot_plugin_jmdownloader/bot/handlers/dependencies.py)
- 前置检查: [handlers/common_handlers.py](../src/nonebot_plugin_jmdownloader/bot/handlers/common_handlers.py)
- 数据管理: [infra/data_manager.py](../src/nonebot_plugin_jmdownloader/infra/data_manager.py)
- JM 服务: [infra/jm_service.py](../src/nonebot_plugin_jmdownloader/infra/jm_service.py)
