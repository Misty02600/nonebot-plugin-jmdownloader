# 缓存使用与清理流程

## 这条流程保证什么

在单个 Bot 进程内，定时清理不会删除正在下载、验证或上传的文件。该流程只协调可丢弃的插件缓存，不涉及 `data_dir` 中的业务数据。

正式取舍见 [ADR-0002](../../adr/0002-coordinate-cache-with-runtime-locks.md)，核心实现位于 [`OutputCache`](../../../src/nonebot_plugin_jmdownloader/infra/output_cache.py)，对 handler 的入口由 [`JMService`](../../../src/nonebot_plugin_jmdownloader/infra/jm_service.py) 暴露。

## 参与者和锁层次

| 参与者 | 所有权 | 保护区间 |
|---|---|---|
| 四个下载 handler | `aiorwlock` 读锁 | 调用 `prepare_*_file()` 前到 `bot.call_api()` 返回或失败 |
| `OutputCache.prepare()` | 最终输出路径锁 | 缓存验证、失效删除、下载和新输出验证 |
| 定时清理 | `aiorwlock` 写锁 | 删除整个缓存根目录并重新创建 |

固定锁顺序是：

```text
缓存读锁 → 最终输出路径锁
```

清理只获取缓存写锁。不要反向获取，也不要在持有读锁时升级为写锁。每条 handler 调用链只在最外层获取一次读锁，使源码中的租约范围直接覆盖准备和上传。

## 正常下载与上传

```text
handler 请求缓存读锁
  ├─ 多个普通请求可以并行进入
  ├─ prepare 获取自己的输出路径锁
  │    └─ 验证并复用缓存，或下载并验证新输出
  ├─ OneBot 上传仍在读锁范围内读取该路径
  └─ 上传结束或异常退出后释放读锁
```

输出路径锁只去重相同最终文件。不同路径拥有不同的锁，仍可并行下载。等待者进入锁后必须重新验证缓存，因为前一个请求可能已经生成了可复用输出。锁条目记录等待者和持有者数量，最后一个使用者退出后从表中删除。

## 定时清理

每天 03:00，scheduled handler 调用共享 `JMService.clear_cache()`：

1. 请求缓存写锁；
2. 等待已有下载和上传释放读锁；
3. 写锁等待期间阻止新读者持续插队；
4. 通过 `asyncio.to_thread()` 执行 `shutil.rmtree()`，然后重新创建缓存根目录；
5. 操作返回后释放写锁，等待的普通请求继续进入并按需重建输出。

当前策略是“等待后清理”，不是“发现忙碌就跳过”。若未来改变清理策略，应创建新的 ADR，而不是依赖 `aiorwlock` 的内部等待队列。

## 线程与取消边界

同步的 jmcomic、文件验证和目录删除通过标准 `asyncio.to_thread()` 离开事件循环。项目不额外实现“任务取消后等待线程结束”的包装：

- 当前源码没有主动下载超时或 `Task.cancel()`；
- NoneBot 2.4.4 在 `CancelScope(shield=True)` 中运行 Matcher，正常停机不会在下载中途取消 handler；
- APScheduler 只会在调度器停机时取消定时任务，此时不会再接受新的下载；
- 强制结束进程或断电会直接终止线程，自定义协程包装同样无法保证缓存完整。

如果未来加入下载超时、主动取消或新的后台任务所有权，必须重新设计线程取消与锁释放语义，并补充对应 ADR 和测试；不能默认认为 `asyncio.to_thread()` 会停止已经运行的线程。

## 范围与维护提示

- 所有锁都是进程内锁；多个 Bot 进程共享同一缓存目录不受保护，当前明确不支持这种部署。
- 新增任何“准备文件后由外部消费者读取”的入口，都必须像现有 handler 一样持有 `cache_usage()` 到消费完成。
- 不要在定时 handler 中绕过 `JMService.clear_cache()` 直接删除缓存目录。
- 最终输出路径锁不协调不同输出共享的 `Bd_Pid` 图片目录；ZIP 必须保持 `delete_original_file: false`，由定时清理统一回收图片。
- 覆盖测试位于 [`test_cache_leases.py`](../../../tests/test_cache_leases.py)、[`test_output_cache.py`](../../../tests/units/test_output_cache.py) 和 [`test_jm_service.py`](../../../tests/units/test_jm_service.py)。
