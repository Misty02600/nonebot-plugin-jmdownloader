from contextlib import asynccontextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from nonebot.exception import ActionFailed, FinishedException, NetworkError


@pytest.fixture
def services(tmp_path, monkeypatch, platform, session_factory):
    from jmcomic import JmPhotoDetail
    from nonebot_plugin_uninfo import Scene, SceneType
    from nonebot_plugin_uninfo.adapters import INFO_FETCHER_MAPPING

    from nonebot_plugin_jmdownloader.bot import dependencies
    from nonebot_plugin_jmdownloader.core.enums import GroupListMode
    from nonebot_plugin_jmdownloader.infra.data_manager import DataManager
    from nonebot_plugin_jmdownloader.infra.jm_service import (
        AvatarDownloadError,
        JMService,
    )
    from nonebot_plugin_jmdownloader.infra.search_session import SessionCache

    name, bot, event_factory = platform
    session = session_factory(
        adapter=name, scope="QQClient" if name == "OneBot V11" else name
    )
    if name == "Discord":
        session.scene = Scene(
            "100", SceneType.CHANNEL_TEXT, parent=Scene("200", SceneType.GUILD)
        )
    monkeypatch.setitem(
        INFO_FETCHER_MAPPING,
        name,
        SimpleNamespace(fetch=AsyncMock(return_value=session)),
    )
    dm = DataManager(tmp_path, 5, GroupListMode.WHITELIST)
    photo = Mock(spec=JmPhotoDetail)
    photo.id = "123456"
    photo.tags = []
    photo.page_arr = ["page"]
    photo.is_single_album = True
    jm = Mock(spec=JMService)
    jm.get_photo = AsyncMock(return_value=photo)
    jm.format_photo_info.return_value = "JM123456 test result"
    jm.download_avatar = AsyncMock(side_effect=AvatarDownloadError("unavailable"))
    output = tmp_path / "123456.pdf"
    output.write_bytes(b"test-pdf")
    jm.prepare_photo_file = AsyncMock(return_value=(str(output), ".pdf"))
    jm.search = AsyncMock(
        return_value=SimpleNamespace(iter_id=lambda: iter(["123456"]))
    )
    jm.cache_in_use = False

    @asynccontextmanager
    async def cache_usage():
        jm.cache_in_use = True
        try:
            yield
        finally:
            jm.cache_in_use = False

    jm.cache_usage = cache_usage
    monkeypatch.setattr(dependencies, "_jm_service", jm)
    monkeypatch.setattr(dependencies, "_data_manager", dm)
    monkeypatch.setattr(dependencies, "_sessions", SessionCache())
    sent = []
    calls = []

    async def send(event, message, **kwargs):
        sent.append(message)
        return SimpleNamespace(
            message_id=17, chat=SimpleNamespace(id=100), id=17, channel_id=100
        )

    async def call_api(api, **kwargs):
        calls.append((api, kwargs))
        return {"message_id": 17}

    monkeypatch.setattr(bot, "send", AsyncMock(side_effect=send))
    monkeypatch.setattr(bot, "call_api", AsyncMock(side_effect=call_api))
    return SimpleNamespace(
        bot=bot,
        event=event_factory,
        session=session,
        dm=dm,
        jm=jm,
        photo=photo,
        sent=sent,
        calls=calls,
    )


def test_metadata_inherits_dependencies():
    import nonebot
    from nonebot.plugin import inherit_supported_adapters

    meta = nonebot.get_plugin("nonebot_plugin_jmdownloader").metadata
    assert meta.supported_adapters == inherit_supported_adapters(
        "nonebot_plugin_alconna", "nonebot_plugin_uninfo"
    )
    assert {
        "nonebot.adapters.telegram",
        "nonebot.adapters.discord",
        "nonebot.adapters.onebot.v11",
    } <= meta.supported_adapters


