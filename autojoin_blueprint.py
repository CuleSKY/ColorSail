from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from flask import Blueprint, Response, current_app, jsonify, request, session
from flask_sock import Sock


@dataclass
class WatcherConfig:
    cn_url: Optional[str]
    us_url: Optional[str]
    shared_token: Optional[str]
    hmac_secret: Optional[str]
    allowed_ids: Optional[set[str]]


class AutoJoinHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: Dict[str, set[Any]] = {}

    def register(self, steam_id: str, ws: Any) -> None:
        with self._lock:
            self._connections.setdefault(steam_id, set()).add(ws)

    def unregister(self, steam_id: str, ws: Any) -> None:
        with self._lock:
            conns = self._connections.get(steam_id)
            if not conns:
                return
            conns.discard(ws)
            if not conns:
                self._connections.pop(steam_id, None)

    def broadcast(self, steam_id: str, payload: Dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        stale = []
        with self._lock:
            conns = list(self._connections.get(steam_id) or [])
        for ws in conns:
            try:
                ws.send(message)
            except Exception:
                stale.append(ws)
        if stale:
            with self._lock:
                for ws in stale:
                    for sid, conns in list(self._connections.items()):
                        if ws in conns:
                            conns.discard(ws)
                            if not conns:
                                self._connections.pop(sid, None)


class EventRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_noncritical: Dict[str, float] = {}

    def allow(self, queue_id: str, critical: bool) -> bool:
        if critical:
            return True
        now = time.monotonic()
        with self._lock:
            last = self._last_noncritical.get(queue_id, 0.0)
            if now - last < 1.0:
                return False
            self._last_noncritical[queue_id] = now
            return True


def _select_watcher(server_region: str, net_profile: str) -> Optional[str]:
    region = (server_region or "").lower()
    profile = (net_profile or "").lower()
    if region == "cn" and profile == "noncn_like":
        return "cn"
    if region in {"us", "eu", "global"} and profile == "cn_like":
        return "us"
    return None


def _signed_headers(token: Optional[str]) -> Dict[str, str]:
    return {"X-Shared-Token": token} if token else {}


def _forward_to_watcher(watcher_url: str, token: Optional[str], path: str, payload: Dict[str, Any]) -> requests.Response:
    url = f"{watcher_url.rstrip('/')}{path}"
    headers = _signed_headers(token)
    return requests.post(url, headers=headers, json=payload, timeout=4)


def _verify_signature(cfg: WatcherConfig, path: str, raw_body: bytes, headers: Dict[str, str]) -> Optional[str]:
    watcher_id = headers.get("X-Watcher-Id")
    ts = headers.get("X-Watcher-Ts")
    signature = headers.get("X-Watcher-Signature")
    if not watcher_id or not ts or not signature:
        return "missing_signature"
    if cfg.allowed_ids and watcher_id not in cfg.allowed_ids:
        return "watcher_not_allowed"
    if not cfg.hmac_secret:
        return "secret_not_configured"
    try:
        ts_int = int(ts)
    except (TypeError, ValueError):
        return "invalid_timestamp"
    now = int(time.time())
    if abs(now - ts_int) > 60:
        return "stale_timestamp"
    body_text = raw_body.decode("utf-8") if raw_body else ""
    message = f"{ts}\n{path}\n{body_text}".encode("utf-8")
    expected = hmac.new(cfg.hmac_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return "invalid_signature"
    return None


def create_autojoin_blueprint(
    cfg: WatcherConfig, hub: AutoJoinHub, limiter: EventRateLimiter, is_prime_check
) -> Blueprint:
    bp = Blueprint("autojoin", __name__, url_prefix="/api")

    @bp.route("/autojoin/start", methods=["POST"])
    def autojoin_start():
        steam_id = session.get("steam_id")
        if not steam_id:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        if not is_prime_check():
            return jsonify({"ok": False, "error": "prime_required"}), 403
        payload = request.get_json(silent=True) or {}
        server_key = payload.get("server_key")
        server_region = payload.get("server_region")
        queue_type = payload.get("queue_type") or "normal"
        priority = payload.get("priority") or "none"
        net_profile = payload.get("net_profile") or "unknown"
        if not server_key:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        watcher_choice = _select_watcher(server_region, net_profile)
        if not watcher_choice:
            return jsonify({"ok": False, "error": "watcher_not_allowed"}), 403
        watcher_url = cfg.cn_url if watcher_choice == "cn" else cfg.us_url
        if not watcher_url:
            return jsonify({"ok": False, "error": "watcher_unavailable"}), 503
        try:
            resp = _forward_to_watcher(
                watcher_url,
                cfg.shared_token,
                "/v1/autojoin/start",
                {
                    "steam_id": steam_id,
                    "server_key": server_key,
                    "priority": priority,
                    "queue_type": queue_type,
                },
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": f"watcher_unreachable: {exc}"}), 502
        data = resp.json() if resp.ok else {"ok": False, "error": "watcher_error"}
        return jsonify(data), resp.status_code

    @bp.route("/autojoin/joined", methods=["POST"])
    def autojoin_joined():
        steam_id = session.get("steam_id")
        if not steam_id:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        payload = request.get_json(silent=True) or {}
        server_key = payload.get("server_key")
        queue_id = payload.get("queue_id")
        watcher_region = payload.get("watcher_region")
        watcher_url = cfg.cn_url if watcher_region == "cn" else cfg.us_url
        if not server_key or not queue_id or not watcher_url:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        try:
            resp = _forward_to_watcher(
                watcher_url,
                cfg.shared_token,
                "/v1/autojoin/joined",
                {"steam_id": steam_id, "server_key": server_key, "queue_id": queue_id},
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": f"watcher_unreachable: {exc}"}), 502
        data = resp.json() if resp.ok else {"ok": False, "error": "watcher_error"}
        return jsonify(data), resp.status_code

    @bp.route("/autojoin/stop", methods=["POST"])
    def autojoin_stop():
        steam_id = session.get("steam_id")
        if not steam_id:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        payload = request.get_json(silent=True) or {}
        server_key = payload.get("server_key")
        queue_id = payload.get("queue_id")
        watcher_region = payload.get("watcher_region")
        watcher_url = cfg.cn_url if watcher_region == "cn" else cfg.us_url
        if not server_key or not queue_id or not watcher_url:
            return jsonify({"ok": False, "error": "invalid_request"}), 400
        try:
            resp = _forward_to_watcher(
                watcher_url,
                cfg.shared_token,
                "/v1/autojoin/stop",
                {"steam_id": steam_id, "server_key": server_key, "queue_id": queue_id},
            )
        except Exception as exc:
            return jsonify({"ok": False, "error": f"watcher_unreachable: {exc}"}), 502
        data = resp.json() if resp.ok else {"ok": False, "error": "watcher_error"}
        return jsonify(data), resp.status_code

    @bp.route("/watcher/event", methods=["POST"])
    def watcher_event():
        raw_body = request.get_data(cache=False) or b""
        error = _verify_signature(cfg, "/api/watcher/event", raw_body, request.headers)
        if error:
            return jsonify({"ok": False, "error": error}), 403
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:
            return jsonify({"ok": False, "error": "invalid_json"}), 400
        queue_id = payload.get("queue_id")
        event_type = payload.get("type")
        steam_id = payload.get("steam_id")
        if not queue_id or not event_type or not steam_id:
            return jsonify({"ok": False, "error": "invalid_event"}), 400
        critical = event_type in {"autojoin.granted", "autojoin.expired", "autojoin.joined", "autojoin.stopped", "autojoin.error"}
        if not limiter.allow(queue_id, critical=critical):
            return jsonify({"ok": True, "skipped": True})
        hub.broadcast(str(steam_id), payload)
        return jsonify({"ok": True})

    return bp


def register_autojoin_ws(sock: Sock, hub: AutoJoinHub) -> None:
    @sock.route("/ws/autojoin")
    def autojoin_ws(ws):
        steam_id = session.get("steam_id")
        if not steam_id:
            ws.close()
            return
        hub.register(str(steam_id), ws)
        try:
            while True:
                msg = ws.receive()
                if msg is None:
                    break
        finally:
            hub.unregister(str(steam_id), ws)
            ws.close()
