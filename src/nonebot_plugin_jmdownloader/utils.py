import asyncio
import random
import struct
from io import BytesIO

import httpx
from jmcomic import (
    JmcomicClient,
    JmcomicException,
    JmDownloader,
    JmModuleConfig,
    JmPhotoDetail,
    JsonResolveFailException,
    MissingAlbumPhotoException,
    RequestRetryAllFailException,
)
from nonebot import logger
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    PrivateMessageEvent,
)
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot.rule import Rule
from PIL import Image, ImageFilter

from .data_source import data_manager


# region API与下载相关函数
def get_photo_info(client: JmcomicClient, photo_id):
    """获取章节信息和 Bot 要发送的消息"""
    try:
        photo = client.get_photo_detail(photo_id)
        return photo

    except MissingAlbumPhotoException as e:
        raise e

    except JsonResolveFailException as e:
        resp = e.resp
        logger.error(
            f"错误：解析 JSON 失败 (HTTP {resp.status_code})\n响应内容: {resp.text}"
        )

    except RequestRetryAllFailException:
        logger.error("错误：请求失败，已达最大重试次数。")

    except JmcomicException as e:
        logger.error(f"JMComic 发生未知错误: {e}")

    return None


async def get_photo_info_async(client: JmcomicClient, photo_id):
    return await asyncio.to_thread(get_photo_info, client, photo_id)


def download_photo(downloader: JmDownloader, photo: JmPhotoDetail):
    try:
        with downloader as dler:
            dler.download_by_photo_detail(photo)
        return True
    except JmcomicException as e:
        logger.error(f"JMComic 下载失败: {e}")
        return False


async def download_photo_async(downloader: JmDownloader, photo: JmPhotoDetail):
    return await asyncio.to_thread(download_photo, downloader, photo)


def search_album(client: JmcomicClient, search_query: str, page: int = 1):
    """搜索本子，支持指定页码"""
    try:
        jmpage = client.search_site(search_query=search_query, page=page)
        return jmpage

    except JsonResolveFailException as e:
        resp = e.resp
        logger.error(
            f"错误：解析 JSON 失败 (HTTP {resp.status_code})\n响应内容: {resp.text}"
        )

    except RequestRetryAllFailException:
        logger.error("错误：请求失败，已达最大重试次数。")

    except JmcomicException as e:
        logger.error(f"JMComic 发生未知错误: {e}")

    return None


async def search_album_async(client: JmcomicClient, search_query: str, page: int = 1):
    return await asyncio.to_thread(search_album, client, search_query, page)


async def download_avatar(photo_id: int | str) -> BytesIO | None:
    """下载本子封面"""
    for domain in JmModuleConfig.DOMAIN_IMAGE_LIST:
        url = f"https://{domain}/media/albums/{photo_id}.jpg"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=40)
                response.raise_for_status()

                if not response.content or len(response.content) < 1024:
                    logger.warning(f"{photo_id} 可能返回了错误页面，无法下载封面")
                    return None

                return BytesIO(response.content)

        except (httpx.HTTPStatusError, httpx.RequestError):
            continue

    logger.warning(f"{photo_id} 封面下载失败：所有域名不可用")
    return None


def blur_image(image_bytes: BytesIO) -> BytesIO:
    """对图片进行模糊处理"""
    image = Image.open(image_bytes)
    blurred_image = image.filter(ImageFilter.GaussianBlur(radius=7))

    output = BytesIO()
    blurred_image.save(output, format="JPEG")

    output.seek(0)

    return output


async def blur_image_async(image_bytes: BytesIO):
    return await asyncio.to_thread(blur_image, image_bytes)


# endregion


async def send_forward_message(bot: Bot, event: MessageEvent, messages: list):
    """发送合并消息"""
    if isinstance(event, GroupMessageEvent):
        await bot.call_api(
            "send_group_forward_msg", group_id=event.group_id, messages=messages
        )
    elif isinstance(event, PrivateMessageEvent):
        await bot.call_api(
            "send_private_forward_msg", user_id=event.user_id, messages=messages
        )


# region 权限相关
async def check_permission(
    bot: Bot, group_id: int, operator_id: int, target_id: int
) -> bool:
    """增减群黑名单权限检查，群主和超管拥有所有权限，管理员只能操作普通成员"""
    if str(operator_id) in bot.config.superusers:
        return True

    try:
        operator_info = await bot.get_group_member_info(
            group_id=group_id, user_id=operator_id
        )
        target_info = await bot.get_group_member_info(
            group_id=group_id, user_id=target_id
        )

        operator_role = operator_info.get("role")
        target_role = target_info.get("role")

        if operator_role == "owner":
            return True

        if operator_role == "admin":
            if target_role not in ["admin", "owner"]:
                return True

        return False

    except ActionFailed as e:
        logger.error(f"无法获取群成员信息：{e}")
        return False


async def user_not_in_blacklist(bot: Bot, event: MessageEvent) -> bool:
    """检查用户是否在群黑名单中"""
    if isinstance(event, GroupMessageEvent):
        group_id = event.group_id
        user_id = event.user_id

        if data_manager.is_user_blacklisted(group_id, user_id):
            return False

    return True


async def group_is_enabled(bot: Bot, event: MessageEvent) -> bool:
    """检查群是否启用插件功能"""
    if isinstance(event, GroupMessageEvent):
        group_id = event.group_id
        if not data_manager.is_group_enabled(group_id):
            return False

    return True


# endregion


def modify_pdf_md5(original_pdf_path, output_path):
    """
    修改PDF文件的MD5值，但保持文件内容可用
    通过在文件末尾添加随机字节来改变MD5

    Args:
        original_pdf_path: 原始PDF文件路径
        output_path: 输出的PDF文件路径

    Returns:
        bool: 是否成功修改
    """
    try:
        # 读取原始PDF
        with open(original_pdf_path, "rb") as f:
            content = f.read()

        # 生成随机字节
        random_bytes = struct.pack("d", random.random())

        # 添加随机注释到PDF末尾
        # PDF规范允许在文件末尾添加注释，以%%EOF结尾
        # 我们在%%EOF之前添加随机内容作为注释
        if content.endswith(b"%%EOF"):
            # 如果PDF以%%EOF结尾，在它前面添加注释
            modified_content = (
                content[:-5] + b"\n% Random: " + random_bytes + b"\n%%EOF"
            )
        else:
            # 如果没有，直接在末尾添加注释和EOF标记
            modified_content = content + b"\n% Random: " + random_bytes + b"\n%%EOF"

        # 写入修改后的内容
        with open(output_path, "wb") as f:
            f.write(modified_content)

        return True
    except Exception as e:
        logger.error(f"修改PDF MD5失败: {e}")
        return False


check_group_and_user = Rule(group_is_enabled) & Rule(user_not_in_blacklist)