def test_state_keys_isolate_platform_scene_and_bot(session_factory):
    from nonebot_plugin_uninfo import Scene, SceneType

    from nonebot_plugin_jmdownloader.bot.session import group_key, search_key, user_key

    telegram = session_factory()
    discord = session_factory(adapter="Discord", scope="Discord")
    onebot = session_factory(adapter="OneBot V11", scope="QQClient")
    assert group_key(onebot) == "100"
    assert user_key(onebot) == "42"
    assert len({group_key(s) for s in (telegram, discord, onebot)}) == 3
    assert len({user_key(s) for s in (telegram, discord, onebot)}) == 3
    other_scene = replace(telegram, scene=Scene("101", SceneType.GROUP))
    other_bot = replace(telegram, self_id="other-bot")
    assert (
        len(
            {search_key(s) for s in (telegram, discord, onebot, other_scene, other_bot)}
        )
        == 5
    )
    topic = replace(
        telegram, scene=Scene("7", SceneType.CHANNEL_TEXT, parent=telegram.scene)
    )
    other_topic = replace(topic, scene=replace(topic.scene, parent=other_scene.scene))
    assert group_key(topic) != group_key(other_topic)
    assert group_key(topic) == group_key(telegram, "100/7")
    assert "/" not in group_key(telegram, "../../unsafe:scene")
    private = replace(telegram, scene=Scene("100", SceneType.PRIVATE))
    assert search_key(private) != search_key(telegram)


@pytest.mark.parametrize("private", [False, True])
async def test_query_runs_through_matcher(app, services, private):
    from nonebot_plugin_jmdownloader.bot.handlers.query import jm_query

    if private:
        from nonebot_plugin_uninfo import Scene, SceneType

        services.session.scene = Scene("42", SceneType.PRIVATE)
    async with app.test_matcher(jm_query) as ctx:
        ctx.receive_event(services.bot, services.event(private=private))
        ctx.should_pass_rule(jm_query)
        ctx.should_pass_permission(jm_query)
    services.jm.get_photo.assert_awaited_once_with("123456")
    assert services.sent or any("forward" in api for api, _ in services.calls)


@pytest.mark.parametrize("private", [False, True])
async def test_download_sends_file_under_lease_and_charges_once(
    app, services, monkeypatch, private
):
    from nonebot_plugin_jmdownloader.bot.handlers.download import jm_download
    from nonebot_plugin_jmdownloader.bot.session import group_key, user_key

    if private:
        from nonebot_plugin_uninfo import Scene, SceneType

        services.session.scene = Scene("42", SceneType.PRIVATE)
    services.dm.get_group(group_key(services.session)).folder_id = "qq-folder"
    original_send = services.bot.send
    original_api = services.bot.call_api

    async def send(event, message, **kwargs):
        if not isinstance(message, str):
            assert services.jm.cache_in_use
        return await original_send(event=event, message=message, **kwargs)

    async def call_api(api, **kwargs):
        if api.startswith("upload_"):
            assert services.jm.cache_in_use
        return await original_api(api, **kwargs)

    monkeypatch.setattr(services.bot, "send", AsyncMock(side_effect=send))
    monkeypatch.setattr(services.bot, "call_api", AsyncMock(side_effect=call_api))
    async with app.test_matcher(jm_download) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下载 123456", private))
        ctx.should_pass_rule(jm_download)
        ctx.should_pass_permission(jm_download)
    services.jm.prepare_photo_file.assert_awaited_once_with(services.photo)
    assert services.dm.users.get_limit(user_key(services.session)) == 4
    assert not services.jm.cache_in_use
    if services.session.adapter == "OneBot V11":
        api, params = next(
            (api, p) for api, p in services.calls if api.startswith("upload_")
        )
        assert api == ("upload_private_file" if private else "upload_group_file")
        assert params["name"] == "123456.pdf"
        if not private:
            assert params["folder_id"] == "qq-folder"
    elif services.session.adapter == "Telegram":
        assert services.sent[-1][0].data["file"] == ("123456.pdf", b"test-pdf")
    else:
        file_message = services.sent[-1]
        assert "123456.pdf" in repr(file_message)
        assert file_message[0].data["file"].content == b"test-pdf"


