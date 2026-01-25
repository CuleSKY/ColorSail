from __future__ import annotations

MAX_PLAYERS = 64
RESERVED_SLOTS = 2
PUBLIC_CAPACITY = MAX_PLAYERS - RESERVED_SLOTS


def normalize_priority(priority: str | None) -> str:
    if not priority:
        return "none"
    low = str(priority).strip().lower()
    if low in {"reserved", "vip", "priority"}:
        return "reserved"
    return "none"


def should_attempt_join(priority: str | None, players: int | None) -> bool:
    if players is None:
        return False
    mode = normalize_priority(priority)
    if mode == "reserved":
        return players < MAX_PLAYERS
    return players < PUBLIC_CAPACITY
