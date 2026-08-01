"""jm_service 单元测试。"""

from __future__ import annotations

import asyncio
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, cast

import pikepdf
import pytest
import pyzipper

from nonebot_plugin_jmdownloader.core.enums import OutputFormat

jm_service_module = cast(
    Any, sys.modules["nonebot_plugin_jmdownloader.infra.jm_service"]
)
jm_option_module = cast(Any, sys.modules["nonebot_plugin_jmdownloader.infra.jm_option"])
output_password = cast(
    Any, sys.modules["nonebot_plugin_jmdownloader.infra.output_password"]
)
JMOptionContext = jm_option_module.JMOptionContext
JMService = jm_service_module.JMService


class DummyLogger:
    def __init__(self):
        self.errors: list[str] = []
        self.exceptions: list[str] = []

    def error(self, message: str):
        self.errors.append(message)

    def exception(self, message: str):
        self.exceptions.append(message)

    def info(self, _message: str):
        pass

    def warning(self, _message: str):
        pass


def _plugin_kwargs(option, mode: str):
    hook = "after_photo" if mode == "photo" else "after_album"
    return option.plugins.get(hook)[0]["kwargs"]


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


def _write_output(
    path: Path, output_format: OutputFormat, password: str | None
) -> None:
    if output_format == OutputFormat.PDF:
        _write_pdf(path, password)
    else:
        _write_zip(path, password)


class TestConstruction:
    def test_constructor_rejects_unsupported_output_format(self):
        config = JMOptionContext(
            cache_dir="cache",
            output_format=cast(Any, "rar"),
        )

        with pytest.raises(ValueError, match="不支持的输出格式"):
            JMService(config, logger=cast(Any, DummyLogger()))


class TestRequestOptionIsolation:
    @pytest.mark.asyncio
    async def test_concurrent_ids_use_isolated_passwords(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        captured: dict[str, str] = {}

        class FakeDownloader:
            def __init__(self, option):
                self.option = option

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def download_by_photo_detail(self, photo):
                time.sleep(0.02)
                captured[str(photo.id)] = _plugin_kwargs(self.option, "photo")[
                    "encrypt"
                ]["password"]

        monkeypatch.setattr(jm_service_module, "JmDownloader", FakeDownloader)
        service = JMService(
            JMOptionContext(
                cache_dir=str(tmp_path),
                output_format=OutputFormat.ZIP,
                zip_password="zip-{id}",
            ),
            logger=cast(Any, DummyLogger()),
        )
        photos = [type("Photo", (), {"id": value})() for value in ("123", "456")]

        await asyncio.gather(
            *(service.download_photo(cast(Any, photo)) for photo in photos)
        )

        assert captured == {"123": "zip-123", "456": "zip-456"}
        assert "encrypt" not in _plugin_kwargs(service._photo_option, "photo")


class TestDownload:
    @pytest.mark.asyncio
    async def test_download_photo_raises_when_client_init_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        config = JMOptionContext(cache_dir="cache")
        option = jm_service_module.create_jm_option(config)

        def fail_build_client():
            raise OSError("network down")

        monkeypatch.setattr(option, "build_jm_client", fail_build_client)
        monkeypatch.setattr(
            jm_service_module,
            "create_jm_option",
            lambda _config, mode="photo": option,
        )
        service = JMService(config, logger=cast(Any, DummyLogger()))
        photo = type("Photo", (), {"id": "123"})()

        with pytest.raises(OSError, match="network down"):
            await service.download_photo(cast(Any, photo))

    @pytest.mark.asyncio
    async def test_download_album_does_not_mutate_shared_album(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        captured: list[Any] = []
        captured_options: list[Any] = []

        class FakeDownloader:
            def __init__(self, option):
                self.option = option

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def download_by_album_detail(self, album):
                captured.append(album)
                captured_options.append(self.option)

        monkeypatch.setattr(jm_service_module, "JmDownloader", FakeDownloader)
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path), pdf_password="{id}"),
            logger=cast(Any, DummyLogger()),
        )
        original_episodes = [object(), object(), object()]
        album = type("Album", (), {"id": "123", "episode_list": original_episodes})()

        await service.download_album(cast(Any, album), [0, 2])

        assert album.episode_list == original_episodes
        assert captured[0] is not album
        assert captured[0].episode_list == [original_episodes[0], original_episodes[2]]
        assert captured[0].output_name == "album_123_ep_1_3"
        assert _plugin_kwargs(captured_options[0], "album")["encrypt"] == {
            "password": "123"
        }
        assert "encrypt" not in _plugin_kwargs(service._album_option, "album")


