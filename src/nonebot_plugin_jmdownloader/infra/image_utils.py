"""图片处理工具"""

import asyncio
from io import BytesIO

from PIL import Image, ImageFilter


def _blur_image(image_bytes: BytesIO) -> BytesIO:
    """对图片进行模糊处理

    Args:
        image_bytes: 图片的 BytesIO

    Returns:
        模糊处理后的图片 BytesIO
    """
    image = Image.open(image_bytes)
    blurred_image = image.filter(ImageFilter.GaussianBlur(radius=7))

    output = BytesIO()
    blurred_image.save(output, format="JPEG")

    output.seek(0)

    return output


async def blur_image_async(image_bytes: BytesIO) -> BytesIO:
    """异步对图片进行模糊处理

    Args:
        image_bytes: 图片的 BytesIO

    Returns:
        模糊处理后的图片 BytesIO
    """
    return await asyncio.to_thread(_blur_image, image_bytes)
