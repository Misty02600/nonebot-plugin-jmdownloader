"""JMComic option 构造测试。"""

from __future__ import annotations

import sys
from typing import Any, cast

import pytest

from nonebot_plugin_jmdownloader.core.enums import OutputFormat

jm_option = cast(Any, sys.modules["nonebot_plugin_jmdownloader.infra.jm_option"])
JMOptionContext = jm_option.JMOptionContext


def _plugin_kwargs(option, mode: str):
    hook = "after_photo" if mode == "photo" else "after_album"
    return option.plugins.get(hook)[0]["kwargs"]


class TestOutputFormatValidation:
    def test_create_jm_option_rejects_unsupported_output_format(self):
        config = JMOptionContext(
            cache_dir="cache",
            output_format=cast(Any, "rar"),
        )

        with pytest.raises(ValueError, match="不支持的输出格式"):
            jm_option.create_jm_option(config)

    def test_create_jm_option_preserves_album_filename_rule_as_string(self):
        config = JMOptionContext(cache_dir="cache")

        option = jm_option.create_jm_option(config, mode="album")

        plugin = option.plugins.after_album[0]
        assert plugin.kwargs.filename_rule == "{Aoutput_name}"
        assert isinstance(plugin.kwargs.filename_rule, str)

    @pytest.mark.parametrize("mode", ["photo", "album"])
    def test_zip_option_preserves_source_images(self, mode: str):
        config = JMOptionContext(
            cache_dir="cache",
            output_format=OutputFormat.ZIP,
        )

        option = jm_option.create_jm_option(config, mode=cast(Any, mode))

        assert _plugin_kwargs(option, mode)["delete_original_file"] is False


class TestRequestOption:
    @pytest.mark.parametrize("mode", ["photo", "album"])
    @pytest.mark.parametrize("output_format", list(OutputFormat))
    def test_request_option_receives_password_without_mutating_base(
        self, mode: str, output_format: OutputFormat
    ):
        config = JMOptionContext(cache_dir="cache", output_format=output_format)
        base = jm_option.create_jm_option(config, mode=mode)

        request = jm_option.copy_option_with_password(
            base, mode, output_format, "resolved-123"
        )

        assert _plugin_kwargs(request, mode)["encrypt"] == {"password": "resolved-123"}
        assert "encrypt" not in _plugin_kwargs(base, mode)

    def test_request_option_removes_encrypt_when_password_is_disabled(self):
        config = JMOptionContext(cache_dir="cache", output_format=OutputFormat.ZIP)
        base = jm_option.create_jm_option(config)
        _plugin_kwargs(base, "photo")["encrypt"] = {"password": "base"}

        request = jm_option.copy_option_with_password(
            base, "photo", OutputFormat.ZIP, None
        )

        assert "encrypt" not in _plugin_kwargs(request, "photo")
        assert _plugin_kwargs(base, "photo")["encrypt"] == {"password": "base"}
