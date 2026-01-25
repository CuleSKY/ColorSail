from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict


DEFAULT_REQUEST_TIMEOUT = 6.0


@dataclass(frozen=True)
class ClientConfig:
    server_list_url: str | None
    watcher_url: str | None
    auth_token: str | None
    request_timeout: float
    config_path: Path
    settings_path: Path
    state_path: Path


def _client_dir() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path.cwd()
    return base_dir / "client"


def load_config() -> ClientConfig:
    config_dir = _client_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    raw = read_json(config_path)
    server_list_url = raw.get("server_list_url") or os.environ.get("CS2ZE_SERVER_LIST_URL")
    watcher_url = os.environ.get("CS2ZE_WATCHER_URL")
    auth_token = os.environ.get("CS2ZE_AUTH_TOKEN")
    request_timeout = DEFAULT_REQUEST_TIMEOUT
    settings_path = config_dir / "settings.json"
    state_path = config_dir / "state.json"
    return ClientConfig(
        server_list_url=server_list_url,
        watcher_url=watcher_url,
        auth_token=auth_token,
        request_timeout=request_timeout,
        config_path=config_path,
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


def update_config_url(cfg: ClientConfig, server_list_url: str) -> ClientConfig:
    payload = read_json(cfg.config_path)
    payload["server_list_url"] = server_list_url
    write_json(cfg.config_path, payload)
    return replace(cfg, server_list_url=server_list_url)


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
