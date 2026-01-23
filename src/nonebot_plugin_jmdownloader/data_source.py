import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from nonebot import logger, require

from .config import plugin_config

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_data_dir


class JmComicDataManager:
    """ 用于管理与 JMComic 插件相关的数据 """

    DEFAULT_RESTRICTED_TAGS = ["獵奇", "重口", "YAOI", "yaoi", "男同", "血腥", "猎奇", "虐杀", "恋尸癖" ]
    DEFAULT_RESTRICTED_IDS = [
        "136494", "323666", "350234", "363848", "405848",
        "454278", "481481", "559716", "611650", "629252",
        "69658", "626487", "400002", "208092", "253199",
        "382596", "418600", "279464", "565616", "222458"
    ]

    def __init__(self, filename: str = "jmcomic_data.json"):
        self.filepath = get_plugin_data_dir() / filename
        self.data = {}
        self.default_enabled = plugin_config.jmcomic_allow_groups
        self._load_data()

        if "restricted_tags" not in self.data or not self.data["restricted_tags"]:
            self.data["restricted_tags"] = self.DEFAULT_RESTRICTED_TAGS.copy()

        if "restricted_ids" not in self.data:
            self.data["restricted_ids"] = self.DEFAULT_RESTRICTED_IDS.copy()

        self.save()

    def _load_data(self):
        """ 加载数据文件 """
        if self.filepath.exists():
            try:
                with self.filepath.open("r", encoding="utf-8") as f:
                    self.data = json.load(f)
                    logger.info(f"成功加载数据文件：{self.filepath}")
            except json.JSONDecodeError as e:
                logger.error(f"数据文件读取错误：{e}")
                self.data = {}
        else:
            logger.info(f"未找到数据文件，将创建新的文件：{self.filepath}")
            self.data = {}

    def save(self):
        """ 保存数据到文件 """
        try:
            with self.filepath.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存数据文件出错：{e}")

    # ------------------- 群文件夹 ID 管理 -------------------
    def set_group_folder_id(self, group_id: int, folder_id: str):
        """ 设置群文件夹ID """
        group_data = self.data.setdefault(str(group_id), {})
        group_data["folder_id"] = folder_id
        self.save()

    def get_group_folder_id(self, group_id: int) -> str | None:
        """ 获取群文件夹ID """
        group_data = self.data.get(str(group_id), {})
        return group_data.get("folder_id")

    # ------------------- 用户下载限制管理 (全局) -------------------
    def get_user_limit(self, user_id: int) -> int:
        """ 获取用户的当前下载次数"""
        user_limits = self.data.setdefault("user_limits", {})
        return user_limits.get(str(user_id), plugin_config.jmcomic_user_limits)

    def set_user_limit(self, user_id: int, limit: int):
        """ 设置用户的下载次数 """
        user_limits = self.data.setdefault("user_limits", {})
        user_limits[str(user_id)] = limit
        self.save()

    def increase_user_limit(self, user_id: int, amount: int = 1):
        """ 增加用户的下载次数 """
        current_limit = self.get_user_limit(user_id)
        self.set_user_limit(user_id, current_limit + amount)

    def decrease_user_limit(self, user_id: int, amount: int = 1):
        """ 减少用户的下载次数，最低为 0 """
        current_limit = self.get_user_limit(user_id)
        new_limit = max(0, current_limit - amount)
        self.set_user_limit(user_id, new_limit)

    # ------------------- 群黑名单管理 -------------------
    def add_blacklist(self, group_id: int, user_id: int):
        """ 添加用户到群黑名单 """
        group_data = self.data.setdefault(str(group_id), {})
        blacklist = group_data.setdefault("blacklist", [])
        if str(user_id) not in blacklist:
            blacklist.append(str(user_id))
            self.save()

    def remove_blacklist(self, group_id: int, user_id: int):
        """ 从群黑名单移除用户 """
        group_data = self.data.get(str(group_id), {})
        blacklist = group_data.get("blacklist", [])
        if str(user_id) in blacklist:
            blacklist.remove(str(user_id))
            self.save()

    def is_user_blacklisted(self, group_id: int, user_id: int) -> bool:
        """ 检查用户是否在群黑名单中 """
        group_data = self.data.get(str(group_id), {})
        blacklist = group_data.get("blacklist", [])
        return str(user_id) in blacklist

    def list_blacklist(self, group_id: int) -> list[str]:
        """ 列出当前群的黑名单 """
        group_data = self.data.get(str(group_id), {})
        return group_data.get("blacklist", [])

    # ------------------- 群功能启用管理 -------------------
    def is_group_enabled(self, group_id: int) -> bool:
        """ 检查群是否启用功能 """
        group_data = self.data.get(str(group_id), {})
        return group_data.get("enabled", self.default_enabled)

    def set_group_enabled(self, group_id: int, enabled: bool):
        """ 设置群功能启用或禁用 """
        group_data = self.data.setdefault(str(group_id), {})
        group_data["enabled"] = enabled
        self.save()

    # ------------------- 默认禁止下载的本子管理 -------------------
    def list_forbidden_albums(self) -> list[str]:
        """
        返回不可下载的本子列表
        """
        return self.data.setdefault("forbidden_albums", [])

    def add_forbidden_album(self, album_id: str):
        """
        将某本子ID加入禁用列表
        """
        forbidden = self.data.setdefault("forbidden_albums", [])
        if album_id not in forbidden:
            forbidden.append(album_id)
            self.save()

    def remove_forbidden_album(self, album_id: str):
        """
        将某本子ID移出禁用列表
        """
        forbidden = self.data.setdefault("forbidden_albums", [])
        if album_id in forbidden:
            forbidden.remove(album_id)
            self.save()

    def is_forbidden_album(self, album_id: str) -> bool:
        """
        检查本子是否被禁用
        """
        return album_id in self.data.setdefault("forbidden_albums", [])

    # ------------------- 禁止下载: IDs + Tags -------------------
    def add_restricted_jm_id(self, jm_id: str):
        """ 将指定本子ID加入到禁止下载列表 """
        restricted_ids = self.data.setdefault("restricted_ids", [])
        if jm_id not in restricted_ids:
            restricted_ids.append(jm_id)
            self.save()

    def is_jm_id_restricted(self, jm_id: str) -> bool:
        """ 检查某个本子ID是否在禁止列表中 """
        restricted_ids = self.data.setdefault("restricted_ids", [])
        return jm_id in restricted_ids

    def add_restricted_tag(self, tag: str):
        """ 将指定标签加入到禁止下载列表 """
        restricted_tags = self.data.setdefault("restricted_tags", [])
        if tag not in restricted_tags:
            restricted_tags.append(tag)
            self.save()

    def is_tag_restricted(self, tag: str) -> bool:
        """ 检查某个标签是否在禁止列表中（忽略大小写的话可再处理） """
        restricted_tags = self.data.setdefault("restricted_tags", [])
        return tag in restricted_tags

    def has_restricted_tag(self, tags: list[str]) -> bool:
        """ 给定一系列tags，若与 restricted_tags 有交集，则返回 True """
        restricted_tags = set(self.data.setdefault("restricted_tags", []))
        for t in tags:
            if t in restricted_tags:
                return True
        return False