@pytest.mark.parametrize("failure", [ActionFailed("test"), NetworkError("test")])
async def test_failed_upload_does_not_charge(app, services, monkeypatch, failure):
    from nonebot_plugin_jmdownloader.bot.handlers import download
    from nonebot_plugin_jmdownloader.bot.session import user_key

    monkeypatch.setattr(download, "send_file", AsyncMock(side_effect=failure))
    async with app.test_matcher(download.jm_download) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下载 123456"))
        ctx.should_pass_rule(download.jm_download)
        ctx.should_pass_permission(download.jm_download)
        ctx.should_finished(download.jm_download)
    assert services.dm.users.get_limit(user_key(services.session)) == 5
    assert not services.jm.cache_in_use


async def test_search_and_next_page_are_adapter_independent(app, services, monkeypatch):
    from nonebot_plugin_jmdownloader.bot import dependencies
    from nonebot_plugin_jmdownloader.bot.handlers.search import jm_next_page, jm_search
    from nonebot_plugin_jmdownloader.bot.session import search_key

    services.jm.search = AsyncMock(
        return_value=SimpleNamespace(iter_id=lambda: iter([str(i) for i in range(21)]))
    )
    async with app.test_matcher(jm_search) as ctx:
        ctx.receive_event(services.bot, services.event("/jm搜索 test"))
        ctx.should_pass_rule(jm_search)
        ctx.should_pass_permission(jm_search)
    session = dependencies._sessions.get(search_key(services.session))
    assert session is not None
    assert session.display_idx == 20
    async with app.test_matcher(jm_next_page) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下一页"))
        ctx.should_pass_rule(jm_next_page)
        ctx.should_pass_permission(jm_next_page)
    assert dependencies._sessions.get(search_key(services.session)) is None
    if services.session.adapter != "OneBot V11":
        assert len([m for m in services.sent if "JM123456" in str(m)]) == 21


async def test_recall_failure_does_not_break_results():
    from nonebot_plugin_jmdownloader.bot.nonebot_utils import recall_progress

    receipt = SimpleNamespace(
        recallable=True, recall=AsyncMock(side_effect=ActionFailed("test"))
    )
    await recall_progress(receipt)
    receipt.recall.assert_awaited_once()


async def test_unsupported_file_is_not_sent_as_text(app, services, monkeypatch):
    from nonebot_plugin_alconna.uniseg import SerializeFailed

    from nonebot_plugin_jmdownloader.bot.handlers import download
    from nonebot_plugin_jmdownloader.bot.session import user_key

    monkeypatch.setattr(
        download, "send_file", AsyncMock(side_effect=SerializeFailed("unsupported"))
    )
    async with app.test_matcher(download.jm_download) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下载 123456"))
        ctx.should_pass_rule(download.jm_download)
        ctx.should_pass_permission(download.jm_download)
        ctx.should_finished(download.jm_download)
    assert services.dm.users.get_limit(user_key(services.session)) == 5
    assert "当前平台不支持文件发送" in str(services.sent[-1])


