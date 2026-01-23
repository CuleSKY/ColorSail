import threading
import time
import secrets
from collections import deque
from watcher_targets import get_target, update_status
from watcher_utils import now_ts, make_fast_join_url
from watcher_a2s import query_a2s


class ServerWatcher:
    def __init__(self, manager, server_key):
        self.manager = manager
        self.server_key = server_key
        self.priority_queue = deque()
        self.normal_queue = deque()
        self.pending_ticket = None
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.a2s_fail_count = 0

    def start(self):
        target = get_target(self.server_key)
        if target and target.get('source_type') == 'exg_api':
            update_status(self.server_key, a2s_unavailable=False)
            self.a2s_fail_count = 0
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=2)

    def _run(self):
        poll_interval = 1.0 / max(1, self.manager.poll_hz)
        while not self.stop_event.is_set():
            now = now_ts()
            if self.pending_ticket and self.pending_ticket['expires_at'] <= now:
                self.manager.handle_ticket_timeout(self.server_key, self.pending_ticket)
                self.pending_ticket = None
            if self.pending_ticket:
                time.sleep(poll_interval)
                continue
            if not self.priority_queue and not self.normal_queue:
                break
            target = get_target(self.server_key)
            if target:
                self._maybe_a2s_scan(target)
            players = int((target or {}).get('players') or 0)
            normal_threshold = self.manager.default_normal_threshold
            priority_threshold = self.manager.default_priority_threshold
            if players < normal_threshold:
                next_id = self._pop_next_any()
            elif players < priority_threshold:
                next_id = self._pop_next_priority()
            else:
                next_id = None
            if next_id:
                self.pending_ticket = self.manager.issue_ticket(self.server_key, next_id)
            time.sleep(poll_interval)
        self.manager.remove_watcher(self.server_key)

    def _pop_next_priority(self):
        return self.priority_queue.popleft() if self.priority_queue else None

    def _pop_next_any(self):
        if self.priority_queue:
            return self.priority_queue.popleft()
        if self.normal_queue:
            return self.normal_queue.popleft()
        return None

    def _maybe_a2s_scan(self, target):
        if target.get('source_type') != 'exg_api':
            return
        if target.get('a2s_unavailable'):
            return
        info = query_a2s(target['ip'], target['port'], timeout=1.5)
        if info:
            update_status(
                self.server_key,
                players=int(info.get('players') or 0),
                max_players=int(info.get('max_players') or target.get('max_players') or 64),
                name=info.get('name') or target.get('name') or "Unknown",
                updated_at=now_ts()
            )
            self.a2s_fail_count = 0
        else:
            self.a2s_fail_count += 1
            if self.a2s_fail_count >= 5:
                update_status(self.server_key, a2s_unavailable=True)


