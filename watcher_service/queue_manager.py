from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional

from autojoin_policy import normalize_priority, should_attempt_join
from watcher_targets import get_target
from watcher_utils import make_fast_join_url, now_ts


GRANT_WINDOW_SECONDS = 15


@dataclass
class QueueEntry:
    queue_id: str
    steam_id: str
    server_key: str
    priority: str
    queue_type: str
    state: str = "queued"
    seq: int = 0
    grant_expires_at: Optional[int] = None
    last_noncritical_at: float = 0.0


@dataclass
class ServerQueueState:
    priority_queue: Deque[str] = field(default_factory=deque)
    normal_queue: Deque[str] = field(default_factory=deque)
    granted_queue_id: Optional[str] = None
    debounce_count: int = 0
    debounce_queue_id: Optional[str] = None


class QueueManager:
    def __init__(self, publisher) -> None:
        self.publisher = publisher
        self._lock = threading.Lock()
        self._entries: Dict[str, QueueEntry] = {}
        self._servers: Dict[str, ServerQueueState] = {}
        self._stop = threading.Event()
        self._expiry_thread = threading.Thread(target=self._expiry_loop, daemon=True)
        self._expiry_thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._expiry_thread.join(timeout=1)

    def get_queue_count(self, server_key: str) -> int:
        with self._lock:
            state = self._servers.get(server_key)
            if not state:
                return 0
            count = len(state.priority_queue) + len(state.normal_queue)
            if state.granted_queue_id:
                count += 1
            return count

    def get_status(self, server_key: str) -> dict:
        with self._lock:
            state = self._servers.get(server_key)
            if not state:
                return {}
            return {
                "server_key": server_key,
                "priority_queue": list(state.priority_queue),
                "normal_queue": list(state.normal_queue),
                "granted_queue_id": state.granted_queue_id,
            }

    def enqueue(self, steam_id: str, server_key: str, priority: str, queue_type: str) -> Dict[str, str]:
        target = get_target(server_key)
        if not target:
            return {"ok": False, "error": "unknown_server"}
        priority_norm = normalize_priority(priority)
        queue_id = str(uuid.uuid4())
        entry = QueueEntry(
            queue_id=queue_id,
            steam_id=steam_id,
            server_key=server_key,
            priority=priority_norm,
            queue_type=queue_type,
        )
        affected = []
        with self._lock:
            state = self._servers.setdefault(server_key, ServerQueueState())
            if priority_norm == "reserved":
                state.priority_queue.append(queue_id)
            else:
                state.normal_queue.append(queue_id)
            self._entries[queue_id] = entry
            affected = self._collect_queue_entries(state)
        for queued_entry in affected:
            self._emit_queued(queued_entry)
        return {"ok": True, "queue_id": queue_id}

    def mark_joined(self, queue_id: str, steam_id: str, server_key: str) -> Dict[str, str]:
        affected = []
        with self._lock:
            entry = self._entries.get(queue_id)
            if not entry or entry.steam_id != steam_id or entry.server_key != server_key:
                return {"ok": False, "error": "queue_not_found"}
            self._remove_from_queues(entry)
            entry.state = "joined"
            entry.grant_expires_at = None
            state = self._servers.get(server_key)
            affected = self._collect_queue_entries(state) if state else []
        self._emit_event(entry, "autojoin.joined")
        for queued_entry in affected:
            self._emit_queued(queued_entry)
        with self._lock:
            self._entries.pop(queue_id, None)
        return {"ok": True}

    def stop_queue(self, queue_id: str, steam_id: str, server_key: str) -> Dict[str, str]:
        affected = []
        with self._lock:
            entry = self._entries.get(queue_id)
            if not entry or entry.steam_id != steam_id or entry.server_key != server_key:
                return {"ok": False, "error": "queue_not_found"}
            self._remove_from_queues(entry)
            entry.state = "stopped"
            entry.grant_expires_at = None
            state = self._servers.get(server_key)
            affected = self._collect_queue_entries(state) if state else []
        self._emit_event(entry, "autojoin.stopped")
        for queued_entry in affected:
            self._emit_queued(queued_entry)
        with self._lock:
            self._entries.pop(queue_id, None)
        return {"ok": True}

    def handle_status(self, server_key: str, status) -> None:
        if status.a2s_unavailable:
            return
        with self._lock:
            state = self._servers.get(server_key)
            if not state:
                return
            if state.granted_queue_id:
                return
            head_id = self._peek_queue(state)
            if not head_id:
                state.debounce_count = 0
                state.debounce_queue_id = None
                return
            if state.debounce_queue_id != head_id:
                state.debounce_queue_id = head_id
                state.debounce_count = 0
            entry = self._entries.get(head_id)
            if not entry:
                state.debounce_count = 0
                return
            if should_attempt_join(entry.priority, status.players):
                state.debounce_count += 1
            else:
                state.debounce_count = 0
            if state.debounce_count < 2:
                return
            self._grant_locked(state, entry)
            affected = self._collect_queue_entries(state)
        for queued_entry in affected:
            self._emit_queued(queued_entry)

    def _grant_locked(self, state: ServerQueueState, entry: QueueEntry) -> None:
        state.debounce_count = 0
        state.debounce_queue_id = None
        state.granted_queue_id = entry.queue_id
        self._remove_from_queues(entry)
        entry.state = "granted"
        entry.grant_expires_at = now_ts() + GRANT_WINDOW_SECONDS
        self._emit_granted(entry)

    def _peek_queue(self, state: ServerQueueState) -> Optional[str]:
        if state.priority_queue:
            return state.priority_queue[0]
        if state.normal_queue:
            return state.normal_queue[0]
        return None

    def _remove_from_queues(self, entry: QueueEntry) -> None:
        state = self._servers.get(entry.server_key)
        if not state:
            return
        if entry.queue_id in state.priority_queue:
            state.priority_queue.remove(entry.queue_id)
        if entry.queue_id in state.normal_queue:
            state.normal_queue.remove(entry.queue_id)
        if state.granted_queue_id == entry.queue_id:
            state.granted_queue_id = None

    def _expiry_loop(self) -> None:
        while not self._stop.is_set():
            now = now_ts()
            expired_entries = []
            affected_entries = []
            with self._lock:
                for entry in list(self._entries.values()):
                    if entry.state == "granted" and entry.grant_expires_at and now >= entry.grant_expires_at:
                        expired_entries.append(entry)
                for entry in expired_entries:
                    state = self._servers.get(entry.server_key)
                    if not state:
                        continue
                    if state.granted_queue_id == entry.queue_id:
                        state.granted_queue_id = None
                    entry.state = "queued"
                    entry.grant_expires_at = None
                    if entry.priority == "reserved":
                        state.priority_queue.appendleft(entry.queue_id)
                    else:
                        state.normal_queue.appendleft(entry.queue_id)
                    affected_entries.extend(self._collect_queue_entries(state))
            for entry in expired_entries:
                self._emit_event(entry, "autojoin.expired", critical=True)
            for queued_entry in affected_entries:
                self._emit_queued(queued_entry)
            time.sleep(0.2)

    def _emit_event(self, entry: QueueEntry, event_type: str, extra: Optional[dict] = None, critical: bool = True) -> None:
        entry.seq += 1
        payload = {
            "type": event_type,
            "steam_id": entry.steam_id,
            "queue_id": entry.queue_id,
            "server_key": entry.server_key,
            "seq": entry.seq,
            "ts": now_ts(),
        }
        if extra:
            payload.update(extra)
        self.publisher.publish(payload, critical=critical)

    def _emit_queued(self, entry: QueueEntry) -> None:
        position = self._queue_position(entry)
        now = time.monotonic()
        if now - entry.last_noncritical_at < 1.0:
            return
        entry.last_noncritical_at = now
        self._emit_event(entry, "autojoin.queued", extra={"position": position}, critical=False)

    def _queue_position(self, entry: QueueEntry) -> int:
        state = self._servers.get(entry.server_key)
        if not state:
            return 1
        if entry.queue_id in state.priority_queue:
            return list(state.priority_queue).index(entry.queue_id) + 1
        if entry.queue_id in state.normal_queue:
            return len(state.priority_queue) + list(state.normal_queue).index(entry.queue_id) + 1
        return 1

    def _collect_queue_entries(self, state: Optional[ServerQueueState]) -> list[QueueEntry]:
        if not state:
            return []
        entries = []
        for queue_id in list(state.priority_queue) + list(state.normal_queue):
            entry = self._entries.get(queue_id)
            if entry:
                entries.append(entry)
        return entries

    def _emit_granted(self, entry: QueueEntry) -> None:
        target = get_target(entry.server_key) or {}
        game = target.get("game") or "cs2"
        fast_join_url = make_fast_join_url(game, target.get("ip"), target.get("port")) if target.get("ip") else None
        extra = {
            "grant_expires_in": GRANT_WINDOW_SECONDS,
            "fast_join_url": fast_join_url,
        }
        self._emit_event(entry, "autojoin.granted", extra=extra, critical=True)
