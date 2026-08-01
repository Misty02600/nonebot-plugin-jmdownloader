"""JMComic option 构造与请求级插件配置。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from jmcomic import JmOption, create_option_by_str

from ..core.enums import OutputFormat

DownloadMode = Literal["photo", "album"]


@dataclass
class JMOptionContext:
    """用于构造 jmcomic option 的配置。"""

    cache_dir: str
    output_format: OutputFormat = OutputFormat.PDF
    zip_password: str | None = None
    pdf_password: str | None = None
    log: bool = False
    proxies: str = "system"
    thread_count: int = 10
    username: str | None = None
    password: str | None = None
    modify_md5: bool = False


def _build_plugin_block(config: JMOptionContext, mode: DownloadMode, quote) -> str:
    """根据输出格式和模式构建插件配置块。

    mode="photo": after_photo 触发，用于单章节下载
    mode="album": after_album 触发，用于本子集下载
    """
    hook = "after_photo" if mode == "photo" else "after_album"
    filename_rule = "Pid" if mode == "photo" else "{Aoutput_name}"

    match config.output_format:
        case OutputFormat.PDF:
            return f"""  {hook}:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {quote(config.cache_dir)}
        filename_rule: {quote(filename_rule)}
"""
        case OutputFormat.ZIP:
            level = "photo" if mode == "photo" else "album"
            return f"""  {hook}:
    - plugin: zip
      kwargs:
        zip_dir: {quote(config.cache_dir)}
        filename_rule: {quote(filename_rule)}
        level: {level}
        suffix: zip
        delete_original_file: false
"""
        case _:
            raise ValueError(f"不支持的输出格式: {config.output_format!r}")


def create_jm_option(config: JMOptionContext, mode: DownloadMode = "photo") -> JmOption:
    """根据配置构造一个新的 JmOption 实例。

    mode="photo": 单章节下载（after_photo 插件）
    mode="album": 本子集下载（after_album 插件）
    """

    def quote(value: str) -> str:
        """安全地引用 YAML 字符串值"""
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    login_block = ""
    if config.username and config.password:
        login_block = f"""  after_init:
    - plugin: login
      kwargs:
        username: {quote(config.username)}
        password: {quote(config.password)}
"""

    plugin_block = _build_plugin_block(config, mode, quote)

    yaml_config = f"""\
log: {config.log}

client:
  impl: api
  retry_times: 1
  postman:
    meta_data:
      proxies: {quote(config.proxies)}

download:
  image:
    suffix: .jpg
  threading:
    image: {config.thread_count}

dir_rule:
  base_dir: {quote(config.cache_dir)}
  rule: Bd_Pid

plugins:
{login_block}{plugin_block}"""

    return create_option_by_str(yaml_config, mode="yml")


def copy_option_with_password(
    base_option: JmOption,
    mode: DownloadMode,
    output_format: OutputFormat,
    password: str | None,
) -> JmOption:
    """复制基础 option，并只修改本次请求的输出密码。"""
    option = base_option.copy_option()
    option.plugins = type(option.plugins)(deepcopy(base_option.plugins.src_dict))
    hook = "after_photo" if mode == "photo" else "after_album"
    plugin_key = "img2pdf" if output_format == OutputFormat.PDF else "zip"

    for plugin_info in option.plugins.get(hook, []):
        if plugin_info.get("plugin") != plugin_key:
            continue
        kwargs = plugin_info.setdefault("kwargs", {})
        if password is None:
            kwargs.pop("encrypt", None)
        else:
            kwargs["encrypt"] = {"password": password}
        return option

    raise ValueError(f"未找到输出插件: hook={hook}, plugin={plugin_key}")
