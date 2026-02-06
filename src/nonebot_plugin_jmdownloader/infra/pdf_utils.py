"""PDF 处理工具"""

import random
import struct


def modify_pdf_md5(original_pdf_path: str, output_path: str) -> bool:
    """修改 PDF 文件的 MD5 值，但保持文件内容可用

    通过在文件末尾添加随机字节来改变 MD5。

    Args:
        original_pdf_path: 原始 PDF 文件路径
        output_path: 输出的 PDF 文件路径

    Returns:
        是否成功修改
    """
    try:
        # 读取原始 PDF
        with open(original_pdf_path, "rb") as f:
            content = f.read()

        # 生成随机字节
        random_bytes = struct.pack("d", random.random())

        # 添加随机注释到 PDF 末尾
        # PDF 规范允许在文件末尾添加注释，以 %%EOF 结尾
        # 我们在 %%EOF 之前添加随机内容作为注释
        if content.endswith(b"%%EOF"):
            # 如果 PDF 以 %%EOF 结尾，在它前面添加注释
            modified_content = (
                content[:-5] + b"\n% Random: " + random_bytes + b"\n%%EOF"
            )
        else:
            # 如果没有，直接在末尾添加注释和 EOF 标记
            modified_content = content + b"\n% Random: " + random_bytes + b"\n%%EOF"

        # 写入修改后的内容
        with open(output_path, "wb") as f:
            f.write(modified_content)

        return True
    except Exception:
        return False


async def modify_pdf_md5_async(original_pdf_path: str, output_path: str) -> bool:
    """异步版本的 modify_pdf_md5"""
    import asyncio

    return await asyncio.to_thread(modify_pdf_md5, original_pdf_path, output_path)


async def prepare_pdf_with_unique_md5(
    src_path: str,
    cache_dir: str,
    photo_id: str,
) -> str | None:
    """复制 PDF 并修改 MD5，生成唯一文件名

    Args:
        src_path: 源 PDF 文件路径
        cache_dir: 缓存目录
        photo_id: 用于生成文件名的 ID

    Returns:
        新文件路径，失败返回 None
    """
    import hashlib
    import random
    import time
    from pathlib import Path

    random_suffix = hashlib.md5(
        str(time.time() + random.random()).encode()
    ).hexdigest()[:8]
    dest_path = Path(cache_dir) / f"{photo_id}_{random_suffix}.pdf"

    if await modify_pdf_md5_async(src_path, str(dest_path)):
        return str(dest_path)
    return None
