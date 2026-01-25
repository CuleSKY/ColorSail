from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict, List, Optional

import requests

from .config import ClientConfig


@dataclass
class ServerEntry:
    game_type: str
    ip: str
    port: int
    server_key: str
    connect_target: str
    name: str
    players: int
    max_players: int
    online: bool
    display_ip: Optional[str]
    raw: Dict[str, Any]


class WebAPI:
    def __init__(self, cfg: ClientConfig) -> None:
        self.cfg = cfg
        self.session = requests.Session()
        if cfg.session_cookie:
            self.session.headers.update({"Cookie": cfg.session_cookie})

    def _request_json(self, url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", self.cfg.request_timeout)
        resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _watcher_request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        if not self.cfg.watcher_url or not self.cfg.auth_token:
            return {"ok": False, "error": "watcher_disabled"}
        url = f"{self.cfg.watcher_url.rstrip('/')}{path}"
        headers = {"X-Shared-Token": self.cfg.auth_token}
        kwargs.setdefault("timeout", self.cfg.request_timeout)
        try:
            resp = self.session.request(method, url, headers=headers, **kwargs)
        except Exception as exc:
            return {"ok": False, "error": f"watcher_unreachable: {exc}"}
        if resp.status_code in (401, 403):
            return {"ok": False, "error": "unauthorized"}
        try:
            data = resp.json()
        except Exception:
            return {"ok": False, "error": "invalid watcher response"}
        if not isinstance(data, dict):
            return {"ok": False, "error": "invalid watcher response"}
        return data

    def fetch_servers_from_url(self, url: str) -> List[ServerEntry]:
        payload = self._request_json(url)
        if isinstance(payload, list):
            server_payload = payload
        elif isinstance(payload, dict):
            servers = payload.get("servers")
            if isinstance(servers, list):
                server_payload = servers
            else:
                server_payload = []
                for cid, items in payload.items():
                    if not isinstance(items, list):
                        continue
                    for raw in items:
                        if isinstance(raw, dict) and "cid" not in raw:
                            raw["cid"] = cid
                        server_payload.append(raw)
        else:
            raise ValueError("Server list response must be a JSON array")
        entries: List[ServerEntry] = []
        for raw in server_payload:
            if not isinstance(raw, dict):
                continue
            game_type = raw.get("game_type")
            if game_type not in {"cs2", "css"}:
                continue
            ip = raw.get("ip")
            port = raw.get("port")
            if not isinstance(ip, str) or not ip:
                continue
            if port is None:
                continue
            try:
                port_num = int(port)
            except (TypeError, ValueError):
                continue
            connect_ip = raw.get("connect_ip") or ip
            if not isinstance(connect_ip, str) or not connect_ip:
                connect_ip = ip
            connect_target = f"{connect_ip}:{port_num}"
            server_key = f"{ip}:{port_num}"
            name = raw.get("name") or "Unknown"
            try:
                players = int(raw.get("players") or 0)
            except (TypeError, ValueError):
                players = 0
            try:
                max_players = int(raw.get("max_players") or 0)
            except (TypeError, ValueError):
                max_players = 0
            online = bool(raw.get("online"))
            display_ip = raw.get("display_ip")
            entries.append(
                ServerEntry(
                    game_type=game_type,
                    ip=ip,
                    port=port_num,
                    server_key=server_key,
                    connect_target=connect_target,
                    name=name,
                    players=players,
                    max_players=max_players,
                    online=online,
                    display_ip=display_ip,
                    raw=raw,
                )
            )
        return entries

    def fetch_servers(self) -> List[ServerEntry]:
        if not self.cfg.server_list_url:
            raise ValueError("Server list URL not configured")
        return self.fetch_servers_from_url(self.cfg.server_list_url)

    def autojoin_start(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._site_request("POST", "/api/autojoin/start", json=payload)

    def autojoin_joined(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._site_request("POST", "/api/autojoin/joined", json=payload)

    def autojoin_stop(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._site_request("POST", "/api/autojoin/stop", json=payload)

    def _site_request(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        base_url = self.cfg.base_url.rstrip("/")
        url = f"{base_url}{path}"
        kwargs.setdefault("timeout", self.cfg.request_timeout)
        try:
            resp = self.session.request(method, url, **kwargs)
        except Exception as exc:
            return {"ok": False, "error": f"main_site_unreachable: {exc}"}
        if resp.status_code in (401, 403):
            return {"ok": False, "error": "unauthorized"}
        try:
            data = resp.json()
        except Exception:
            return {"ok": False, "error": "invalid_response"}
        if not isinstance(data, dict):
            return {"ok": False, "error": "invalid_response"}
        return data

    def ws_url(self, path: str) -> str:
        base = urlparse(self.cfg.base_url)
        scheme = "wss" if base.scheme == "https" else "ws"
        return urlunparse((scheme, base.netloc, path, "", "", ""))

    def watcher_join(self, server_key: str, queue_type: str = "normal") -> Dict[str, Any]:
        return self._watcher_request("POST", "/v1/autojoin/join", json={"server_key": server_key, "queue_type": queue_type})

    def watcher_poll(self, server_key: str) -> Dict[str, Any]:
        return self._watcher_request("GET", "/v1/autojoin/poll", params={"server_key": server_key})

    def watcher_leave(self, server_key: str) -> Dict[str, Any]:
        return self._watcher_request("POST", "/v1/autojoin/leave", json={"server_key": server_key})
