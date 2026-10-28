"""通用消息发送，以及仅 OneBot V11 提供的文件夹上传能力。"""

from pathlib import Path

from nonebot import logger
from nonebot.adapters import Bot, Event
from nonebot.exception import ActionFailed, NetworkError
from nonebot_plugin_alconna import CustomNode, File, Reference, UniMessage
from nonebot_plugin_alconna.uniseg import Receipt, SerializeFailed
from nonebot_plugin_uninfo import Session

from .session import is_onebot_v11


async def send_forward_msg(
    bot: Bot, event: Event, messages: list[UniMessage], title: str
):
    """优先合并转发；不支持时逐条发送，保留结果边界。"""
    if not messages:
        return
    nodes = [CustomNode(bot.self_id, title, message) for message in messages]
    try:
        await UniMessage(Reference(nodes=nodes)).send(
            target=event, bot=bot, fallback=False
        )
    except SerializeFailed:
        for message in messages:
            await message.send(target=event, bot=bot)


async def recall_progress(receipt: Receipt) -> None:
    """进度消息撤回失败不影响已经完成的业务操作。"""
    if receipt.recallable:
        try:
            await receipt.recall()
        except (ActionFailed, NetworkError):
            logger.debug("无法撤回搜索进度消息")


async def send_file(
    bot: Bot,
    event: Event,
    session: Session,
    path: str,
    name: str,
    folder_id: str | None = None,
) -> None:
    """上传真实文件；禁止把不支持的 File 消息降级为文本。"""
    if is_onebot_v11(session):
        if session.scene.is_private:
            await bot.call_api(
                "upload_private_file",
                user_id=int(session.user.id),
                file=path,
                name=name,
            )
        else:
            params = {"group_id": int(session.scene.id), "file": path, "name": name}
            if folder_id:
                params["folder_id"] = folder_id
            await bot.call_api("upload_group_file", **params)
    else:
        await UniMessage(File(path=Path(path), name=name)).send(
            target=event, bot=bot, fallback=False
        )
