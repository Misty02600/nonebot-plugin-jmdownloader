# [TASK016] - 数据文件损坏时的容错处理

**Status:** Pending
**Added:** 2026-02-06
**Updated:** 2026-02-06

## Original Request
数据文件损坏时 `_load` 会直接抛异常导致插件启动失败，没有兜底。

## Problem Analysis

### 当前实现
```python
def _load(self, path: Path, cls: type):
    if path.exists():
        return msgspec.json.decode(path.read_bytes(), type=cls)  # 无 try-except
    return cls()
```

### 问题场景

| 场景          | 当前行为     | 期望行为                 |
| ------------- | ------------ | ------------------------ |
| 文件不存在    | ✅ 返回默认值 | 返回默认值               |
| 文件正常      | ✅ 正常加载   | 正常加载                 |
| 文件为空      | ❌ 抛异常     | 备份损坏文件，返回默认值 |
| JSON 格式错误 | ❌ 抛异常     | 备份损坏文件，返回默认值 |
| 类型不匹配    | ❌ 抛异常     | 备份损坏文件，返回默认值 |

### 影响
- 插件完全无法启动
- 用户需要手动删除损坏文件
- 可能丢失所有配置数据

## Thought Process

### 方案 A：捕获异常 + 备份（推荐）
```python
def _load(self, path: Path, cls: type):
    if path.exists():
        try:
            return msgspec.json.decode(path.read_bytes(), type=cls)
        except Exception as e:
            logger.error(f"数据文件损坏: {path}, 错误: {e}")
            backup = path.with_suffix(".json.corrupted")
            shutil.copy2(path, backup)
            path.unlink()
            logger.warning(f"已备份损坏文件到: {backup}")
            return cls()
    return cls()
```

### 方案 B：只记录日志
- 不备份，直接覆盖
- 数据丢失无法恢复

### 方案 C：启动失败 + 友好提示
- 保持当前行为但增加提示信息
- 不解决核心问题

## Implementation Plan
- [ ] 1. 在 `_load` 中添加 try-except
- [ ] 2. 捕获到异常时备份损坏文件
- [ ] 3. 记录错误日志
- [ ] 4. 返回默认实例
- [ ] 5. 添加单元测试

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description  | Status      | Updated | Notes |
| --- | ------------ | ----------- | ------- | ----- |
| 1.1 | 添加异常处理 | Not Started | -       | -     |
| 1.2 | 实现文件备份 | Not Started | -       | -     |
| 1.3 | 添加日志记录 | Not Started | -       | -     |
| 1.4 | 编写测试用例 | Not Started | -       | -     |

## Progress Log
### 2026-02-06
- Created task
- Analyzed current implementation and failure scenarios
- Recommended solution: catch exception + backup corrupted file
