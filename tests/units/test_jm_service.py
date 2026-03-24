"""jm_service 单元测试"""

from __future__ import annotations

import sys
from typing import Any, cast

import pytest

jm_service_module = cast(
    Any, sys.modules["nonebot_plugin_jmdownloader.infra.jm_service"]
)
JMOptionContext = jm_service_module.JMOptionContext
JMService = jm_service_module.JMService


class DummyLogger:
    def __init__(self):
        self.exceptions: list[str] = []

    def exception(self, message: str):
        self.exceptions.append(message)


class DummyOption:
    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.build_calls = 0

    def build_jm_client(self):
        self.build_calls += 1
        if self.build_calls <= self.fail_times:
            raise OSError("network down")
        return object()


class TestOutputFormatValidation:
    def test_create_jm_option_rejects_unsupported_output_format(self):
        config = JMOptionContext(
            cache_dir="cache",
            output_format=cast(Any, "rar"),
        )

        with pytest.raises(ValueError, match="不支持的输出格式"):
            jm_service_module.create_jm_option(config)

    def test_constructor_rejects_unsupported_output_format(self):
        """JMService 内部调用 create_jm_option，同样会拒绝不支持的格式。"""
        config = JMOptionContext(
            cache_dir="cache",
            output_format=cast(Any, "rar"),
        )

        with pytest.raises(ValueError, match="不支持的输出格式"):
            JMService(config, logger=cast(Any, object()))

    def test_create_jm_option_preserves_album_filename_rule_as_string(self):
        config = JMOptionContext(cache_dir="cache")

        option = jm_service_module.create_jm_option(config, mode="album")

        plugin = option.plugins.after_album[0]
        assert plugin.kwargs.filename_rule == "{Aoutput_name}"
        assert isinstance(plugin.kwargs.filename_rule, str)


class TestDownloadPhoto:
    @pytest.mark.asyncio
    async def test_download_photo_raises_when_client_init_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        option = DummyOption(fail_times=1)
        logger = DummyLogger()

        monkeypatch.setattr(
            jm_service_module,
            "create_jm_option",
            lambda _config, mode="photo": option,
        )

        service = JMService(
            JMOptionContext(cache_dir="cache"), logger=cast(Any, logger)
        )
        photo = type("Photo", (), {"id": "123"})()

        with pytest.raises(OSError, match="network down"):
            await service.download_photo(cast(Any, photo))
        assert logger.exceptions == []


class TestPrepareAlbumFile:
    @pytest.mark.asyncio
    async def test_prepare_album_file_uses_selection_specific_output_name(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ):
        service = JMService(
            JMOptionContext(cache_dir=str(tmp_path)),
            logger=cast(Any, object()),
        )
        album = type("Album", (), {"id": "123"})()

        async def fake_download(received_album, episodes=None):
            output = tmp_path / (
                f"{service.get_album_output_name(received_album, episodes)}.pdf"
            )
            output.write_bytes(b"pdf")

        monkeypatch.setattr(service, "download_album", fake_download)

        result = await service.prepare_album_file(cast(Any, album), [0, 1, 2])

        assert result == (str(tmp_path / "album_123_ep_1-3.pdf"), ".pdf")
