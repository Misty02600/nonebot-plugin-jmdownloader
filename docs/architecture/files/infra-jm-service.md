# `infra/jm_service.py` 文件导读

源码：[`src/nonebot_plugin_jmdownloader/infra/jm_service.py`](../../../src/nonebot_plugin_jmdownloader/infra/jm_service.py)

## 看完先记住

`JMService` 是 handler 面向 JM 能力的异步门面。它负责把对象 ID、输出路径、请求密码、jmcomic downloader 和 PDF 后处理连接起来；option 构造、缓存并发和文件验证已分别下沉到专门模块，不应重新堆回服务类。

## 关键区域

| 区域或符号 | 作用 | 为什么重要 |
|---|---|---|
| `build_album_output_name()` | 为完整或部分本子集生成稳定输出名 | 同时影响缓存 key 和 OneBot 上传文件名 |
| `JMService.__init__()` | 创建 photo/album 基础 option 与共享 `OutputCache` | 服务级对象不能携带请求专属密码 |
| `cache_usage()`、`clear_cache()` | 把缓存共享租约和独占清理暴露给 handler/定时任务 | 租约必须覆盖准备到上传完整区间 |
| `_resolve_password()` | 按当前输出格式选择模板并替换 `{id}` | photo 和 album 使用不同对象 ID 语义 |
| `_create_request_downloader()` | 创建请求 option，并让 downloader 使用本次插件参数 | 避免并发请求污染基础 option |
| `download_photo()`、`download_album()` | 在线程中调用同步 jmcomic downloader | album 使用副本承载章节选择，不能改写传入对象 |
| `prepare_photo_file()`、`prepare_album_file()` | 委托缓存准备，执行可选 MD5 后处理并返回上传路径 | 只返回经过实际格式验证的文件 |
| 查询、搜索和封面方法 | 封装同步 JM API 与异步 HTTP 请求 | handler 不直接依赖 jmcomic client 细节 |

## 它和其他文件怎么配合

```text
bot/dependencies.py
  └─ 构造 JMOptionContext 和共享 JMService
       ├─ jm_option.py：基础 option 与请求密码副本
       ├─ output_cache.py：读写锁、同路径锁、复用和重建
       ├─ output_password.py：模板解析和 PDF/ZIP 实际验证
       ├─ pdf_utils.py：可选唯一 MD5 PDF
       ├─ bot/handlers/download.py：持有缓存租约完成准备和上传
       └─ bot/handlers/scheduled.py：通过独占入口清理缓存
```

`JMService` 不导入 NoneBot event、matcher、permission、OneBot bot 或 `DataManager`。这些职责留在 `bot/`，使输出准备逻辑能独立测试。

## 必须保持的不变量

### 请求密码不能写入基础 option

`_photo_option` 和 `_album_option` 是共享对象。请求密码只能进入 `copy_option_with_password()` 返回的 option。当前 jmcomic `copy_option()` 会共享嵌套的 `plugins.src_dict`，所以 [`jm_option.py`](../../../src/nonebot_plugin_jmdownloader/infra/jm_option.py) 中的显式深拷贝不能省略。

### photo 与 album 的差异集中处理

- photo 使用 `after_photo`，输出名为 `photo.id`；
- album 使用 `after_album`，基础名为 `album_<album.id>`；
- 部分章节只改变 album 副本及输出名，密码仍使用 `album.id`；
- ZIP 保留源图片，避免内容重叠请求相互删除。

新增输出模式时，先扩展 `OutputFormat`、jmcomic 插件块和真实文件验证器，再接入共享缓存流程。

### 缓存租约跨越服务返回边界

`OutputCache.prepare()` 的同路径锁只覆盖文件准备，无法保护已经返回给 OneBot 的路径。因此生产 handler 必须在调用 `prepare_*_file()` 前取得 `cache_usage()`，并持有到上传 API 返回。定时清理只能调用 `clear_cache()` 获取写锁，不能直接删除目录。

### 返回路径必须经过实际验证

缓存复用和新下载都使用当前密码实际打开 PDF/ZIP。密码或加密开关改变会自然导致旧文件验证失败并重建，不需要 sidecar。开启 MD5 修改时，新副本也必须再次验证。

## 修改时要注意什么

| 想修改 | 至少检查 |
|---|---|
| 登录、代理、线程或缓存目录 | `JMOptionContext`、`create_jm_option()`、依赖组装和 README |
| PDF/ZIP 插件参数 | `jm_option.py`、真实文件验证和上游 jmcomic 版本 |
| 密码模板 | `_resolve_password()`、`output_password.py`、配置模型和 README |
| album 章节输出名 | `build_album_output_name()`、上传显示名和缓存碰撞测试 |
| 缓存复用或并发 | `output_cache.py`、下载 handler、两个 runtime flow |
| 下载超时或主动取消 | `asyncio.to_thread()`、两层锁和 [ADR-0002](../../adr/0002-coordinate-cache-with-runtime-locks.md)；必须重新定义取消语义 |
| PDF MD5 | 两个 prepare 方法和加密/未加密组合测试 |
| jmcomic 版本 | `copy_option()` 嵌套复制、插件 hook/kwargs 和 client 行为 |

## 测试入口

- [`test_jm_service.py`](../../../tests/units/test_jm_service.py)：服务编排、缓存失效、并发、album 命名和 MD5；
- [`test_jm_option.py`](../../../tests/units/test_jm_option.py)：插件块、请求 option 和深拷贝隔离；
- [`test_output_cache.py`](../../../tests/units/test_output_cache.py)：读写锁与清理；
- [`test_output_password.py`](../../../tests/units/test_output_password.py)：模板和真实 PDF/ZIP 验证；
- [`test_cache_leases.py`](../../../tests/test_cache_leases.py)：四条 handler 的准备到上传租约；
- [`test_dependencies.py`](../../../tests/test_dependencies.py)、[`test_config.py`](../../../tests/units/test_config.py)：配置组装与默认值。

完整状态顺序见 [输出准备与密码流程](../flows/output-preparation.md)，缓存所有权见 [缓存使用与清理流程](../flows/cache-lifecycle.md)。