@pytest.mark.parametrize("private", [False, True])
async def test_album_download_uses_same_upload_flow(
    app, services, monkeypatch, private
):
    from jmcomic import JmAlbumDetail
    from nonebot_plugin_uninfo import Scene, SceneType

    from nonebot_plugin_jmdownloader.bot.dependencies import plugin_config
    from nonebot_plugin_jmdownloader.bot.handlers.download import jm_album_download
    from nonebot_plugin_jmdownloader.bot.session import user_key

    if private:
        services.session.scene = Scene("42", SceneType.PRIVATE)
    monkeypatch.setattr(plugin_config, "jmcomic_allow_album_download", True)
    album = Mock(spec=JmAlbumDetail)
    album.id = "987654"
    album.tags = []
    album.episode_list = ["chapter1", "chapter2"]
    services.jm.get_album = AsyncMock(return_value=album)
    services.jm.get_album_output_name.return_value = "987654_1-2"
    services.jm.format_album_info.return_value = "album info"
    services.jm.prepare_album_file = AsyncMock(
        return_value=services.jm.prepare_photo_file.return_value
    )
    async with app.test_matcher(jm_album_download) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下载集 987654 1-2", private))
        ctx.should_pass_rule(jm_album_download)
        ctx.should_pass_permission(jm_album_download)
    services.jm.prepare_album_file.assert_awaited_once_with(album, [0, 1])
    assert services.dm.users.get_limit(user_key(services.session)) == 4


@pytest.mark.parametrize("private", [False, True])
async def test_disabled_scene_stops_before_query(app, services, monkeypatch, private):
    from nonebot_plugin_uninfo import Scene, SceneType

    from nonebot_plugin_jmdownloader.bot.dependencies import plugin_config
    from nonebot_plugin_jmdownloader.bot.handlers.query import jm_query
    from nonebot_plugin_jmdownloader.bot.session import group_key

    if private:
        services.session.scene = Scene("42", SceneType.PRIVATE)
        monkeypatch.setattr(plugin_config, "jmcomic_allow_private", False)
    else:
        services.dm.get_group(group_key(services.session)).enabled = False
    async with app.test_matcher(jm_query) as ctx:
        ctx.receive_event(services.bot, services.event(private=private))
        ctx.should_pass_rule(jm_query)
        ctx.should_pass_permission(jm_query)
        ctx.should_finished(jm_query)
    services.jm.get_photo.assert_not_awaited()


async def test_blacklisted_user_cannot_start_download(app, services):
    from nonebot_plugin_jmdownloader.bot.handlers.download import jm_download
    from nonebot_plugin_jmdownloader.bot.session import group_key

    services.dm.get_group(group_key(services.session)).blacklist.add("42")
    async with app.test_matcher(jm_download) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下载 123456"))
        ctx.should_pass_rule(jm_download)
        ctx.should_pass_permission(jm_download)
        ctx.should_finished(jm_download)
    services.jm.prepare_photo_file.assert_not_awaited()


@pytest.mark.parametrize("role", ["MEMBER", "ADMINISTRATOR", None])
async def test_restricted_download_respects_roles_and_platform(app, services, role):
    from nonebot_plugin_uninfo import Role

    from nonebot_plugin_jmdownloader.bot.handlers.download import jm_download
    from nonebot_plugin_jmdownloader.bot.session import group_key

    services.session.member.roles = (
        [] if role is None else [Role(role, 10 if role == "ADMINISTRATOR" else 1)]
    )
    services.dm.restriction.restricted_ids.add("123456")
    async with app.test_matcher(jm_download) as ctx:
        ctx.receive_event(services.bot, services.event("/jm下载 123456"))
        ctx.should_pass_rule(jm_download)
        ctx.should_pass_permission(jm_download)
        ctx.should_finished(jm_download)
    services.jm.prepare_photo_file.assert_not_awaited()
    assert ("42" in services.dm.get_group(group_key(services.session)).blacklist) == (
        role == "MEMBER"
    )
    muted = any(api == "set_group_ban" for api, _ in services.calls)
    assert muted == (role == "MEMBER" and services.session.adapter == "OneBot V11")


