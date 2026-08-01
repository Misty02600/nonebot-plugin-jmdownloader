"""插件配置单元测试。"""

from __future__ import annotations

import sys
from typing import Any, cast

import pytest

config_module = cast(Any, sys.modules["nonebot_plugin_jmdownloader.config"])
PluginConfig = config_module.PluginConfig


class TestOutputPasswordConfig:
    def test_passwords_default_to_none(self):
        config = PluginConfig()

        assert config.jmcomic_zip_password is None
        assert config.jmcomic_pdf_password is None

    @pytest.mark.parametrize("field", ["jmcomic_zip_password", "jmcomic_pdf_password"])
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, None),
            ("", None),
            (123, "123"),
            (" fixed password ", " fixed password "),
            ("prefix-{id}", "prefix-{id}"),
        ],
    )
    def test_password_input_normalization(
        self, field: str, value: object, expected: str | None
    ):
        config = PluginConfig.model_validate({field: value})

        assert getattr(config, field) == expected