class AutoJoinManager:
    def __init__(self, cfg):
        limits = cfg.get('limits', {})
        thresholds = cfg.get('thresholds', {})
        self.poll_hz = int(limits.get('poll_hz') or 1)
        self.ticket_ttl_seconds = int(limits.get('ticket_ttl_seconds') or 12)
        self.user_fail_cooldown_seconds = int(limits.get('user_fail_cooldown_seconds') or 20)
        self.max_active_watchers = int(limits.get('max_active_watchers') or 100)
        self.max_queue_per_server = int(limits.get('max_queue_per_server') or 100)
        self.max_tasks_per_user = int(limits.get('max_tasks_per_user') or 1)
        self.default_normal_threshold = int(thresholds.get('default_normal_threshold') or 62)
        self.default_priority_threshold = int(thresholds.get('default_priority_threshold') or 64)
        self.default_max_players = int(thresholds.get('default_max_players') or 64)
        self.watchers = {}
        self.user_tasks = {}
        self.user_cooldowns = {}
        self.lock = threading.Lock()

    def _get_watcher(self, server_key):
        watcher = self.watchers.get(server_key)
        if watcher:
            return watcher
        if len(self.watchers) >= self.max_active_watchers:
            return None
        watcher = ServerWatcher(self, server_key)
        self.watchers[server_key] = watcher
        watcher.start()
        return watcher

    def remove_watcher(self, server_key):
        with self.lock:
            self.watchers.pop(server_key, None)

    def issue_ticket(self, server_key, steam_id):
        target = get_target(server_key) or {}
        now = now_ts()
        ticket = {
            "ticket_id": secrets.token_urlsafe(8),
            "steam_id": steam_id,
            "server_key": server_key,
            "expires_at": now + self.ticket_ttl_seconds,
            "fast_join_url": make_fast_join_url(target.get('game') or 'cs2', target.get('ip'), target.get('port'))
        }
        return ticket

    def join(self, steam_id, server_key, queue_type):
        if not steam_id or not server_key:
            return {"ok": False, "error": "missing_fields"}
        queue_type = queue_type or "normal"
        if queue_type not in ("normal", "priority"):
            return {"ok": False, "error": "invalid_queue_type"}
        if server_key and not get_target(server_key):
            return {"ok": False, "error": "unknown_server"}
        now = now_ts()
        with self.lock:
            cooldown = self.user_cooldowns.get(steam_id)
            if cooldown and now < cooldown:
                return {"ok": False, "error": "cooldown"}
            if steam_id in self.user_tasks:
                return {"ok": False, "error": "already_queued"}
            watcher = self._get_watcher(server_key)
            if not watcher:
                return {"ok": False, "error": "too_many_watchers"}
            total_q = len(watcher.priority_queue) + len(watcher.normal_queue)
            if total_q >= self.max_queue_per_server:
                return {"ok": False, "error": "queue_full"}
            if queue_type == "priority":
                watcher.priority_queue.append(steam_id)
            else:
                watcher.normal_queue.append(steam_id)
            self.user_tasks[steam_id] = {"server_key": server_key, "queue_type": queue_type}
        return {"ok": True}

    def poll(self, steam_id, server_key):
        if not steam_id or not server_key:
            return {"ok": False, "error": "missing_fields"}
        watcher = self.watchers.get(server_key)
        if not watcher:
            return {"ok": True, "granted": False, "position": 0}
        if watcher.pending_ticket and watcher.pending_ticket.get('steam_id') == steam_id:
            expires_in = max(0, watcher.pending_ticket['expires_at'] - now_ts())
            return {
                "ok": True,
                "granted": True,
                "ticket_id": watcher.pending_ticket['ticket_id'],
                "expires_in": expires_in,
                "fast_join_url": watcher.pending_ticket['fast_join_url']
            }
        try:
            if steam_id in watcher.priority_queue:
                position = list(watcher.priority_queue).index(steam_id) + 1
            elif steam_id in watcher.normal_queue:
                position = len(watcher.priority_queue) + list(watcher.normal_queue).index(steam_id) + 1
            else:
                position = 0
        except ValueError:
            position = 0
        return {"ok": True, "granted": False, "position": position}

    def report(self, steam_id, ticket_id, result):
        if not steam_id or not ticket_id:
            return {"ok": False, "error": "missing_fields"}
        watcher = None
        for w in self.watchers.values():
            if w.pending_ticket and w.pending_ticket['ticket_id'] == ticket_id:
                watcher = w
                break
        if not watcher or watcher.pending_ticket.get('steam_id') != steam_id:
            return {"ok": False, "error": "ticket_not_found"}
        if result == "success":
            watcher.pending_ticket = None
            with self.lock:
                self.user_tasks.pop(steam_id, None)
            return {"ok": True}
        if result in ("failed", "timeout"):
            watcher.pending_ticket = None
            with self.lock:
                self.user_cooldowns[steam_id] = now_ts() + self.user_fail_cooldown_seconds
                task = self.user_tasks.get(steam_id)
                if task:
                    if task.get('queue_type') == 'priority':
                        watcher.priority_queue.append(steam_id)
                    else:
                        watcher.normal_queue.append(steam_id)
            return {"ok": True}
        return {"ok": False, "error": "invalid_result"}

    def leave(self, steam_id, server_key):
        watcher = self.watchers.get(server_key)
        if watcher:
            try:
                watcher.priority_queue.remove(steam_id)
            except ValueError:
                pass
            try:
                watcher.normal_queue.remove(steam_id)
            except ValueError:
                pass
            if watcher.pending_ticket and watcher.pending_ticket.get('steam_id') == steam_id:
                watcher.pending_ticket = None
        with self.lock:
            self.user_tasks.pop(steam_id, None)
        return {"ok": True}

    def handle_ticket_timeout(self, server_key, ticket):
        steam_id = ticket.get('steam_id')
        if not steam_id:
            return
        watcher = self.watchers.get(server_key)
        if not watcher:
            return
        with self.lock:
            self.user_cooldowns[steam_id] = now_ts() + self.user_fail_cooldown_seconds
            task = self.user_tasks.get(steam_id)
            if task:
                if task.get('queue_type') == 'priority':
                    watcher.priority_queue.append(steam_id)
                else:
                    watcher.normal_queue.append(steam_id)