class TestPrepareOutput:
    @pytest.mark.asyncio
    async def test_prepare_album_file_uses_album_id_and_selection_output_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path), pdf_password="album-{id}"),
            logger=cast(Any, DummyLogger()),
        )
        album = type("Album", (), {"id": "123"})()

        async def fake_download(received_album, episodes=None):
            output = tmp_path / (
                f"{service.get_album_output_name(received_album, episodes)}.pdf"
            )
            _write_pdf(output, "album-123")

        monkeypatch.setattr(service, "download_album", fake_download)

        result = await service.prepare_album_file(cast(Any, album), [0, 1, 2])

        expected = tmp_path / "album_123_ep_1-3.pdf"
        assert result == (str(expected), ".pdf")
        assert output_password.validate_output_file(
            expected, OutputFormat.PDF, "album-123"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("output_format", list(OutputFormat))
    async def test_valid_cache_is_reused(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        output_format: OutputFormat,
    ):
        password = "password-{id}"
        service = JMService(
            JMOptionContext(
                cache_dir=str(tmp_path),
                output_format=output_format,
                pdf_password=password,
                zip_password=password,
            ),
            logger=cast(Any, DummyLogger()),
        )
        photo = type("Photo", (), {"id": "123"})()
        calls = 0

        async def fake_download(_photo):
            nonlocal calls
            calls += 1
            _write_output(
                tmp_path / f"123{output_format.ext}", output_format, "password-123"
            )

        monkeypatch.setattr(service, "download_photo", fake_download)

        first = await service.prepare_photo_file(cast(Any, photo))
        second = await service.prepare_photo_file(cast(Any, photo))

        assert (
            first
            == second
            == (str(tmp_path / f"123{output_format.ext}"), output_format.ext)
        )
        assert calls == 1

    @pytest.mark.asyncio
    async def test_password_change_rebuilds_only_on_next_prepare(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        photo = type("Photo", (), {"id": "123"})()
        first_service = JMService(
            JMOptionContext(cache_dir=str(tmp_path), pdf_password="first"),
            logger=cast(Any, DummyLogger()),
        )

        async def first_download(_photo):
            _write_pdf(tmp_path / "123.pdf", "first")

        monkeypatch.setattr(first_service, "download_photo", first_download)
        await first_service.prepare_photo_file(cast(Any, photo))

        second_service = JMService(
            JMOptionContext(cache_dir=str(tmp_path), pdf_password="second"),
            logger=cast(Any, DummyLogger()),
        )
        calls = 0

        async def second_download(_photo):
            nonlocal calls
            calls += 1
            _write_pdf(tmp_path / "123.pdf", "second")

        monkeypatch.setattr(second_service, "download_photo", second_download)

        assert output_password.validate_output_file(
            tmp_path / "123.pdf", OutputFormat.PDF, "first"
        )
        result = await second_service.prepare_photo_file(cast(Any, photo))

        assert result == (str(tmp_path / "123.pdf"), ".pdf")
        assert calls == 1
        assert output_password.validate_output_file(
            tmp_path / "123.pdf", OutputFormat.PDF, "second"
        )

    @pytest.mark.asyncio
    async def test_invalid_cached_file_is_regenerated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path), pdf_password="{id}"),
            logger=cast(Any, DummyLogger()),
        )
        photo = type("Photo", (), {"id": "123"})()
        output = tmp_path / "123.pdf"
        _write_pdf(output, None)
        calls = 0

        async def fake_download(_photo):
            nonlocal calls
            calls += 1
            _write_pdf(output, "123")

        monkeypatch.setattr(service, "download_photo", fake_download)

        result = await service.prepare_photo_file(cast(Any, photo))

        assert result == (str(output), ".pdf")
        assert calls == 1
        assert output_password.validate_output_file(output, OutputFormat.PDF, "123")

    @pytest.mark.asyncio
    async def test_existing_valid_output_is_reused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path)),
            logger=cast(Any, DummyLogger()),
        )
        photo = type("Photo", (), {"id": "123"})()
        output = tmp_path / "123.pdf"
        _write_pdf(output, None)
        calls = 0

        async def fake_download(_photo):
            nonlocal calls
            calls += 1
            _write_pdf(output, None)

        monkeypatch.setattr(service, "download_photo", fake_download)

        result = await service.prepare_photo_file(cast(Any, photo))

        assert result == (str(output), ".pdf")
        assert calls == 0

    @pytest.mark.asyncio
    async def test_missing_output_after_download_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        logger = DummyLogger()
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path)),
            logger=cast(Any, logger),
        )
        photo = type("Photo", (), {"id": "123"})()

        async def fake_download(_photo):
            pass

        monkeypatch.setattr(service, "download_photo", fake_download)

        result = await service.prepare_photo_file(cast(Any, photo))

        assert result is None
        assert logger.errors

    @pytest.mark.asyncio
    async def test_plaintext_output_is_rejected_when_password_is_required(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        logger = DummyLogger()
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path), pdf_password="{id}"),
            logger=cast(Any, logger),
        )
        photo = type("Photo", (), {"id": "123"})()
        output = tmp_path / "123.pdf"

        async def fake_download(_photo):
            _write_pdf(output, None)

        monkeypatch.setattr(service, "download_photo", fake_download)

        result = await service.prepare_photo_file(cast(Any, photo))

        assert result is None
        assert not output.exists()
        assert logger.errors

    @pytest.mark.asyncio
    async def test_same_output_concurrency_downloads_once(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path)),
            logger=cast(Any, DummyLogger()),
        )
        photo = type("Photo", (), {"id": "123"})()
        calls = 0

        async def fake_download(_photo):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.03)
            _write_pdf(tmp_path / "123.pdf", None)

        monkeypatch.setattr(service, "download_photo", fake_download)

        first, second = await asyncio.gather(
            service.prepare_photo_file(cast(Any, photo)),
            service.prepare_photo_file(cast(Any, photo)),
        )

        assert first == second == (str(tmp_path / "123.pdf"), ".pdf")
        assert calls == 1
        assert service._output_cache._output_locks == {}

    @pytest.mark.asyncio
    async def test_different_outputs_can_prepare_concurrently(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path)),
            logger=cast(Any, DummyLogger()),
        )
        active = 0
        max_active = 0

        async def fake_download(photo):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.03)
            _write_pdf(tmp_path / f"{photo.id}.pdf", None)
            active -= 1

        monkeypatch.setattr(service, "download_photo", fake_download)
        photos = [type("Photo", (), {"id": value})() for value in ("123", "456")]

        await asyncio.gather(
            *(service.prepare_photo_file(cast(Any, photo)) for photo in photos)
        )

        assert max_active == 2
        assert service._output_cache._output_locks == {}

    @pytest.mark.asyncio
    @pytest.mark.parametrize("password_template", [None, "{id}"])
    async def test_modify_md5_copy_preserves_password(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        password_template: str | None,
    ):
        service = JMService(
            JMOptionContext(
                cache_dir=str(tmp_path),
                pdf_password=password_template,
                modify_md5=True,
            ),
            logger=cast(Any, DummyLogger()),
        )
        photo = type("Photo", (), {"id": "123"})()
        password = "123" if password_template else None

        async def fake_download(_photo):
            _write_pdf(tmp_path / "123.pdf", password)

        monkeypatch.setattr(service, "download_photo", fake_download)

        result = await service.prepare_photo_file(cast(Any, photo))

        assert result is not None
        modified_path, ext = result
        assert ext == ".pdf"
        assert Path(modified_path) != tmp_path / "123.pdf"
        assert output_password.validate_output_file(
            modified_path, OutputFormat.PDF, password
        )


class TestWarmup:
    @pytest.mark.asyncio
    async def test_warmup_reports_failure(self, monkeypatch: pytest.MonkeyPatch):
        service = JMService(
            JMOptionContext(cache_dir="cache"),
            logger=cast(Any, logger := DummyLogger()),
        )

        def fail_client():
            raise OSError("network down")

        monkeypatch.setattr(service, "_get_client", fail_client)

        assert await service.warmup() is False
        assert logger.exceptions == []
