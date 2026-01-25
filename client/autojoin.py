from __future__ import annotations

import json
import queue
import threading
import time
import webbrowser
from dataclasses import dataclass
from typing import List, Optional

import requests
from websocket import WebSocketApp

from autojoin_policy import normalize_priority, should_attempt_join
from .config import AutoJoinState, ClientConfig, clear_state, load_state, read_json, save_state, write_json
from .latency import a2s_info, median_rtt
from .scheduler import RateLimiter
from .web_api import WebAPI, ServerEntry

APP_ID_BY_GAME = {"cs2": 730, "css": 240}
LAUNCH_COOLDOWN_SECONDS = 10.0
JOIN_COOLDOWN_SECONDS = 2.5


@dataclass
class PrecheckResult:
    success_count: int
    timeout_ratio: float
    median_rtt: Optional[float]


@dataclass
class AutoJoinMode:
    name: str
    watcher: bool


@dataclass
class NetProfileResult:
    profile: str
    google_ok: bool


class AutoJoinWSClient:
    def __init__(self, url: str, headers: list[str]) -> None:
        self.url = url
        self.headers = headers
        self.queue: queue.Queue[dict] = queue.Queue()
        self._stop = False
        self._thread = None

    def start(self) -> None:
        if self._thread:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop:
            ws_app = WebSocketApp(
                self.url,
                header=self.headers,
                on_message=self._on_message,
            )
            ws_app.run_forever(ping_interval=20, ping_timeout=5)
            if self._stop:
                break
            time.sleep(backoff)
            backoff = min(10.0, backoff * 1.5)

    def _on_message(self, _ws, message: str) -> None:
        try:
            payload = json.loads(message)
        except Exception:
            return
        if isinstance(payload, dict):
            self.queue.put(payload)

    def next_event(self, timeout: float = 1.0) -> Optional[dict]:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None


