from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class BackoffState:
    failures: int = 0
    last_attempt: float = 0.0


class RateLimiter:
    def __init__(self, min_interval: float, max_in_flight: int = 12, max_backoff: float = 5.0) -> None:
        self.min_interval = min_interval
        self.max_backoff = max_backoff
        self._sem = threading.Semaphore(max_in_flight)
        self._lock = threading.Lock()
        self._states: Dict[str, BackoffState] = {}

    def acquire(self, server_key: str) -> None:
        self._sem.acquire()
        delay = self._wait_delay(server_key)
        if delay > 0:
            time.sleep(delay)
        with self._lock:
            state = self._states.setdefault(server_key, BackoffState())
            state.last_attempt = time.monotonic()

    def release(self) -> None:
        self._sem.release()

    def record_failure(self, server_key: str) -> None:
        with self._lock:
            state = self._states.setdefault(server_key, BackoffState())
            state.failures += 1

    def record_success(self, server_key: str) -> None:
        with self._lock:
            state = self._states.setdefault(server_key, BackoffState())
            state.failures = 0

    def _wait_delay(self, server_key: str) -> float:
        now = time.monotonic()
        with self._lock:
            state = self._states.setdefault(server_key, BackoffState())
            elapsed = now - state.last_attempt
            base_wait = max(0.0, self.min_interval - elapsed)
            backoff = min(self.max_backoff, (2 ** max(0, state.failures - 1)) * 0.5) if state.failures else 0.0
            return max(base_wait, backoff)
