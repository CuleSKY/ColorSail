from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict

import requests


class EventPublisher:
    def __init__(self, base_url: str, watcher_id: str, hmac_secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.watcher_id = watcher_id
        self.hmac_secret = hmac_secret
        self.session = requests.Session()

    def publish(self, path: str, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        ts = str(int(time.time()))
        signature = self._sign(ts, path, body)
        headers = {
            "Content-Type": "application/json",
            "X-Watcher-Id": self.watcher_id,
            "X-Watcher-Ts": ts,
            "X-Watcher-Signature": signature,
        }
        url = f"{self.base_url}{path}"
        try:
            self.session.post(url, data=body.encode("utf-8"), headers=headers, timeout=3)
        except Exception:
            return

    def _sign(self, ts: str, path: str, body: str) -> str:
        message = f"{ts}\n{path}\n{body}".encode("utf-8")
        return hmac.new(self.hmac_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


class RateLimitedPublisher:
    def __init__(self, publisher: EventPublisher, path: str) -> None:
        self.publisher = publisher
        self.path = path
        self._last_noncritical: Dict[str, float] = {}

    def publish(self, payload: Dict[str, Any], critical: bool = True) -> None:
        queue_id = payload.get("queue_id")
        if not critical and queue_id:
            now = time.monotonic()
            last = self._last_noncritical.get(queue_id, 0.0)
            if now - last < 1.0:
                return
            self._last_noncritical[queue_id] = now
        self.publisher.publish(self.path, payload)