@pytest.mark.parametrize("admin", [False, True])
async def test_blacklist_permission_uses_platform_roles(app, services, admin):
    from nonebot_plugin_uninfo import Role

    from nonebot_plugin_jmdownloader.bot.handlers.blacklist import jm_blacklist

    if admin:
        services.session.member.roles = [Role("ADMINISTRATOR", 10)]
    async with app.test_matcher(jm_blacklist) as ctx:
        ctx.receive_event(services.bot, services.event("/jm黑名单"))
        if admin:
            ctx.should_pass_permission(jm_blacklist)
            ctx.should_pass_rule(jm_blacklist)
            ctx.should_finished(jm_blacklist)
        else:
            ctx.should_not_pass_permission(jm_blacklist)
    assert bool(services.sent) == admin


async def test_folder_command_keeps_onebot_capability(app, services, monkeypatch):
    from nonebot_plugin_uninfo import Role

    from nonebot_plugin_jmdownloader.bot.handlers.group_control import jm_set_folder
    from nonebot_plugin_jmdownloader.bot.session import group_key

    services.session.member.roles = [Role("ADMINISTRATOR", 10)]
    api = AsyncMock(
        return_value={"folders": [{"folder_name": "JM", "folder_id": "native-folder"}]}
    )
    monkeypatch.setattr(services.bot, "call_api", api)
    async with app.test_matcher(jm_set_folder) as ctx:
        ctx.receive_event(services.bot, services.event("/jm设置文件夹 JM"))
        ctx.should_pass_permission(jm_set_folder)
        ctx.should_pass_rule(jm_set_folder)
        ctx.should_finished(jm_set_folder)
    if services.session.adapter == "OneBot V11":
        assert (
            services.dm.get_group(group_key(services.session)).folder_id
            == "native-folder"
        )
        api.assert_awaited_once_with("get_group_root_files", group_id=100)
    else:
        api.assert_not_awaited()
        assert "仅支持 OneBot V11" in str(services.sent[-1])


@pytest.mark.parametrize("target_level", [1, 10, 100, None])
async def test_blacklist_target_role_must_be_lower(services, target_level):
    from nonebot_plugin_uninfo import Member, Role, User

    from nonebot_plugin_jmdownloader.bot.handlers.blacklist import can_operate_check

    services.session.member.roles = [Role("ADMINISTRATOR", 10)]
    target = (
        None
        if target_level is None
        else Member(User("43"), roles=[Role("target", target_level)])
    )
    interface = SimpleNamespace(get_member=AsyncMock(return_value=target))
    matcher = SimpleNamespace(finish=AsyncMock(side_effect=FinishedException))
    args = (services.bot, services.event(), services.session, interface, matcher, "43")
    if target_level == 1:
        await can_operate_check(*args)
        matcher.finish.assert_not_awaited()
    else:
        with pytest.raises(FinishedException):
            await can_operate_check(*args)


@pytest.mark.parametrize("mention", [False, True])
async def test_blacklist_accepts_native_mentions_and_ids(
    app, services, monkeypatch, mention
):
    from nonebot_plugin_alconna import UniMessage

    from nonebot_plugin_jmdownloader.bot.handlers.blacklist import (
        jm_ban_user,
        jm_unban_user,
    )
    from nonebot_plugin_jmdownloader.bot.session import group_key

    prefix = services.bot.adapter.get_name().split()[0].lower()
    monkeypatch.setattr(services.bot.config, "superusers", {f"{prefix}:42"})
    for command, matcher in (("jm拉黑", jm_ban_user), ("jm解除拉黑", jm_unban_user)):
        event = services.event(f"/{command} " + ("" if mention else "43"))
        if mention:
            if services.session.adapter == "Telegram":
                from nonebot.adapters.telegram.message import Entity
                from nonebot.adapters.telegram.model import User

                at = Entity.text_mention(
                    "Target", User(id=43, is_bot=False, first_name="Target")
                )
            else:
                at = await UniMessage.at("43").export(bot=services.bot)
            event.get_message().__iadd__(at)
        async with app.test_matcher(matcher) as ctx:
            ctx.receive_event(services.bot, event)
            ctx.should_pass_permission(matcher)
            ctx.should_pass_rule(matcher)
            ctx.should_finished(matcher)
        assert (
            "43" in services.dm.get_group(group_key(services.session)).blacklist
        ) == (matcher == jm_ban_user)


