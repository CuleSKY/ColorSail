from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import requests

from .config import ClientConfig


LOGGER = logging.getLogger(__name__)


@dataclass
class ServerEntry:
    server_key: str
    name: str
    ip: str
    port: int
    players: int
    max_players: int
    community_id: str
    community_name: str
    raw: Dict[str, Any]


class WebAPI:
    def __init__(self, cfg: ClientConfig) -> None:
        self.cfg = cfg
        self.session = requests.Session()
        if cfg.session_cookie:
            self.session.headers.update({"Cookie": cfg.session_cookie})

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.cfg.base_url}{path}"
        kwargs.setdefault("timeout", self.cfg.request_timeout)
        resp = self.session.request(method, url, **kwargs)
        return resp

    def get_config(self) -> List[Dict[str, Any]]:
        resp = self._request("GET", "/api/config")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected /api/config response")
        return data

    def get_servers(self, community_id: str) -> List[Dict[str, Any]]:
        resp = self._request("GET", f"/api/servers/{community_id}")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Unexpected /api/servers response")
        return data

    def get_steam_status(self) -> Dict[str, Any]:
        resp = self._request("GET", "/api/steam/status")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected /api/steam/status response")
        return data

    def autojoin_join(self, server_key: str, queue_type: str = "normal") -> Dict[str, Any]:
        resp = self._request("POST", "/api/autojoin/join", json={"server_key": server_key, "queue_type": queue_type})
        if resp.status_code == 403:
            return {"ok": False, "error": "prime_required"}
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected autojoin join response")
        return data

    def autojoin_poll(self, server_key: str) -> Dict[str, Any]:
        resp = self._request("GET", "/api/autojoin/poll", params={"server_key": server_key})
        if resp.status_code == 403:
            return {"ok": False, "error": "prime_required"}
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected autojoin poll response")
        return data

    def autojoin_leave(self, server_key: str) -> Dict[str, Any]:
        resp = self._request("POST", "/api/autojoin/leave", json={"server_key": server_key})
        if resp.status_code == 403:
            return {"ok": False, "error": "prime_required"}
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected autojoin leave response")
        return data


    def fetch_servers(self) -> List[ServerEntry]:
        communities = self.get_config()
        entries: List[ServerEntry] = []
        for comm in communities:
            cid = str(comm.get("id", ""))
            name = comm.get("name", "") or comm.get("short_name", "") or cid
            if not cid:
                continue
            try:
                servers = self.get_servers(cid)
            except Exception as exc:
                LOGGER.warning("Failed to load servers for %s: %s", cid, exc)
                continue
            for srv in servers:
                ip = srv.get("ip")
                port = srv.get("port")
                if not ip or not port:
                    continue
                server_key = f"{ip}:{port}"
                entries.append(
                    ServerEntry(
                        server_key=server_key,
                        name=srv.get("name") or "Unknown",
                        ip=ip,
                        port=int(port),
                        players=int(srv.get("players") or 0),
                        max_players=int(srv.get("max_players") or 64),
                        community_id=cid,
                        community_name=name,
                        raw=srv,
                    )
                )
        return entries
