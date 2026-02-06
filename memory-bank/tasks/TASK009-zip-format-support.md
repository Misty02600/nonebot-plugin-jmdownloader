# [TASK009] - 支持压缩包格式下载

**Status:** Pending
**Added:** 2026-02-01
**Updated:** 2026-02-01

## Original Request

准备添加一个新功能，可以为群聊上传压缩包文件而非 PDF。压缩包功能似乎在 jmcomic 库有插件实现，调研并规划方案。

## Research

### jmcomic 压缩文件插件

根据调研，jmcomic 库内置了**压缩文件插件**，支持：

1. **格式支持**: `zip` 和 `7z`
2. **压缩级别**:
   - `photo` - 按章节压缩
   - `album` - 按整本压缩
3. **配置选项**:
   - 自定义文件名规则
   - 指定输出目录
   - 密码保护（可选）

### 当前配置 (img2pdf)

```yaml
# jm_service.py 中的配置
plugins:
  after_photo:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {cache_dir}
        filename_rule: Pid
```

### 压缩包插件配置示例

```yaml
plugins:
  after_album:
    - plugin: zip  # 或 7z
      kwargs:
        zip_dir: {cache_dir}
        filename_rule: Aid  # 按本子 ID 命名
        level: album  # 按整本压缩
        # password: "optional"  # 可选密码
```

## Thought Process

### 设计方案

#### 1. 配置选项

```python
class OutputFormat(StrEnum):
    PDF = "pdf"
    ZIP = "zip"
    SEVENZIP = "7z"

class Config(BaseModel):
    # 新增
    jmcomic_output_format: OutputFormat = Field(default=OutputFormat.PDF)
```

#### 2. 群级别配置（可选）

每个群可以选择自己的输出格式：

```python
class GroupConfig(msgspec.Struct):
    # 新增
    output_format: OutputFormat | UnsetType = msgspec.UNSET
```

#### 3. JMConfig 修改

```python
@dataclass
class JMConfig:
    cache_dir: str
    output_format: str = "pdf"  # "pdf" | "zip" | "7z"
    # ...
```

#### 4. create_jm_service 动态配置

```python
def create_jm_service(config: JMConfig) -> JMService:
    # 根据 output_format 生成不同的插件配置
    match config.output_format:
        case "pdf":
            plugin_config = """
  after_photo:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {cache_dir}
        filename_rule: Pid
"""
        case "zip":
            plugin_config = """
  after_album:
    - plugin: zip
      kwargs:
        zip_dir: {cache_dir}
        filename_rule: Aid
        level: album
"""
        case "7z":
            # 类似 zip 配置
            pass
```

### 需要解决的问题

1. **文件扩展名处理**: PDF 用 `.pdf`，压缩包用 `.zip`/`.7z`
2. **文件查找逻辑**: `download_service.py` 中查找生成的文件
3. **QQ 群文件上传兼容性**: 确认群文件是否支持这些格式
4. **用户选择**: 是否允许用户在命令中指定格式？

## Implementation Plan

- [ ] 1. 调研验证：
  - 确认 jmcomic zip 插件的具体配置语法
  - 测试 zip 插件是否正常工作
  - 确认 QQ 群文件上传对 zip 的支持

- [ ] 2. 修改 `config.py`:
  - 添加 `jmcomic_output_format` 配置项

- [ ] 3. 修改 `infra/jm_service.py`:
  - `JMConfig` 添加 `output_format` 字段
  - `create_jm_service` 根据格式生成不同的插件配置

- [ ] 4. 修改 `bot/dependencies.py`:
  - 传递 output_format 到 JMConfig

- [ ] 5. 修改 `bot/services/download_service.py`:
  - 更新文件查找逻辑，支持多种扩展名

- [ ] 6. （可选）群级别配置:
  - 允许每个群选择不同的输出格式

- [ ] 7. 测试和文档

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description              | Status      | Updated | Notes |
| --- | ------------------------ | ----------- | ------- | ----- |
| 9.1 | 调研验证 zip 插件        | Not Started |         |       |
| 9.2 | 修改 config.py           | Not Started |         |       |
| 9.3 | 修改 jm_service.py       | Not Started |         |       |
| 9.4 | 修改 dependencies.py     | Not Started |         |       |
| 9.5 | 修改 download_service.py | Not Started |         |       |
| 9.6 | 群级别配置（可选）       | Not Started |         |       |
| 9.7 | 测试和文档               | Not Started |         |       |

## Progress Log

### 2026-02-01

- 创建任务文件
- 调研 jmcomic 压缩文件插件
- 规划实施方案
