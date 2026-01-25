from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


DEFAULT_BASE_URL = "http://localhost:5000"


@dataclass(frozen=True)
class ClientConfig:
    base_url: str
    session_cookie: str | None
    request_timeout: float
    settings_path: Path
    state_path: Path


def _default_config_dir() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "cs2ze_cli"


def load_config() -> ClientConfig:
    base_url = os.environ.get("CS2ZE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    session_cookie = os.environ.get("CS2ZE_SESSION_COOKIE")
    request_timeout = float(os.environ.get("CS2ZE_TIMEOUT", "6"))
    config_dir = _default_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_path = config_dir / "settings.json"
    state_path = config_dir / "state.json"
    return ClientConfig(
        base_url=base_url,
        session_cookie=session_cookie,
        request_timeout=request_timeout,
        settings_path=settings_path,
        state_path=state_path,
    )


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    temp_path.replace(path)


@dataclass
class AutoJoinState:
    server_key: str
    mode: str
    started_at: float
    watcher_since: float | None = None


def load_state(cfg: ClientConfig) -> AutoJoinState | None:
    raw = read_json(cfg.state_path)
    if not raw:
        return None
    server_key = raw.get("server_key")
    mode = raw.get("mode")
    started_at = raw.get("started_at")
    if not server_key or not mode or not started_at:
        return None
    return AutoJoinState(
        server_key=server_key,
        mode=mode,
        started_at=float(started_at),
        watcher_since=float(raw.get("watcher_since")) if raw.get("watcher_since") else None,
    )


def save_state(cfg: ClientConfig, state: AutoJoinState) -> None:
    write_json(
        cfg.state_path,
        {
            "server_key": state.server_key,
            "mode": state.mode,
            "started_at": state.started_at,
            "watcher_since": state.watcher_since,
        },
    )


def clear_state(cfg: ClientConfig) -> None:
    if cfg.state_path.exists():
        cfg.state_path.unlink(missing_ok=True)
