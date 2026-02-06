# [TASK015] - JmDownloader 单例状态泄漏

**Status:** Pending
**Added:** 2026-02-06
**Updated:** 2026-02-06

## Original Request
JmDownloader 被作为单例复用，并在 asyncio.to_thread 中并发调用。下载器内部状态（download_success_dict, download_failed_*）会累积，导致内存泄漏。

## Problem Analysis

### 当前实现
```python
# create_jm_service 创建单例
_jm_service = create_jm_service(...)

# JMService 持有单例 downloader
self._downloader = downloader  # 单例！

# 每次下载使用同一个实例
with self._downloader as dler:
    dler.download_by_photo_detail(photo)
```

### JmDownloader 内部状态
```python
class JmDownloader:
    def __init__(self):
        self.download_success_dict: Dict[...] = {}  # 持续累积
        self.download_failed_image: List[...] = []   # 持续累积
        self.download_failed_photo: List[...] = []   # 持续累积
```

### 影响分析

| 影响       | 严重程度 | 说明                          |
| ---------- | -------- | ----------------------------- |
| 功能正确性 | ⚠️ 低     | 下载本身仍会成功              |
| 内存泄漏   | ⚠️ 中     | 随时间推移 dict/list 持续增长 |
| 文件损坏   | ✅ 无     | 每个 photo 有独立文件路径     |
| 竞态条件   | ⚠️ 低     | CPython GIL 保护大部分操作    |

## Thought Process

### 方案 A：每次下载创建新 Downloader（推荐）
- 保存 JmOption 而非 JmDownloader
- 每次 download_photo 时创建新实例
- 无状态累积，无内存泄漏
- 改动小，风险低

### 方案 B：定期清理状态
- 下载完成后手动清空 dict/list
- 需要了解 downloader 内部实现细节
- 可能遗漏

### 方案 C：使用锁串行化
- 避免并发问题但不解决内存泄漏
- 降低性能

## Implementation Plan
- [ ] 1. 修改 JMService，保存 JmOption 而非 JmDownloader
- [ ] 2. 在 download_photo 方法中每次创建新 JmDownloader
- [ ] 3. 测试并发下载场景
- [ ] 4. 验证内存不再泄漏

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID  | Description                    | Status      | Updated | Notes |
| --- | ------------------------------ | ----------- | ------- | ----- |
| 1.1 | 修改 JMService 保存 option     | Not Started | -       | -     |
| 1.2 | 修改 download_photo 创建新实例 | Not Started | -       | -     |
| 1.3 | 测试并发场景                   | Not Started | -       | -     |

## Progress Log
### 2026-02-06
- Created task
- Analyzed JmDownloader internal state
- Determined severity: medium (memory leak over time)
- Recommended solution: create new downloader per download
