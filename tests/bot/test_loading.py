import os
import subprocess
import sys
from pathlib import Path


def test_plugin_loads_without_onebot(tmp_path):
    """禁止导入 OneBot，验证 Telegram 宿主仍能完整注册插件。"""
    source = Path(__file__).resolve().parents[2] / "src"
    script = """
import importlib.abc
import sys

class BlockOneBot(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("nonebot.adapters.onebot"):
            raise ModuleNotFoundError(fullname, name=fullname)

sys.meta_path.insert(0, BlockOneBot())
import nonebot
from nonebot.adapters.telegram import Adapter
nonebot.init(driver="~fastapi+~httpx", localstore_use_cwd=True)
nonebot.get_driver().register_adapter(Adapter)
plugin = nonebot.load_plugin("nonebot_plugin_jmdownloader")
assert plugin is not None
assert "nonebot.adapters.telegram" in plugin.metadata.supported_adapters
assert "nonebot.adapters.onebot.v11" not in sys.modules
assert len(plugin.matcher) >= 10
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(source)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
