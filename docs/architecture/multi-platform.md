# 跨平台边界

## 加载和适配器声明

插件入口先 `require("nonebot_plugin_alconna")` 和 `require("nonebot_plugin_uninfo")`，再导入它们的接口。`inherit_supported_adapters()` 取两者支持列表的交集，避免声明无法获取会话信息的平台。宿主负责安装和注册适配器，运行时依赖不强制安装 OneBot。

处理器和 `CommandArg()` 依赖使用 NoneBot 的 `Bot`、`Event`、`Message` 基类。`Uninfo` 提供用户、场景、成员与角色；群组/频道管理命令通过 `group_scene` rule 排除私聊，再由 `SUPERUSER` 或 `ADMIN()` 校验权限。不要在通用 handler 或其子依赖里重新引入 OneBot 专属事件注解，否则 NoneBot 会跳过其他平台的处理。

## 消息和文件

`bot/nonebot_utils.py` 集中负责平台发送差异：

- 查询、搜索构造 `UniMessage`，使用 `Image(raw=...)` 发送封面，不把机器人 ID 转成整数。
- 先尝试 `Reference` 和 `CustomNode` 合并转发；导出时出现 `SerializeFailed` 则逐条发送结果，避免把整页压成一条消息。发送 API 失败不会再次降级重发。
- 搜索进度保存 Alconna `Receipt`；仅在 `recallable` 时撤回，撤回 API 失败不改变业务结果。
- OneBot V11 保留 `upload_group_file`、`upload_private_file` 和 `folder_id`；其他平台使用 `File(path=..., name=...)`，并设置 `fallback=False`。不支持文件时明确失败，禁止发送文件路径或占位文本冒充成功。
- 单本、本子集各有一个通用下载 handler；`cache_usage()` 从文件准备前持有到发送完成，成功后才执行扣额 handler。下载失败、无法导出文件、上传失败都结束当前流程，不扣额度。

指定文件夹与禁言仅用于 OneBot V11，所有 QQ API 调用都在显式平台判断后执行。其他平台的普通成员违规时可加入当前场景黑名单；超管、管理员和角色未知的用户只阻止下载。手动黑名单操作必须确认目标角色低于操作者，查询失败或角色未知时取消操作。

目标用户优先从 Alconna 通用提及中读取 ID；若 `CommandArg()` 切片丢失实体，回读原始消息中的提及。Telegram 的普通 `@username` 没有数值 ID 时提示直接填写用户 ID，禁止将用户名作为 ID 入库。

## 状态隔离与兼容

`bot/session.py` 统一生成键，持久化模型无需知道平台信息：

| 状态 | 键的来源 |
| --- | --- |
| OneBot V11 群配置、额度 | 继续使用原始群号、用户 ID，兼容已有 JSON |
| 其他平台群配置 | adapter、scope、platform、完整父子场景 ID 列表 |
| 其他平台额度 | adapter、scope、platform、用户 ID |
| 所有平台搜索会话 | adapter、scope、platform、机器人 ID、场景类型、完整父子场景、用户 ID |

非历史键采用 JSON 编码后生成带类别前缀的 SHA-256，避免平台 ID 中的冒号、斜杠等成为文件路径。黑名单内部保存当前平台的原始用户 ID，便于生成通用 @ 消息。群配置和用户额度可在同平台的机器人间共享，搜索会话不共享。全局受限 jm 号与 tag 仍对所有平台生效。

批量群开关命令只解释当前平台的 ID；频道和话题可使用 `父场景ID/场景ID`，多级父场景按从外到内的顺序填写。`开启jm` 直接使用当前完整场景。

## 验证入口与依据

- [`tests/bot/test_cross_platform.py`](../../tests/bot/test_cross_platform.py)：真实 OneBot V11、Telegram、Discord 事件，通过 NoneBug 运行响应器和 Alconna 导出；平台 API 与 JM 请求使用替代实现，检查查询、翻页、单本/本子集、上传租约、失败扣额、开关和权限。
- [`tests/bot/test_loading.py`](../../tests/bot/test_loading.py)：子进程禁止导入 OneBot，验证 Telegram 宿主仍能完整加载插件。
- [NoneBot 跨平台规范](https://nonebot.dev/docs/best-practice/multi-adapter)、[插件发布规范](https://nonebot.dev/docs/developer/plugin-publishing)。
- [Alconna 通用消息](https://nonebot.dev/docs/best-practice/alconna/uniseg/message)、[消息段](https://nonebot.dev/docs/best-practice/alconna/uniseg/segment)、[Uninfo 接口](https://github.com/RF-Tar-Railt/nonebot-plugin-uninfo#使用)。

这些测试不连接真实平台账号；实际文件大小、上传权限和平台限流由部署环境决定。
