"""Notification models for the client scaffold."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClickAction(str, Enum):
    ACTION_JOIN_STEAM = "ACTION_JOIN_STEAM"
    ACTION_COPY_CONSOLE = "ACTION_COPY_CONSOLE"
    ACTION_NONE = "ACTION_NONE"


@dataclass(frozen=True)
class Notification:
    title: str
    message: str
    server_key: str
    map_name: str
    action: ClickAction
    action_payload: str | None = None


def build_steam_uri(game_id: int, ip: str, port: int | str) -> str:
    return f"steam://rungameid/{game_id}//+connect%20{ip}:{port}"
