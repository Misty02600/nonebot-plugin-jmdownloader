"""加载真实插件和适配器，不启动联网任务；平台 API 由各测试替代。"""

import tempfile
from pathlib import Path

import nonebot
import pytest
from nonebug import NONEBOT_INIT_KWARGS, NONEBOT_START_LIFESPAN


def pytest_configure(config: pytest.Config):
    storage = tempfile.TemporaryDirectory(prefix="jmdownloader-tests-")
    config.add_cleanup(storage.cleanup)
    root = Path(storage.name)
    config.stash[NONEBOT_INIT_KWARGS] = {
        "driver": "~fastapi+~httpx",
        "superusers": {"99999"},
        "localstore_data_dir": root / "data",
        "localstore_cache_dir": root / "cache",
        "localstore_config_dir": root / "config",
    }
    config.stash[NONEBOT_START_LIFESPAN] = False


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(_nonebot_init):
    from nonebot.adapters.discord import Adapter as DiscordAdapter
    from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter
    from nonebot.adapters.telegram import Adapter as TelegramAdapter

    driver = nonebot.get_driver()
    for adapter in (DiscordAdapter, OneBotAdapter, TelegramAdapter):
        driver.register_adapter(adapter)
    assert nonebot.load_plugin("nonebot_plugin_jmdownloader") is not None


@pytest.fixture
def session_factory():
    from nonebot_plugin_uninfo import Member, Role, Scene, SceneType, Session, User

    def make(adapter="Telegram", scope="Telegram", private=False, role="MEMBER"):
        user = User("42")
        scene = Scene(
            "42" if private else "100",
            SceneType.PRIVATE if private else SceneType.GROUP,
        )
        member = Member(
            user,
            roles=[Role(role, {"MEMBER": 1, "ADMINISTRATOR": 10, "OWNER": 100}[role])],
        )
        return Session("12345", adapter, scope, scene, user, member)

    return make


@pytest.fixture(params=["Telegram", "Discord", "OneBot V11"])
def platform(request):
    from nonebot.adapters.discord import Adapter as DiscordAdapter
    from nonebot.adapters.discord import Bot as DiscordBot
    from nonebot.adapters.discord.config import BotInfo
    from nonebot.adapters.discord.event import (
        DirectMessageCreateEvent,
        GuildMessageCreateEvent,
    )
    from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter
    from nonebot.adapters.onebot.v11 import Bot as OneBot
    from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
    from nonebot.adapters.telegram import Adapter as TelegramAdapter
    from nonebot.adapters.telegram import Bot as TelegramBot
    from nonebot.adapters.telegram.config import BotConfig
    from nonebot.adapters.telegram.event import Event as TelegramEvent

    name = request.param
    driver = nonebot.get_driver()
    if name == "Telegram":
        bot = TelegramBot(
            TelegramAdapter(driver), "12345", config=BotConfig(token="12345:test")
        )
    elif name == "Discord":
        bot = DiscordBot(DiscordAdapter(driver), "12345", BotInfo(token="test"))
    else:
        bot = OneBot(OneBotAdapter(driver), "12345")

    def event(text="/jm查询 123456", private=False):
        if name == "Telegram":
            return TelegramEvent.parse_event(
                {
                    "update_id": 1,
                    "message": {
                        "message_id": 10,
                        "date": 0,
                        "chat": {
                            "id": 42 if private else 100,
                            "type": "private" if private else "group",
                        },
                        "from": {"id": 42, "is_bot": False, "first_name": "Tester"},
                        "text": text,
                    },
                }
            )
        if name == "Discord":
            data = {
                "id": "10",
                "channel_id": "100",
                "author": {
                    "id": "42",
                    "username": "Tester",
                    "discriminator": "0",
                    "avatar": None,
                },
                "content": text,
                "timestamp": "2026-10-28T00:00:00Z",
                "edited_timestamp": None,
                "tts": False,
                "mention_everyone": False,
                "mentions": [],
                "mention_roles": [],
                "attachments": [],
                "embeds": [],
                "pinned": False,
                "type": 0,
            }
            if private:
                return DirectMessageCreateEvent.model_validate(data)
            data["guild_id"] = "200"
            data["member"] = {
                "roles": [],
                "joined_at": "2026-10-28T00:00:00Z",
                "deaf": False,
                "mute": False,
                "flags": 0,
            }
            return GuildMessageCreateEvent.model_validate(data)
        data = {
            "time": 0,
            "self_id": 12345,
            "post_type": "message",
            "message_id": 10,
            "user_id": 42,
            "message": text,
            "raw_message": text,
            "font": 0,
            "sender": {"user_id": 42, "role": "member"},
            "sub_type": "friend" if private else "normal",
            "message_type": "private" if private else "group",
        }
        if private:
            return PrivateMessageEvent.model_validate(data)
        data["group_id"] = 100
        return GroupMessageEvent.model_validate(data)

    return name, bot, event
