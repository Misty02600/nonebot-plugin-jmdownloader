"""
units 测试目录的 conftest.py

为不依赖完整 NoneBot 环境的单元测试提供模块导入支持。
通过修改 sys.path 和使用 importlib 直接导入子模块，绕过主包 __init__.py。
"""

import sys
from pathlib import Path

import pytest

# 将 src 目录添加到 sys.path，但作为独立模块导入
_src_path = Path(__file__).parents[2] / "src" / "nonebot_plugin_jmdownloader"

# 不初始化 NoneBot，而是直接使用 importlib 导入需要的模块
# 这些模块会被放入 sys.modules 中供测试使用


def import_module_directly(module_name: str, subpath: str):
    """直接导入模块文件，不触发包的 __init__.py"""
    import importlib.util

    module_path = _src_path / subpath
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# 预导入纯核心模块（不依赖 NoneBot）
# 这些在测试收集之前就需要可用
import_module_directly(
    "nonebot_plugin_jmdownloader.core.search_session", "core/search_session.py"
)
import_module_directly(
    "nonebot_plugin_jmdownloader.core.data_models", "core/data_models.py"
)
# infra 模块依赖 core 模块，所以需要在 core 之后导入
import_module_directly(
    "nonebot_plugin_jmdownloader.infra.search_session", "infra/search_session.py"
)


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init():
    """覆盖根目录的 fixture，不执行任何初始化"""
    pass
