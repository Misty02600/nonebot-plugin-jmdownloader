"""输出文件密码解析与实际文件验证。"""

from __future__ import annotations

import warnings
from pathlib import Path

import pikepdf
import pyzipper

from ..core.enums import OutputFormat


def resolve_output_password(template: str | None, content_id: str | int) -> str | None:
    if template is None or template == "":
        return None
    return template.replace("{id}", str(content_id))


def validate_output_file(
    output_path: str | Path,
    output_format: OutputFormat,
    password: str | None,
) -> bool:
    match output_format:
        case OutputFormat.PDF:
            return _validate_pdf(Path(output_path), password)
        case OutputFormat.ZIP:
            return _validate_zip(Path(output_path), password)
        case _:
            return False


def _validate_pdf(output_path: Path, password: str | None) -> bool:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with pikepdf.open(output_path, password=password or "") as pdf:
                return pdf.is_encrypted is (password is not None)
    except Exception:
        return False


def _read_first_zip_entry(output_path: Path, password: str | None) -> bool | None:
    with pyzipper.AESZipFile(output_path, "r") as archive:
        info = next((item for item in archive.infolist() if not item.is_dir()), None)
        if info is None:
            return None
        if password is not None:
            archive.setpassword(password.encode())
        with archive.open(info, "r") as entry:
            entry.read(1)
        return bool(info.flag_bits & 0x1)


def _validate_zip(output_path: Path, password: str | None) -> bool:
    try:
        encrypted = _read_first_zip_entry(output_path, password)
    except Exception:
        return False
    return encrypted is not None and encrypted is (password is not None)
