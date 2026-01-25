from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from watcher_a2s import query_a2s
from watcher_targets import get_target, update_status
from watcher_utils import now_ts


@dataclass
class A2SStatus:
    server_key: str
    players: Optional[int]
    max_players: Optional[int]
    name: Optional[str]
    updated_at: int
    last_ok_at: int
    a2s_unavailable: bool
    stale: bool


class A2SCache:
    def __init__(self, get_queue_count: Callable[[str], int], on_status: Callable[[str, A2SStatus], None]) -> None:
        self._get_queue_count = get_queue_count
        self._on_status = on_status
        self._lock = threading.Lock()
        self._status: Dict[str, A2SStatus] = {}
        self._threads: Dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        self._failures: Dict[str, int] = {}

    def start(self) -> None:
        self._stop.clear()

    def stop(self) -> None:
        self._stop.set()
        for thread in list(self._threads.values()):
            thread.join(timeout=1)

    def ensure_server(self, server_key: str) -> None:
        with self._lock:
            if server_key in self._threads:
                return
            thread = threading.Thread(target=self._poll_loop, args=(server_key,), daemon=True)
            self._threads[server_key] = thread
            thread.start()

    def get_status(self, server_key: str) -> Optional[A2SStatus]:
        with self._lock:
            status = self._status.get(server_key)
            return status

    def _poll_loop(self, server_key: str) -> None:
        while not self._stop.is_set():
            queue_count = self._get_queue_count(server_key)
            base_interval = random.uniform(0.2, 0.5) if queue_count > 0 else random.uniform(1.0, 3.0)
            fail_count = self._failures.get(server_key, 0)
            if fail_count:
                backoff = min(15.0, (2 ** max(0, fail_count - 1)) * 0.5)
                interval = max(base_interval, backoff)
            else:
                interval = base_interval
            target = get_target(server_key)
            if not target:
                time.sleep(interval)
                continue
            info = query_a2s(target["ip"], target["port"], timeout=1.2)
            now = now_ts()
            if info:
                self._failures[server_key] = 0
                status = A2SStatus(
                    server_key=server_key,
                    players=info.get("players"),
                    max_players=info.get("max_players"),
                    name=info.get("name"),
                    updated_at=now,
                    last_ok_at=now,
                    a2s_unavailable=False,
                    stale=False,
                )
                update_status(
                    server_key,
                    players=info.get("players"),
                    max_players=info.get("max_players"),
                    name=info.get("name") or target.get("name"),
                    a2s_unavailable=False,
                    updated_at=now,
                )
            else:
                self._failures[server_key] = fail_count + 1
                prev = self._status.get(server_key)
                last_ok = prev.last_ok_at if prev else 0
                status = A2SStatus(
                    server_key=server_key,
                    players=prev.players if prev else None,
                    max_players=prev.max_players if prev else None,
                    name=prev.name if prev else None,
                    updated_at=now,
                    last_ok_at=last_ok,
                    a2s_unavailable=True,
                    stale=True,
                )
                update_status(server_key, a2s_unavailable=True, updated_at=now)
            with self._lock:
                self._status[server_key] = status
            self._on_status(server_key, status)
            time.sleep(interval)
