from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

from .autojoin import AutoJoinController, stop_autojoin
from .config import ClientConfig, load_config, update_config_url
from .latency import DisplayChoice, ProbeResult, a2s_info, choose_display, ping_icmp
from .scheduler import RateLimiter
from .web_api import ServerEntry, WebAPI


def resolve_server(servers: List[ServerEntry], identifier: str) -> ServerEntry:
    if identifier.isdigit():
        idx = int(identifier)
        if idx < 0 or idx >= len(servers):
            raise ValueError("Index out of range")
        return servers[idx]
    for srv in servers:
        if srv.server_key == identifier:
            return srv
    raise ValueError("Server not found")


def format_latency(choice: DisplayChoice) -> str:
    if choice.source == "timeout" or choice.rtt_ms is None:
        return "timeout"
    return f"{choice.rtt_ms:.1f} ms ({choice.source})"


def list_servers(api: WebAPI) -> int:
    servers = api.fetch_servers()
    if not servers:
        print("No servers found.")
        return 1

    results: Dict[str, Tuple[ProbeResult, ProbeResult, DisplayChoice]] = {}
    limiter = RateLimiter(min_interval=2.0, max_in_flight=12, max_backoff=3.0)

    def probe(server: ServerEntry) -> Tuple[str, ProbeResult, ProbeResult]:
        icmp = ping_icmp(server.ip)
        limiter.acquire(server.server_key)
        a2s = a2s_info(server.ip, server.port)
        limiter.release()
        if a2s.ok:
            limiter.record_success(server.server_key)
        else:
            limiter.record_failure(server.server_key)
        return server.server_key, icmp, a2s

    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = [executor.submit(probe, server) for server in servers]
        for fut in as_completed(futures):
            key, icmp, a2s = fut.result()
            choice = choose_display(icmp, a2s, None, None)
            results[key] = (icmp, a2s, choice)

    print(f"{'#':<3} {'Game':<4} {'Server':<32} {'Players':<12} {'Latency':<16}")
    for idx, server in enumerate(servers):
        icmp, a2s, choice = results.get(server.server_key, (ProbeResult(False, None), ProbeResult(False, None), DisplayChoice("timeout", None)))
        latency = format_latency(choice)
        players = f"{server.players}/{server.max_players}"
        print(f"{idx:<3} {server.game_type:<4} {server.name[:32]:<32} {players:<12} {latency:<16}")
    return 0


def probe_server(api: WebAPI, identifier: str) -> int:
    servers = api.fetch_servers()
    try:
        server = resolve_server(servers, identifier)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    icmp = ping_icmp(server.ip)
    a2s = a2s_info(server.ip, server.port)
    choice = choose_display(icmp, a2s, None, None)
    print(f"Server: {server.name} ({server.server_key})")
    print(f"Game: {server.game_type}")
    print(f"ICMP: {'ok' if icmp.ok else 'fail'}", end="")
    if icmp.rtt_ms is not None:
        print(f" {icmp.rtt_ms:.1f} ms")
    else:
        print("")
    print(f"A2S: {'ok' if a2s.ok else 'fail'}", end="")
    if a2s.rtt_ms is not None:
        print(f" {a2s.rtt_ms:.1f} ms")
    else:
        print("")
    print(f"Display: {format_latency(choice)}")
    return 0


def autojoin_server(cfg: ClientConfig, api: WebAPI, identifier: str, auto_connect: bool) -> int:
    servers = api.fetch_servers()
    try:
        server = resolve_server(servers, identifier)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1
    controller = AutoJoinController(cfg, api, auto_connect=auto_connect)
    return controller.run(server)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cs2ze", description="CS2ZE CLI client")
    parser.add_argument("--server-list-url", help="Override server list URL for this run")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List servers")

    probe_cmd = sub.add_parser("probe", help="Probe one server")
    probe_cmd.add_argument("target", help="Index or server_key")

    auto_cmd = sub.add_parser("autojoin", help="Start AutoJoin")
    auto_cmd.add_argument("target", help="Index or server_key")
    auto_cmd.add_argument("--auto-connect", action="store_true", help="Launch the game automatically when a slot opens")

    sub.add_parser("stop", help="Stop AutoJoin")

    return parser


def ensure_server_list_url(cfg: ClientConfig, api: WebAPI, override_url: str | None) -> ClientConfig:
    url = override_url or cfg.server_list_url
    if url:
        try:
            api.fetch_servers_from_url(url)
            if override_url:
                return replace(cfg, server_list_url=url)
            return cfg
        except Exception as exc:
            print(f"Server list URL invalid: {exc}")
    while True:
        try:
            url = input("Enter server list URL: ").strip()
        except KeyboardInterrupt:
            print("\nAborted.")
            raise
        if not url:
            continue
        try:
            api.fetch_servers_from_url(url)
        except Exception as exc:
            print(f"Server list URL invalid: {exc}")
            continue
        cfg = update_config_url(cfg, url)
        print("Server list URL saved to client/config.json.")
        return cfg


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    cfg = load_config()
    api = WebAPI(cfg)
    if args.command in {"list", "probe", "autojoin"}:
        cfg = ensure_server_list_url(cfg, api, args.server_list_url)
        api = WebAPI(cfg)

    if args.command == "list":
        return list_servers(api)
    if args.command == "probe":
        return probe_server(api, args.target)
    if args.command == "autojoin":
        return autojoin_server(cfg, api, args.target, args.auto_connect)
    if args.command == "stop":
        return stop_autojoin(cfg, api)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
