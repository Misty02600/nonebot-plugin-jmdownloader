from pathlib import Path

from nonebot import get_plugin_config, require
from pydantic import BaseModel, Field, validator

require("nonebot_plugin_localstore")

from nonebot_plugin_localstore import get_plugin_cache_dir


class Config(BaseModel):
    jmcomic_log: bool = Field(default=False, description="是否启用JMComic API日志")
    jmcomic_proxies: str = Field(default="system", description="代理配置")
    jmcomic_thread_count: int = Field(default=10, description="下载线程数量")
    jmcomic_username: str | None = Field(default=None, description="JM登录用户名")
    jmcomic_password: str | None = Field(default=None, description="JM登录密码")
    jmcomic_allow_groups: bool = Field(default=False, description="是否默认启用所有群")
    jmcomic_user_limits: int = Field(default=5, description="每位用户的每周下载限制次数")
    jmcomic_modify_real_md5: bool = Field(default=False, description="是否真正修改PDF文件的MD5值")
    jmcomic_blocked_message: str = Field(default="猫猫吃掉了一个不豪吃的本子", description="搜索屏蔽时显示的消息")
    jmcomic_results_per_page: int = Field(default=20, description="每页显示的搜索结果数量")


    @validator("jmcomic_password", "jmcomic_username", pre=True)
    def convert_to_string(cls, v):
        if v is not None:
            return str(v)
        return v

plugin_config = get_plugin_config(Config)

plugin_cache_dir: Path = get_plugin_cache_dir()
cache_dir = plugin_cache_dir.as_posix()

login_block = ""
if plugin_config.jmcomic_username is not None and plugin_config.jmcomic_password is not None:
    login_block = f"""  after_init:
    - plugin: login
      kwargs:
        username: {plugin_config.jmcomic_username}
        password: {plugin_config.jmcomic_password}
"""


config_data = f"""
log: {plugin_config.jmcomic_log}

client:
  impl: api
  retry_times: 1
  postman:
    meta_data:
      proxies: {plugin_config.jmcomic_proxies}

download:
  image:
    suffix: .jpg
  threading:
    image: {plugin_config.jmcomic_thread_count}

dir_rule:
  base_dir: {cache_dir}
  rule: Bd_Pid

plugins:
{login_block}
  after_photo:
    - plugin: img2pdf
      kwargs:
        pdf_dir: {cache_dir}
        filename_rule: Pid
"""
