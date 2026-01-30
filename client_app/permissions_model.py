"""User permission modeling for the client scaffold."""
from __future__ import annotations

from enum import Enum


class UserMode(str, Enum):
    GUEST = "GUEST"
    LOGGED_IN = "LOGGED_IN"
    AUTOJOIN_ENABLED = "AUTOJOIN_ENABLED"


def _normalize_mode(mode: UserMode | str) -> UserMode:
    if isinstance(mode, UserMode):
        return mode
    return UserMode(mode)


def show_join_server(mode: UserMode | str) -> bool:
    return True


def show_copy_console(mode: UserMode | str) -> bool:
    return True


def show_subscribe_map(mode: UserMode | str) -> bool:
    normalized = _normalize_mode(mode)
    return normalized in {UserMode.LOGGED_IN, UserMode.AUTOJOIN_ENABLED}


def show_apply_autojoin(mode: UserMode | str) -> bool:
    normalized = _normalize_mode(mode)
    return normalized == UserMode.LOGGED_IN


def show_autojoin_button(mode: UserMode | str) -> bool:
    normalized = _normalize_mode(mode)
    return normalized == UserMode.AUTOJOIN_ENABLED
