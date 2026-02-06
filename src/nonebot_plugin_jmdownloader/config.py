"""插件配置"""

from pydantic import BaseModel, Field, field_validator


class PluginConfig(BaseModel):
    """插件配置"""

    # JM 服务
    jmcomic_log: bool = Field(default=False, description="是否启用JMComic API日志")
    jmcomic_proxies: str = Field(default="system", description="代理配置")
    jmcomic_thread_count: int = Field(default=10, description="下载线程数量")
    jmcomic_username: str | None = Field(default=None, description="JM登录用户名")
    jmcomic_password: str | None = Field(default=None, description="JM登录密码")
    jmcomic_modify_real_md5: bool = Field(
        default=False, description="是否修改PDF的MD5值"
    )

    # 数据管理
    jmcomic_allow_groups: bool = Field(default=False, description="是否默认启用所有群")
    jmcomic_user_limits: int = Field(
        default=5, description="每位用户的每周下载限制次数"
    )

    # 服务层
    jmcomic_results_per_page: int = Field(
        default=20, description="每页显示的搜索结果数量"
    )

    @field_validator("jmcomic_password", "jmcomic_username", mode="before")
    @classmethod
    def convert_to_string(cls, v):
        if v is not None:
            return str(v)
        return v
