import os
import sys
import threading
import time
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from watcher_utils import load_config, now_ts
from watcher_targets import upsert_target, list_targets
from watcher_exg import ExgDiscovery
from watcher_a2s import query_a2s
from a2s_cache import A2SCache
from autojoin_service import AutoJoinService
from event_publisher import EventPublisher, RateLimitedPublisher
from http_api import create_app
from queue_manager import QueueManager


def start_agent_pull(cfg):
    main_site = cfg.get("main_site", {})
    base_url = (main_site.get("base_url") or "http://127.0.0.1:5000").rstrip("/")
    shared_token = main_site.get("shared_token") or cfg.get("http", {}).get("shared_token")
    interval = 5
    if not shared_token:
        return

    def loop():
        while True:
            try:
                resp = requests.get(f"{base_url}/api/agent/status", headers={"X-Shared-Token": shared_token}, timeout=4)
                data = resp.json() if resp.ok else {}
                servers = data.get("servers") or []
            except Exception:
                servers = []
            now = now_ts()
            for srv in servers:
                if not isinstance(srv, dict):
                    continue
                meta = {
                    "server_key": srv.get("server_key"),
                    "ip": srv.get("ip"),
                    "port": srv.get("port"),
                    "name": srv.get("name") or "Unknown",
                    "players": srv.get("players") or 0,
                    "max_players": srv.get("max_players") or 64,
                    "game": srv.get("game") or "cs2",
                    "community_id": srv.get("community_id") or "",
                    "source_type": "agent_push",
                    "updated_at": int(srv.get("updated_at") or now),
                    "last_seen_ts": now,
                    "state": "active",
                }
                upsert_target(meta)
            time.sleep(interval)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


def start_static_a2s_poll(cfg):
    communities = cfg.get("communities") or []
    location_by_id = {str(c.get("id")): c.get("location") for c in communities}

    def loop():
        while True:
            targets = list_targets()
            for t in targets:
                if t.get("source_type") != "static_a2s":
                    continue
                if location_by_id.get(t.get("community_id")) == "cn":
                    continue
                info = query_a2s(t["ip"], t["port"], timeout=1.5)
                if info:
                    upsert_target(
                        {
                            "server_key": t["server_key"],
                            "ip": t["ip"],
                            "port": t["port"],
                            "name": info.get("name") or t.get("name") or "Unknown",
                            "players": info.get("players") or 0,
                            "max_players": info.get("max_players") or t.get("max_players") or 64,
                            "game": t.get("game") or "cs2",
                            "community_id": t.get("community_id"),
                            "source_type": t.get("source_type"),
                            "updated_at": now_ts(),
                            "last_seen_ts": now_ts(),
                            "state": "active",
                        }
                    )
            time.sleep(1)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()


def load_static_targets(cfg):
    communities = cfg.get("communities") or []
    for comm in communities:
        if not comm.get("enabled"):
            continue
        if comm.get("source_type") != "static_a2s":
            continue
        servers = comm.get("servers") or []
        for srv in servers:
            ip = srv.get("ip")
            port = srv.get("port")
            if not ip or not port:
                continue
            upsert_target(
                {
                    "server_key": f"{ip}:{port}",
                    "ip": ip,
                    "port": port,
                    "name": srv.get("name") or "Unknown",
                    "players": 0,
                    "max_players": srv.get("max_players") or 64,
                    "game": comm.get("game") or "cs2",
                    "community_id": comm.get("id"),
                    "source_type": "static_a2s",
                    "updated_at": now_ts(),
                    "last_seen_ts": now_ts(),
                    "state": "active",
                }
            )


def main():
    cfg = load_config()
    load_static_targets(cfg)
    exg_communities = [c for c in (cfg.get("communities") or []) if c.get("source_type") == "exg_api"]
    exg_discovery = ExgDiscovery(exg_communities)
    exg_discovery.start()
    start_agent_pull(cfg)
    start_static_a2s_poll(cfg)

    main_site = cfg.get("main_site", {})
    base_url = (main_site.get("base_url") or "http://127.0.0.1:5000").rstrip("/")
    watcher_id = main_site.get("watcher_id") or "watcher"
    hmac_secret = main_site.get("hmac_secret") or ""
    if not hmac_secret:
        raise RuntimeError("watcher_config.json main_site.hmac_secret is required")
    publisher = RateLimitedPublisher(EventPublisher(base_url, watcher_id, hmac_secret), "/api/watcher/event")

    queue_manager = QueueManager(publisher)
    a2s_cache = A2SCache(queue_manager.get_queue_count, queue_manager.handle_status)
    a2s_cache.start()
    service = AutoJoinService(queue_manager, a2s_cache)

    http_cfg = cfg.get("http") or {}
    host = http_cfg.get("host") or "127.0.0.1"
    port = int(http_cfg.get("port") or 5010)
    shared_token = http_cfg.get("shared_token")
    if not shared_token:
        raise RuntimeError("watcher_config.json http.shared_token is required")
    app = create_app(service, shared_token)
    app.run(host=host, port=port, debug=False, threaded=False)


if __name__ == "__main__":
    main()
