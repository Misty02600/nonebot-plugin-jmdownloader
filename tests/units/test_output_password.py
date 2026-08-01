"""输出密码基础设施测试。"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from typing import Any, cast

import pikepdf
import pytest
import pyzipper

from nonebot_plugin_jmdownloader.core.enums import OutputFormat

output_password = cast(
    Any, sys.modules["nonebot_plugin_jmdownloader.infra.output_password"]
)


@pytest.mark.parametrize(
    ("template", "content_id", "expected"),
    [
        (None, 123, None),
        ("", 123, None),
        ("{id}", 123, "123"),
        ("jm-{id}", "456", "jm-456"),
        ("{id}-{id}", 7, "7-7"),
        ("fixed-{other}", 123, "fixed-{other}"),
        (" leading and trailing ", 123, " leading and trailing "),
    ],
)
def test_resolve_output_password(template, content_id, expected):
    assert output_password.resolve_output_password(template, content_id) == expected


def _write_pdf(path: Path, password: str | None) -> None:
    with pikepdf.new() as pdf:
        pdf.add_blank_page()
        if password is None:
            pdf.save(path)
        else:
            pdf.save(
                path,
                encryption=pikepdf.Encryption(user=password, owner=password),
            )


def _write_zip(path: Path, password: str | None) -> None:
    if password is None:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("content.txt", b"content")
        return

    with pyzipper.AESZipFile(path, "w", pyzipper.ZIP_DEFLATED) as archive:
        archive.setencryption(pyzipper.WZ_AES, nbits=128)
        archive.setpassword(password.encode())
        archive.writestr("content.txt", b"content")


@pytest.mark.parametrize("password", [None, "123", "含空格 password"])
def test_validate_pdf_matches_expected_password(tmp_path: Path, password: str | None):
    output = tmp_path / "test.pdf"
    _write_pdf(output, password)

    assert output_password.validate_output_file(output, OutputFormat.PDF, password)
    if password is None:
        assert not output_password.validate_output_file(
            output, OutputFormat.PDF, "unexpected"
        )
    else:
        assert not output_password.validate_output_file(output, OutputFormat.PDF, None)
        assert not output_password.validate_output_file(
            output, OutputFormat.PDF, "wrong"
        )


@pytest.mark.parametrize("password", [None, "123", "含空格 password"])
def test_validate_zip_matches_expected_password(tmp_path: Path, password: str | None):
    output = tmp_path / "test.zip"
    _write_zip(output, password)

    assert output_password.validate_output_file(output, OutputFormat.ZIP, password)
    if password is None:
        assert not output_password.validate_output_file(
            output, OutputFormat.ZIP, "unexpected"
        )
    else:
        assert not output_password.validate_output_file(output, OutputFormat.ZIP, None)
        assert not output_password.validate_output_file(
            output, OutputFormat.ZIP, "wrong"
        )


@pytest.mark.parametrize(
    ("output_format", "suffix"),
    [(OutputFormat.PDF, ".pdf"), (OutputFormat.ZIP, ".zip")],
)
def test_validate_output_rejects_corrupt_file(
    tmp_path: Path, output_format: OutputFormat, suffix: str
):
    output = tmp_path / f"corrupt{suffix}"
    output.write_bytes(b"not a valid output")

    assert not output_password.validate_output_file(output, output_format, None)


def test_validate_zip_rejects_empty_archive(tmp_path: Path):
    output = tmp_path / "empty.zip"
    with zipfile.ZipFile(output, "w"):
        pass

    assert not output_password.validate_output_file(output, OutputFormat.ZIP, None)