class AutoJoinController:
    def __init__(self, cfg: ClientConfig, api: WebAPI, auto_connect: bool = False) -> None:
        self.cfg = cfg
        self.api = api
        self.auto_connect = auto_connect
        self.settings = read_json(cfg.settings_path)
        self._last_launch_at: float | None = None

    def _save_settings(self) -> None:
        write_json(self.cfg.settings_path, self.settings)

    def confirm_warning(self) -> bool:
        if self.settings.get("skip_autojoin_warning"):
            return True
        print("WARNING: AutoJoin will send frequent server queries (up to 3–5 per second).")
        print("This may cause network instability or trigger server rate limits.")
        resp = input("Continue? [y/N] ").strip().lower()
        if resp == "y":
            skip = input("Don't show this warning again? [y/N] ").strip().lower()
            if skip == "y":
                self.settings["skip_autojoin_warning"] = True
                self._save_settings()
            return True
        return False

    def run_precheck(self, server: ServerEntry) -> PrecheckResult:
        probes = 5
        interval = 1.0
        success = 0
        samples: List[float] = []
        for _ in range(probes):
            result = a2s_info(server.ip, server.port, timeout=1.0)
            if result.ok and result.rtt_ms is not None:
                success += 1
                samples.append(result.rtt_ms)
            time.sleep(interval)
        timeout_ratio = 1.0 - (success / probes)
        return PrecheckResult(success_count=success, timeout_ratio=timeout_ratio, median_rtt=median_rtt(samples))

    def _determine_net_profile(self) -> NetProfileResult:
        tz_offset = time.localtime().tm_gmtoff if hasattr(time, "localtime") else 0
        tz_cn = tz_offset == 8 * 3600
        google_ok = False
        try:
            resp = requests.get("https://www.google.com/generate_204", timeout=2)
            google_ok = resp.status_code in {200, 204}
        except Exception:
            google_ok = False
        if google_ok:
            return NetProfileResult(profile="NonCN_like", google_ok=True)
        if tz_cn:
            return NetProfileResult(profile="CN_like", google_ok=False)
        return NetProfileResult(profile="Unknown", google_ok=False)

    def _resolve_server_region(self, server: ServerEntry) -> str:
        raw = server.raw or {}
        for key in ("location", "region", "area", "country"):
            value = raw.get(key)
            if isinstance(value, str) and value:
                return value.lower()
        return "unknown"

    def _should_use_watcher(self, server_region: str, net_profile: str, precheck: PrecheckResult) -> bool:
        cross_region = (server_region == "cn" and net_profile == "NonCN_like") or (
            server_region in {"us", "eu", "global"} and net_profile == "CN_like"
        )
        if cross_region:
            return True
        return precheck.timeout_ratio > 0.4

    def _ask_priority(self) -> str:
        resp = input("Do you have priority access? [y/N] ").strip().lower()
        return "reserved" if resp == "y" else "none"

    def decide_mode(self, precheck: PrecheckResult, watcher_available: bool, server_region: str, net_profile: str) -> AutoJoinMode:
        if watcher_available and self._should_use_watcher(server_region, net_profile, precheck):
            return AutoJoinMode(name="watcher", watcher=True)
        return AutoJoinMode(name="local", watcher=False)

    def run(self, server: ServerEntry) -> int:
        if not self.confirm_warning():
            print("AutoJoin aborted.")
            return 1
        watcher_available = bool(self.cfg.base_url and self.cfg.session_cookie)
        precheck = self.run_precheck(server)
        server_region = self._resolve_server_region(server)
        net_profile = self._determine_net_profile().profile
        mode = self.decide_mode(precheck, watcher_available, server_region, net_profile)
        if not mode.watcher and precheck.timeout_ratio > 0.4:
            print("Local A2S appears unstable; falling back to local mode with reduced frequency.")
        priority = normalize_priority(self._ask_priority())
        state = AutoJoinState(
            server_key=server.server_key,
            mode=mode.name,
            priority=priority,
            started_at=time.time(),
        )
        if mode.watcher:
            state.watcher_since = time.time()
        save_state(self.cfg, state)
        try:
            if mode.watcher:
                return self._run_watcher_mode(server, priority, server_region, net_profile)
            return self._run_local_mode(server, priority, aggressive=precheck.timeout_ratio <= 0.4)
        finally:
            clear_state(self.cfg)

    def _run_local_mode(self, server: ServerEntry, priority: str, aggressive: bool = True) -> int:
        interval = 0.3 if aggressive else 1.0
        limiter = RateLimiter(min_interval=interval, max_in_flight=10, max_backoff=3.0)
        print(f"Running AutoJoin in local mode for {server.name} ({server.server_key}).")
        print("Press Ctrl+C to stop.")
        consecutive = 0
        last_attempt = 0.0
        try:
            while True:
                limiter.acquire(server.server_key)
                result = a2s_info(server.ip, server.port, timeout=1.0)
                limiter.release()
                if result.ok:
                    limiter.record_success(server.server_key)
                    if result.players is not None and result.max_players is not None:
                        print(f"A2S: {result.players}/{result.max_players} players (RTT {result.rtt_ms:.1f} ms)")
                        if should_attempt_join(priority, result.players):
                            consecutive += 1
                        else:
                            consecutive = 0
                        if consecutive >= 2 and time.time() - last_attempt >= JOIN_COOLDOWN_SECONDS:
                            print("Slot available! You can connect now:")
                            self._launch_game(server)
                            print(f"connect {server.connect_target}")
                            last_attempt = time.time()
                            consecutive = 0
                    else:
                        print("A2S response ok but missing player data.")
                else:
                    limiter.record_failure(server.server_key)
                    print("A2S timeout; retrying...")
        except KeyboardInterrupt:
            print("AutoJoin stopped by user.")
            return 0

    def _run_watcher_mode(self, server: ServerEntry, priority: str, server_region: str, net_profile: str) -> int:
        print(f"Running AutoJoin in watcher mode for {server.name} ({server.server_key}).")
        print("Press Ctrl+C to stop.")
        watcher_region = "cn" if server_region == "cn" else "us"
        ws_url = self.api.ws_url("/ws/autojoin")
        headers = []
        if self.cfg.session_cookie:
            headers.append(f"Cookie: {self.cfg.session_cookie}")
        ws_client = AutoJoinWSClient(ws_url, headers)
        ws_client.start()
        join_resp = self.api.autojoin_start(
            {
                "server_key": server.server_key,
                "server_region": server_region,
                "queue_type": "normal",
                "priority": priority,
                "net_profile": net_profile,
            }
        )
        if not join_resp.get("ok"):
            error = join_resp.get("error")
            if error in {"prime_required", "unauthorized", "watcher_unavailable", "watcher_not_allowed"}:
                print("Watcher unavailable; falling back to local mode.")
                return self._run_local_mode(server, priority, aggressive=False)
            print(f"Watcher join failed: {error}")
            return 1
        queue_id = join_resp.get("queue_id")
        if not queue_id:
            print("Watcher did not return queue_id; aborting.")
            return 1
        state = load_state(self.cfg)
        if state:
            state.queue_id = queue_id
            state.watcher_region = watcher_region
            state.priority = priority
            save_state(self.cfg, state)
        last_seq = 0
        try:
            while True:
                event = ws_client.next_event(timeout=1.0)
                if not event:
                    continue
                if event.get("queue_id") != queue_id:
                    continue
                seq = int(event.get("seq") or 0)
                if seq <= last_seq:
                    continue
                last_seq = seq
                event_type = event.get("type")
                if event_type == "autojoin.granted":
                    print("Join slot granted!")
                    fast_url = event.get("fast_join_url")
                    if fast_url:
                        print(f"Fast join URL: {fast_url}")
                    self._launch_game(server, url_override=fast_url)
                    self.api.autojoin_joined(
                        {"queue_id": queue_id, "server_key": server.server_key, "watcher_region": watcher_region}
                    )
                elif event_type == "autojoin.queued":
                    position = event.get("position")
                    if isinstance(position, int):
                        print(f"Queue position: {position}")
                elif event_type == "autojoin.expired":
                    print("Join slot expired; continuing to queue...")
                elif event_type == "autojoin.stopped":
                    print("AutoJoin stopped by watcher.")
                    return 0
                elif event_type == "autojoin.error":
                    print(f"AutoJoin error: {event.get('message') or event.get('error')}")
                    return 1
        except KeyboardInterrupt:
            self.api.autojoin_stop(
                {"queue_id": queue_id, "server_key": server.server_key, "watcher_region": watcher_region}
            )
            print("AutoJoin stopped by user.")
            return 0
        finally:
            ws_client.stop()

    def _launch_game(self, server: ServerEntry, url_override: Optional[str] = None) -> None:
        if not self.auto_connect:
            return
        now = time.time()
        if self._last_launch_at and (now - self._last_launch_at) < LAUNCH_COOLDOWN_SECONDS:
            return
        if url_override:
            url = url_override
        else:
            app_id = APP_ID_BY_GAME.get(server.game_type)
            if not app_id:
                print(f"Unknown game type '{server.game_type}'; unable to launch automatically.")
                return
            url = f"steam://rungameid/{app_id}//+connect%20{server.connect_target}"
        print(f"Launching game via Steam: {url}")
        try:
            webbrowser.open(url)
            self._last_launch_at = now
        except Exception as exc:
            print(f"Failed to launch Steam URL: {exc}")


def stop_autojoin(cfg: ClientConfig, api: WebAPI) -> int:
    state = load_state(cfg)
    if not state:
        print("No active AutoJoin state found.")
        return 0
    if state.mode == "watcher" and state.queue_id and state.watcher_region:
        resp = api.autojoin_stop(
            {"queue_id": state.queue_id, "server_key": state.server_key, "watcher_region": state.watcher_region}
        )
        if not resp.get("ok"):
            print(f"Watcher stop failed: {resp.get('error')}")
    clear_state(cfg)
    print("AutoJoin stopped.")
    return 0
