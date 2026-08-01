# 输出准备与密码流程

## 目的

`prepare_photo_file()` 和 `prepare_album_file()` 只返回真实存在、加密状态符合当前配置且能用当前密码打开的 PDF 或 ZIP。配置改变时不扫描历史缓存，而是在目标文件下一次准备发送时验证并按需重建。

入口位于 [`JMService`](../../../src/nonebot_plugin_jmdownloader/infra/jm_service.py)，缓存编排位于 [`OutputCache`](../../../src/nonebot_plugin_jmdownloader/infra/output_cache.py)，密码解析和格式验证位于 [`output_password.py`](../../../src/nonebot_plugin_jmdownloader/infra/output_password.py)。

## 参与者

| 参与者 | 职责 |
|---|---|
| 下载 handler | 取得缓存共享租约，调用准备方法，并在租约释放前上传返回路径 |
| `JMService` | 计算目标路径、解析请求密码、构造请求 downloader，并执行可选 PDF 后处理 |
| `OutputCache` | 串行化同路径准备，决定复用或重建，并清理无效输出 |
| jmcomic 输出插件 | 收集图片并生成 PDF/ZIP；存在 `encrypt.password` 时执行加密 |
| `output_password.py` | 字面替换 `{id}`，并实际打开输出验证密码与加密状态 |
| `pdf_utils.py` | 可选地从已验证 PDF 生成内容等价但 MD5 不同的副本 |

## 主流程

```text
handler 取得缓存共享租约
  │
  ├─ JMService 计算输出路径并解析当前密码
  ├─ OutputCache 获取最终输出路径锁
  │    ├─ 用当前密码实际验证现有输出
  │    │    └─ 成功：直接复用
  │    └─ 验证失败：删除旧输出
  │         ├─ 复制基础 option 并隔离插件树
  │         ├─ 设置或移除本次 encrypt.password
  │         ├─ 调用 jmcomic 生成输出
  │         └─ 实际验证新 PDF/ZIP
  │
  ├─ PDF 且启用 modify_md5？
  │    ├─ 生成唯一 MD5 副本
  │    ├─ 再次验证副本密码状态
  │    └─ 返回副本路径
  │
  ├─ OneBot 上传返回的路径
  └─ 上传结束后释放缓存共享租约
```

## 密码解析

当前输出格式只读取自己的配置：PDF 使用 `jmcomic_pdf_password`，ZIP 使用 `jmcomic_zip_password`。

- `None` 或空字符串：不加密；
- 固定字符串：直接作为密码；
- 包含 `{id}`：把所有字面 `{id}` 替换为当前对象 ID；
- 其他花括号保持原样，不使用 Python `format()`。

单本使用 `photo.id`。本子集无论下载全部还是选择部分章节，都使用 `album.id`；章节选择只改变内容和输出文件名。

## 请求 option 与共享状态

`JMService` 构造稳定的 photo/album 基础 option，基础 option 不携带请求密码。每次下载：

1. 对对应基础 option 调用 `copy_option()`；
2. 显式深拷贝 `base_option.plugins.src_dict`；
3. 在 `after_photo` 或 `after_album` 输出插件中设置或移除 `encrypt`；
4. downloader 使用基础 option 创建 client，再切换到请求 option 执行插件。

当前上游 `copy_option()` 会让嵌套插件字典继续共享，因此显式深拷贝是请求隔离的一部分。ZIP 插件还必须设置 `delete_original_file: false`，避免内容重叠的请求在打包后删除共享图片；图片由每日缓存清理统一回收。

## 实际文件验证与缓存失效

缓存不保存额外 sidecar，也不依赖配置指纹。当前密码本身就是缓存验证输入：

- 加密 PDF：用当前密码打开，并要求 `is_encrypted` 为真；
- 未加密 PDF：无密码打开，并要求 `is_encrypted` 为假；
- ZIP：读取第一个非目录条目的一个字节，并要求条目的加密位与“是否配置密码”一致；
- 空归档、错误格式、错误密码或无法读取都视为无效。

因此密码变化、从有密码切换到无密码、从无密码切换到有密码，以及损坏文件，都会在下一次准备时验证失败并触发重建。相同密码下只要文件仍符合当前状态即可复用；本功能不为加密实现版本变化单独强制刷新缓存。

验证失败时删除目标输出并返回失败，不会降级发送明文。多个相同路径请求由同一把锁串行化；等待者进入后重新验证，通常直接复用前一个请求刚生成的文件。

## PDF 修改 MD5

开启 `jmcomic_modify_real_md5` 时，基础 PDF 先完成密码验证，再生成唯一 MD5 副本。副本必须用同一密码规则再次验证后才能返回，因为后处理直接修改 PDF 字节；副本不参与基础缓存复用，由每日清理统一回收。

## 失败边界

- 下载插件未生成目标文件：记录明确错误并返回失败；
- 新输出验证失败：删除目标并返回失败；
- MD5 副本生成或复验失败：不返回副本；
- 准备方法返回 `None`：下载 handler 结束当前流程，不上传目标文件。

OneBot 上传和下载额度仍属于 handler 层，JM 服务不依赖消息协议或用户策略；缓存租约必须跨过服务返回边界持续到上传结束。

## 维护与测试入口

- 模板或格式验证：[`test_output_password.py`](../../../tests/units/test_output_password.py)；
- option 复制、缓存失效、并发或 MD5：[`test_jm_option.py`](../../../tests/units/test_jm_option.py) 与 [`test_jm_service.py`](../../../tests/units/test_jm_service.py)；
- 缓存读写锁：[`test_output_cache.py`](../../../tests/units/test_output_cache.py)；
- 上传租约边界：[`test_cache_leases.py`](../../../tests/test_cache_leases.py)；
- 配置默认值和空字符串：[`test_config.py`](../../../tests/units/test_config.py)。
