from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from .config import AutoJoinState, ClientConfig, clear_state, load_state, read_json, save_state, write_json
from .latency import a2s_info, median_rtt
from .scheduler import RateLimiter
from .web_api import WebAPI, ServerEntry


@dataclass
class PrecheckResult:
    success_count: int
    timeout_ratio: float
    median_rtt: Optional[float]


@dataclass
class AutoJoinMode:
    name: str
    watcher: bool


class AutoJoinController:
    def __init__(self, cfg: ClientConfig, api: WebAPI) -> None:
        self.cfg = cfg
        self.api = api
        self.settings = read_json(cfg.settings_path)

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

    def decide_mode(self, precheck: PrecheckResult, is_prime: bool) -> AutoJoinMode:
        stable = precheck.success_count >= 3 and precheck.timeout_ratio <= 0.4
        if stable:
            return AutoJoinMode(name="local", watcher=False)
        if is_prime:
            return AutoJoinMode(name="watcher", watcher=True)
        return AutoJoinMode(name="local", watcher=False)

    def run(self, server: ServerEntry) -> int:
        if not self.confirm_warning():
            print("AutoJoin aborted.")
            return 1
        is_prime = False
        try:
            status = self.api.get_steam_status()
            is_prime = bool(status.get("prime"))
        except Exception:
            pass
        precheck = self.run_precheck(server)
        mode = self.decide_mode(precheck, is_prime)
        if not mode.watcher and precheck.timeout_ratio > 0.4:
            print("Local A2S appears unstable; falling back to local mode with reduced frequency.")
        state = AutoJoinState(server_key=server.server_key, mode=mode.name, started_at=time.time())
        if mode.watcher:
            state.watcher_since = time.time()
        save_state(self.cfg, state)
        try:
            if mode.watcher:
                return self._run_watcher_mode(server)
            return self._run_local_mode(server, aggressive=precheck.timeout_ratio <= 0.4)
        finally:
            clear_state(self.cfg)

    def _run_local_mode(self, server: ServerEntry, aggressive: bool = True) -> int:
        interval = 0.3 if aggressive else 1.0
        limiter = RateLimiter(min_interval=interval, max_in_flight=10, max_backoff=3.0)
        print(f"Running AutoJoin in local mode for {server.name} ({server.server_key}).")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                limiter.acquire(server.server_key)
                result = a2s_info(server.ip, server.port, timeout=1.0)
                limiter.release()
                if result.ok:
                    limiter.record_success(server.server_key)
                    if result.players is not None and result.max_players is not None:
                        print(f"A2S: {result.players}/{result.max_players} players (RTT {result.rtt_ms:.1f} ms)")
                        if result.players < result.max_players:
                            print("Slot available! You can connect now:")
                            print(f"connect {server.server_key}")
                            return 0
                    else:
                        print("A2S response ok but missing player data.")
                else:
                    limiter.record_failure(server.server_key)
                    print("A2S timeout; retrying...")
        except KeyboardInterrupt:
            print("AutoJoin stopped by user.")
            return 0

    def _run_watcher_mode(self, server: ServerEntry) -> int:
        print(f"Running AutoJoin in watcher mode for {server.name} ({server.server_key}).")
        print("Press Ctrl+C to stop.")
        try:
            join_resp = self.api.autojoin_join(server.server_key)
        except Exception as exc:
            print(f"Watcher join unreachable: {exc}")
            return self._run_local_mode(server, aggressive=False)
        if not join_resp.get("ok"):
            if join_resp.get("error") == "prime_required":
                print("Prime required for watcher mode. Falling back to local mode.")
                return self._run_local_mode(server, aggressive=False)
            print(f"Watcher join failed: {join_resp.get('error')}")
            return 1
        start = time.time()
        last_ticket = None
        try:
            while True:
                try:
                    poll = self.api.autojoin_poll(server.server_key)
                except Exception as exc:
                    print(f"Watcher poll unreachable: {exc}")
                    return self._run_local_mode(server, aggressive=False)
                if poll.get("error") == "prime_required":
                    print("Prime required for watcher mode. Falling back to local mode.")
                    return self._run_local_mode(server, aggressive=False)
                if not poll.get("ok"):
                    print(f"Watcher poll error: {poll.get('error')}")
                    time.sleep(1.0)
                    continue
                if poll.get("granted"):
                    ticket_id = poll.get("ticket_id")
                    if ticket_id and ticket_id != last_ticket:
                        last_ticket = ticket_id
                        print("Join slot granted!")
                        fast_url = poll.get("fast_join_url")
                        if fast_url:
                            print(f"Fast join URL: {fast_url}")
                        expires = poll.get("expires_in")
                        if expires:
                            print(f"Expires in {expires} seconds.")
                    time.sleep(1.0)
                    continue
                position = poll.get("position")
                if isinstance(position, int):
                    print(f"Queue position: {position}")
                elapsed = time.time() - start
                if elapsed < 60:
                    time.sleep(0.5)
                else:
                    time.sleep(1.0)
        except KeyboardInterrupt:
            self.api.autojoin_leave(server.server_key)
            print("AutoJoin stopped by user.")
            return 0


def stop_autojoin(cfg: ClientConfig, api: WebAPI) -> int:
    state = load_state(cfg)
    if not state:
        print("No active AutoJoin state found.")
        return 0
    if state.mode == "watcher":
        try:
            resp = api.autojoin_leave(state.server_key)
            if not resp.get("ok"):
                print(f"Watcher leave failed: {resp.get('error')}")
        except Exception as exc:
            print(f"Watcher leave failed: {exc}")
    clear_state(cfg)
    print("AutoJoin stopped.")
    return 0