@dataclass
class SearchState:
    query: str
    start_idx: int
    total_results: list[str]
    api_page: int
    created_at: datetime = field(default_factory=datetime.now)

    def is_expired(self, ttl_minutes: int = 30) -> bool:
        return datetime.now() - self.created_at > timedelta(minutes=ttl_minutes)

    @property
    def has_more(self) -> bool:
        """检查是否还有更多结果"""
        return self.start_idx < len(self.total_results)

class SearchManager:
    def __init__(self, ttl_minutes: int = 30):
        self.states: dict[str, SearchState] = {}
        self.ttl_minutes = ttl_minutes

    def get_state(self, user_id: str) -> SearchState | None:
        """获取用户的搜索状态,如果过期则返回None"""
        state = self.states.get(user_id)
        if state and state.is_expired(self.ttl_minutes):
            del self.states[user_id]
            return None
        return state

    def set_state(self, user_id: str, state: SearchState):
        """设置用户的搜索状态"""
        self.states[user_id] = state

    def remove_state(self, user_id: str):
        """移除用户的搜索状态"""
        self.states.pop(user_id, None)

    def clean_expired(self):
        """清理所有过期的搜索状态"""
        expired = [uid for uid, state in self.states.items()
                  if state.is_expired(self.ttl_minutes)]
        for uid in expired:
            del self.states[uid]


search_manager = SearchManager()
data_manager = JmComicDataManager()
