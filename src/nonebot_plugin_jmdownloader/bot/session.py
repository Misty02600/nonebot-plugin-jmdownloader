"""跨平台状态标识；保留 OneBot V11 的历史数据键。"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nonebot_plugin_uninfo import Member, Session


def is_onebot_v11(session: Session) -> bool:
    return session.adapter == "OneBot V11" and session.scope == "QQClient"


def _key(kind: str, session: Session, *parts: object) -> str:
    platform = session.platform
    if isinstance(platform, set):
        platform = sorted(platform)
    raw = json.dumps(
        [session.adapter, session.scope, platform, *parts], ensure_ascii=False
    )
    return f"{kind}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def _scene_parts(session: Session) -> list[str]:
    parts = [session.scene.id]
    parent = session.scene.parent
    while parent is not None:
        parts.append(parent.id)
        parent = parent.parent
    return list(reversed(parts))


def group_key(session: Session, path: str | None = None) -> str:
    parts = _scene_parts(session) if path is None else path.split("/")
    if is_onebot_v11(session):
        return parts[-1]
    # 标识经过哈希，平台中的斜杠、冒号等不会成为文件路径。
    return _key("scene", session, parts)


def user_key(session: Session) -> str:
    if is_onebot_v11(session):
        return session.user.id
    return _key("user", session, session.user.id)


def search_key(session: Session) -> str:
    return _key(
        "search",
        session,
        session.self_id,
        session.scene.type.value,
        _scene_parts(session),
        session.user.id,
    )


def role_level(member: Member | None) -> int:
    return member.role.level if member is not None and member.role is not None else 0


def is_admin(session: Session) -> bool:
    return session.member is not None and any(
        role.id in {"OWNER", "ADMINISTRATOR", "CHANNEL_ADMINISTRATOR"}
        for role in session.member.roles
    )