@pytest.mark.parametrize("platform", ["Telegram"], indirect=True)
async def test_telegram_username_is_not_stored_as_user_id(app, services, monkeypatch):
    from nonebot.adapters.telegram.message import Entity

    from nonebot_plugin_jmdownloader.bot.handlers.blacklist import jm_ban_user
    from nonebot_plugin_jmdownloader.bot.session import group_key

    monkeypatch.setattr(services.bot.config, "superusers", {"telegram:42"})
    event = services.event("/jm拉黑 ")
    event.message += Entity.mention("@target")
    # NoneBug 0.4.x 不记录被并发依赖包装进 ExceptionGroup 的 finish。
    async with app.test_matcher(jm_ban_user) as ctx:
        ctx.receive_event(services.bot, event)
        ctx.should_pass_permission(jm_ban_user)
        ctx.should_pass_rule(jm_ban_user)
    assert not services.dm.get_group(group_key(services.session)).blacklist
    assert "直接填写用户 ID" in str(services.sent[-1])


@pytest.mark.parametrize("enabled", [False, True])
async def test_bulk_switch_uses_current_platform_scene_path(
    app, services, monkeypatch, enabled
):
    from nonebot_plugin_jmdownloader.bot.handlers.group_control import (
        jm_disable_group,
        jm_enable_group,
    )
    from nonebot_plugin_jmdownloader.bot.session import group_key

    prefix = services.bot.adapter.get_name().split()[0].lower()
    monkeypatch.setattr(services.bot.config, "superusers", {f"{prefix}:42"})
    path = "200/100" if services.session.adapter == "Discord" else "100"
    matcher = jm_enable_group if enabled else jm_disable_group
    command = "jm启用群" if enabled else "jm禁用群"
    async with app.test_matcher(matcher) as ctx:
        ctx.receive_event(services.bot, services.event(f"/{command} {path}"))
        ctx.should_pass_permission(matcher)
        ctx.should_pass_rule(matcher)
        ctx.should_finished(matcher)
    assert services.dm.get_group(group_key(services.session)).enabled == enabled


async def test_group_management_does_not_reply_in_private(app, services, monkeypatch):
    from nonebot_plugin_uninfo import Scene, SceneType

    from nonebot_plugin_jmdownloader.bot.handlers.blacklist import jm_blacklist

    prefix = services.bot.adapter.get_name().split()[0].lower()
    monkeypatch.setattr(services.bot.config, "superusers", {f"{prefix}:42"})
    services.session.scene = Scene("42", SceneType.PRIVATE)
    async with app.test_matcher(jm_blacklist) as ctx:
        ctx.receive_event(services.bot, services.event("/jm黑名单", private=True))
        ctx.should_pass_permission(jm_blacklist)
        ctx.should_not_pass_rule(jm_blacklist)
    assert not services.sent


async def test_query_exports_cover_image(app, services):
    import io

    from PIL import Image

    from nonebot_plugin_jmdownloader.bot.handlers.query import jm_query

    data = io.BytesIO()
    Image.new("RGB", (4, 4), color="red").save(data, format="PNG")
    data.seek(0)
    services.jm.download_avatar = AsyncMock(return_value=data)
    async with app.test_matcher(jm_query) as ctx:
        ctx.receive_event(services.bot, services.event())
        ctx.should_pass_permission(jm_query)
        ctx.should_pass_rule(jm_query)
    if services.session.adapter == "OneBot V11":
        nodes = next(
            params["messages"] for api, params in services.calls if "forward" in api
        )
        assert "image" in repr(nodes)
    else:
        assert any(seg.type in {"photo", "attachment"} for seg in services.sent[-1])
