# [TASK009] - 支持压缩包格式下载

**Status:** Completed
**Added:** 2026-02-01
**Updated:** 2026-02-06

## Original Request

准备添加一个新功能，可以为群聊上传压缩包文件而非 PDF。压缩包功能似乎在 jmcomic 库有插件实现，调研并规划方案。

## Research

### jmcomic 压缩文件插件

✅ **调研完成 (2026-02-06)**

| 项目                  | 信息                                                  |
| --------------------- | ----------------------------------------------------- |
| **当前 jmcomic 版本** | 2.6.13                                                |
| **zip 插件要求版本**  | >=2.6.0（dir_rule 等高级配置）                        |
| **支持格式**          | `pdf`、`zip`（7z 已移除，见下方说明）                 |
| **额外依赖**          | `pyzipper>=0.3.6`（ZIP 加密）；`img2pdf`（PDF 生成）  |
| **QQ 群文件支持**     | ✅ 支持 pdf/zip                                        |

### ⚠️ 7z 格式调研结论：已移除

**原因**：jmcomic 的 `ZipPlugin.open_zip_file()` 仅在 `encrypt.impl == "7z"` 时使用 `py7zr`；
当未配置 `encrypt` 时，即使设置 `suffix: 7z`，实际仍使用标准 `zipfile.ZipFile`，
产出的是 **ZIP 格式文件但带 `.7z` 扩展名**，完全错误。

`py7zr` 本身也有问题：8+ 传递依赖（PyCryptodomex、backports.zstd、PyPPMd、Brotli 等），
运行时需 300-700MB 内存。权衡后决定移除 7z 支持。

### ZIP 加密方案

使用 `pyzipper`（纯 Python，零外部依赖，stdlib `zipfile` 的 AES 加密 fork）：
- 已添加 `jmcomic_zip_password` 配置项
- YAML 生成时条件性插入 `encrypt: password:` 块
- jmcomic 的 `ZipPlugin.open_zip_file()` 在有 `encrypt_dict` 时会 `import pyzipper` 并使用 AES-128

### ZipPlugin 错误行为调研

**调研链路**（jmcomic 源码）：

1. `JmDownloader.after_photo()` → `self.option.call_all_plugin('after_photo', safe=True, ...)`
2. `JmOption.call_all_plugin(safe=True)` 中：
   ```python
   try:
       self.invoke_plugin(pclass, kwargs, extra, pinfo)
   except BaseException as e:
       if safe is True:
           traceback_print_exec()  # 仅打印堆栈，吞掉异常！
   ```
3. `invoke_plugin()` 内部三层捕获：
   - `PluginValidationException` → `handle_plugin_valid_exception`（默认 mode=`log`，仅日志）
   - `JmcomicException` → `handle_plugin_jmcomic_exception`（日志 + re-raise）
   - `BaseException` → `handle_plugin_unexpected_error`（日志 + re-raise）
4. `invoke_plugin` 的 re-raise 到达 `call_all_plugin` 后被 `safe=True` **吞掉**

**结论**：ZipPlugin/Img2pdfPlugin 出错时，异常被静默吞掉，输出文件不生成（或损坏），
但下载流程照常返回成功。**唯一能检测失败的方式是检查输出文件是否存在**。

可能的错误场景：

| 场景 | 触发位置 | 异常类型 | 后果 |
|------|----------|----------|------|
| `download_success_dict` 找不到 key | `get_downloaded_photo()` | `KeyError` | ZIP 不生成 |
| 压缩目录不存在/为空 | `zip_photo()` → `files_of_dir()` | `FileNotFoundError` | ZIP 不生成 |
| 磁盘空间不足 | `zipfile.ZipFile.write()` | `OSError` | ZIP 损坏或为空 |
| pyzipper 未安装（有加密时） | `open_zip_file()` | `PluginValidationException` | ZIP 不生成 |
| encrypt 配置缺 password 字段 | `decide_password()` | `KeyError` | ZIP 不生成 |

### 关键配置项

| 配置项                 | 说明                                |
| ---------------------- | ----------------------------------- |
| `level`                | `photo`（按章节）或 `album`（整本） |
| `filename_rule`        | 命名规则，如 `Pid`、`Aid`           |
| `zip_dir`              | 输出目录                            |
| `suffix`               | 文件扩展名：`zip`                   |
| `delete_original_file` | 压缩后删除原始图片                  |
| `encrypt`              | 可选加密，`password` 字段           |

## Thought Process

### 设计方案（最终版）

采用**全局配置硬编码**方式，不做群级别配置。

#### 1. OutputFormat 枚举

```python
# core/enums.py（从 config.py 独立出来，属于领域概念）
from enum import StrEnum

class OutputFormat(StrEnum):
    PDF = "pdf"
    ZIP = "zip"
    # SEVENZIP 已移除：jmcomic 在无 encrypt 时实际使用 zipfile 而非 py7zr
```

#### 2. 配置选项

```python
# config.py
class PluginConfig(BaseModel):
    jmcomic_output_format: OutputFormat = Field(
        default=OutputFormat.PDF,
        description="输出格式：pdf 或 zip"
    )
    jmcomic_zip_password: str | None = Field(
        default=None,
        description="ZIP 压缩包密码（仅 ZIP 格式有效，需安装 pyzipper）"
    )
```

#### 3. JMConfig 修改

```python
@dataclass
class JMConfig:
    cache_dir: str
    output_format: OutputFormat = OutputFormat.PDF
    zip_password: str | None = None
    # ... 其他字段
```

