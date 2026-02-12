import json
import os
import socket
import time
from concurrent.futures import ThreadPoolExecutor

import a2s
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _require_env(*names: str) -> str:
    for name in names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    raise RuntimeError(f"Missing required environment variable(s): {', '.join(names)}")


def load_runtime_config() -> dict:
    return {
        "master_url": _require_env("AGENT_MASTER_URL", "MASTER_URL").rstrip("/"),
        "agent_token": _require_env("AGENT_SHARED_TOKEN", "AGENT_TOKEN"),
        "config_file": os.environ.get("AGENT_CONFIG_FILE", "config.json"),
        "poll_interval_seconds": int(os.environ.get("AGENT_POLL_INTERVAL_SECONDS", "15")),
        "request_timeout_seconds": float(os.environ.get("AGENT_REQUEST_TIMEOUT_SECONDS", "5")),
        "a2s_timeout_seconds": float(os.environ.get("AGENT_A2S_TIMEOUT_SECONDS", "2")),
        "max_workers": max(1, int(os.environ.get("AGENT_MAX_WORKERS", "10"))),
    }


def fetch_server_data(server_cfg: dict, a2s_timeout_seconds: float) -> dict:
    host = server_cfg["host"]
    port = server_cfg["port"]
    name = server_cfg.get("name", "")

    try:
        resolved_ip = socket.gethostbyname(host)
    except Exception:
        resolved_ip = None

    result = {
        "ip": host,
        "connect_ip": resolved_ip or host,
        "port": port,
        "display_ip": f"{host}:{port}",
        "name": name,
        "map": "-",
        "players": 0,
        "max_players": 0,
        "online": False,
        "ping": -1,
        "game_type": "cs2",
    }

    try:
        info = a2s.info((host, port), timeout=a2s_timeout_seconds)
        result.update(
            {
                "online": True,
                "name": info.server_name,
                "map": info.map_name,
                "players": info.player_count,
                "max_players": info.max_players,
                "ping": int(info.ping * 1000),
            }
        )
    except Exception:
        pass

    return result


def run_agent() -> None:
    try:
        cfg = load_runtime_config()
    except RuntimeError as exc:
        print(f"[Fatal] {exc}")
        return

    print(f"[*] Agent started | master={cfg['master_url']}")

    while True:
        try:
            if not os.path.exists(cfg["config_file"]):
                print(f"[Error] {cfg['config_file']} not found.")
                time.sleep(min(10, cfg["poll_interval_seconds"]))
                continue

            with open(cfg["config_file"], "r", encoding="utf-8") as handle:
                local_config = json.load(handle)

            non_cn_communities = [
                community
                for community in local_config.get("communities", [])
                if community.get("location") != "cn"
            ]

            payload = {"communities": {}}
            for community in non_cn_communities:
                print(f"[Job] Refreshing community: {community.get('id', '-')}")
                with ThreadPoolExecutor(max_workers=cfg["max_workers"]) as executor:
                    results = list(
                        executor.map(
                            lambda server: fetch_server_data(server, cfg["a2s_timeout_seconds"]),
                            community.get("servers", []),
                        )
                    )
                payload["communities"][community["id"]] = results

            if payload["communities"]:
                requests.post(
                    f"{cfg['master_url']}/api/agent/update",
                    json=payload,
                    headers={"Authorization": f"Bearer {cfg['agent_token']}"},
                    timeout=cfg["request_timeout_seconds"],
                )
        except Exception as exc:
            print(f"[Error] main loop failed: {exc}")

        time.sleep(cfg["poll_interval_seconds"])


if __name__ == "__main__":
    run_agent()
