"""Core AutoJoin decisioning scaffold (no UI, no networking)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class AutoJoinDecision(str, Enum):
    DIRECT_CONNECT = "DIRECT_CONNECT"
    START_QUEUE = "START_QUEUE"


class AutoJoinState(str, Enum):
    IDLE = "Idle"
    RUNNING = "Running"
    LAUNCHING = "Launching"
    DONE = "Done"
    STOPPED = "Stopped"
    ERROR = "Error"


@dataclass
class ServerOverride:
    queue_threshold: int
    priority_queue_supported: bool
    aliases: Optional[list[str]] = None


@dataclass
class AutoJoinScanLoop:
    """Stub scan loop that tracks attempt counts."""
    attempts: int = 0

    def scan_once(self) -> int:
        self.attempts += 1
        return self.attempts


DEFAULT_OVERRIDES: Dict[str, ServerOverride] = {
    "css.nide.gg:27015": ServerOverride(
        queue_threshold=65,
        priority_queue_supported=False,
        aliases=["css.nide.gg:27015"],
    )
}


def _normalize_server_key(server_key: str) -> str:
    return server_key.strip().lower()


def _resolve_override(server_key: str, overrides: Dict[str, ServerOverride]) -> Optional[ServerOverride]:
    normalized = _normalize_server_key(server_key)
    for key, override in overrides.items():
        if _normalize_server_key(key) == normalized:
            return override
        for alias in override.aliases or []:
            if _normalize_server_key(alias) == normalized:
                return override
    return None


def decide_autojoin(
    server_entry: dict,
    overrides: Optional[Dict[str, ServerOverride]] = None,
    priority_declared: bool = False,
    disclaimer_accepted: bool = False,
) -> AutoJoinDecision:
    """Return the core AutoJoin decision for a server entry."""
    if not disclaimer_accepted:
        return AutoJoinDecision.DIRECT_CONNECT

    overrides = overrides or DEFAULT_OVERRIDES
    server_key = str(server_entry.get("server_key") or "")
    players = int(server_entry.get("players") or 0)
    reported_max = int(server_entry.get("reported_max_players") or 0)

    override = _resolve_override(server_key, overrides)
    queue_threshold = override.queue_threshold if override else None
    priority_supported = override.priority_queue_supported if override else True

    if queue_threshold is None:
        queue_threshold = reported_max or 0

    if priority_declared and not priority_supported:
        priority_declared = False

    if players >= queue_threshold:
        return AutoJoinDecision.START_QUEUE
    return AutoJoinDecision.DIRECT_CONNECT