#### 4. create_jm_service YAML 生成

ZIP 格式时条件性生成 encrypt 块：
```python
case OutputFormat.ZIP:
    encrypt_block = ""
    if config.zip_password:
        encrypt_block = f"""
        encrypt:
          password: {quote(config.zip_password)}"""
    plugin_block = f"""  after_photo:
    - plugin: zip
      kwargs:
        zip_dir: {quote(config.cache_dir)}
        filename_rule: Pid
        level: photo
        suffix: zip
        delete_original_file: true{encrypt_block}
"""
```

#### 5. 已修复的 Bug

1. **download_success_dict 状态泄漏**（关联 TASK015）
   - 问题：JmDownloader 单例的 `download_success_dict` 在 `__enter__`/`__exit__` 中不清理
   - 后果：内存泄漏 + `after_zip` 遍历所有历史记录时尝试删除已不存在的文件
   - 修复：在 `download_photo()` 中调用 `self._downloader.download_success_dict.clear()`

2. **下载后输出文件不验证**
   - 问题：ZipPlugin/Img2pdfPlugin 出错时异常被 `call_all_plugin(safe=True)` 吞掉，
     `prepare_photo_file` 返回不存在的文件路径
   - 修复：下载后添加 `file_path.exists()` 检查，失败返回 None 并记录错误日志

## Implementation Plan

- [x] 1. 调研验证 ✅
- [x] 2. 更新 `pyproject.toml`（Python >=3.11, jmcomic>=2.6.0, pyzipper>=0.3.6）
- [x] 3. 添加 `OutputFormat` 枚举（`core/enums.py`）
- [x] 4. 修改 `config.py`（导入 OutputFormat、添加 zip_password 配置）
- [x] 5. 修改 `infra/jm_service.py`（YAML 生成、下载状态清理、文件验证）
- [x] 6. 修改 `bot/dependencies.py`（传递 output_format + zip_password）
- [x] 7. 修改 `bot/handlers/download.py`（动态扩展名、MD5 仅 PDF）
- [x] 8. 更新文档和记忆库

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID   | Description                   | Status   | Updated    | Notes                                  |
| ---- | ----------------------------- | -------- | ---------- | -------------------------------------- |
| 9.1  | 调研验证 zip 插件             | Complete | 2026-02-06 | jmcomic >=2.6.0                        |
| 9.2  | 更新 pyproject.toml           | Complete | 2026-02-06 | Python >=3.11, jmcomic>=2.6, pyzipper  |
| 9.3  | 添加 OutputFormat 枚举       | Complete | 2026-02-06 | core/enums.py (PDF/ZIP only)           |
| 9.4  | 修改 config.py                | Complete | 2026-02-06 | 添加 zip_password 配置                 |
| 9.5  | 修改 jm_service.py            | Complete | 2026-02-06 | match case + encrypt + bug fixes       |
| 9.6  | 修改 dependencies.py          | Complete | 2026-02-06 | 传递 zip_password                      |
| 9.7  | 修改 download.py              | Complete | 2026-02-06 | MD5/提示消息处理                       |
| 9.8  | 更新文档                      | Complete | 2026-02-06 |                                        |
| 9.9  | 移除 SEVENZIP                 | Complete | 2026-02-06 | jmcomic bug：无 encrypt 时用 zipfile   |
| 9.10 | download_success_dict 清理    | Complete | 2026-02-06 | 关联 TASK015                           |
| 9.11 | 输出文件存在性验证            | Complete | 2026-02-06 | 检测插件静默失败                       |
| 9.12 | ZipPlugin 错误行为调研        | Complete | 2026-02-06 | safe=True 吞异常                       |

## Progress Log

### 2026-02-01

- 创建任务文件
- 初步调研 jmcomic 压缩文件插件
- 规划初始方案

### 2026-02-06 - 初始实现

- ✅ 完成调研验证（jmcomic >=2.6.0 支持 zip 插件）
- 简化方案：全局配置硬编码，不做群级别配置
- ✅ 全部基础功能实施完成
  - `OutputFormat` StrEnum 添加到 config.py
  - `jm_service.py` 使用 match case 动态生成插件配置
  - `prepare_photo_pdf` 重命名为 `prepare_photo_file`，返回 (路径, 扩展名) 元组
  - 所有检查通过 (Ruff, basedpyright, 114 tests)

### 2026-02-06 - 深度优化

- 🔍 发现 jmcomic 7z 格式 bug：`open_zip_file()` 在无 `encrypt` 配置时使用 `zipfile.ZipFile` 而非 `py7zr`
- ❌ 移除 `OutputFormat.SEVENZIP`，仅保留 PDF/ZIP
- ✅ `OutputFormat` 从 config.py 移至 `core/enums.py`（领域概念独立）
- ✅ 添加 `jmcomic_zip_password` 配置项 + YAML encrypt 块条件生成
- ✅ 添加 `pyzipper>=0.3.6` 到 pyproject.toml（轻量 AES 加密）
- ✅ 修复 `download_success_dict` 状态泄漏：每次下载前 `.clear()`
- ✅ 修复下载后文件不验证：添加 `file_path.exists()` 检查
- 🔍 完成 ZipPlugin 错误行为调研：
  - `call_all_plugin(safe=True)` 会吞掉所有异常，仅打印 traceback
  - 验证了 `file_path.exists()` 是唯一能检测插件失败的方式
