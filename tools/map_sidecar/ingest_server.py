from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable, Optional

if __package__:
    from .config import load_settings
    from .db import MySQLClient
    from .exporter import atomic_write_json
    from .logging_utils import setup_logging
    from .redis_cache import RedisCache
    from .utils import convert_to_traditional, normalize_map_key
else:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import load_settings  # type: ignore
    from db import MySQLClient  # type: ignore
    from exporter import atomic_write_json  # type: ignore
    from logging_utils import setup_logging  # type: ignore
    from redis_cache import RedisCache  # type: ignore
    from utils import convert_to_traditional, normalize_map_key  # type: ignore

INDEX_STAMP_KEY = "map_sidecar:index_stamp"
EXG_LAST_INGEST_KEY = "map_sidecar:exg_last_ingest"


@dataclass(frozen=True)
class IngestSettings:
    bind_host: str
    bind_port: int
    ingest_token: str
    allowlist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]
    max_bytes: int
    request_timeout_seconds: int


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def _load_ingest_settings() -> IngestSettings:
    allowlist_raw = _get_env("INGEST_ALLOWLIST", "") or ""
    allowlist: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in allowlist_raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        allowlist.append(ipaddress.ip_network(entry, strict=False))

    return IngestSettings(
        bind_host=_get_env("INGEST_BIND_HOST", "0.0.0.0"),
        bind_port=int(_get_env("INGEST_BIND_PORT", "8082")),
        ingest_token=_get_env("INGEST_TOKEN", ""),
        allowlist=tuple(allowlist),
        max_bytes=int(_get_env("INGEST_MAX_BYTES", "1048576")),
        request_timeout_seconds=int(_get_env("INGEST_REQUEST_TIMEOUT_SECONDS", "10")),
    )


def export_map_index(settings, logger: logging.Logger, db: MySQLClient) -> int:
    records = db.fetch_map_index()
    payload = {
        "generated_at_epoch": int(time.time()),
        "maps": {},
    }
    for record in records:
        payload["maps"][record.map_key] = {
            "name_zh_cn": record.name_zh_cn or "",
            "name_zh_tw": record.name_zh_tw or "",
            "exg": {
                "achievement": record.achievement,
                "cooldown_end_epoch": record.cooldown_end_epoch,
                "workshop_id": record.workshop_id,
                "workshop_url": record.workshop_url,
            },
        }
    target_path = os.path.join(settings.project_root, "map_index.json")
    atomic_write_json(target_path, payload)
    logger.info("map_index.json exported (%s maps)", len(records))
    return len(records)


def _validate_records(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("Payload records must be a non-empty list")

    cleaned: list[dict] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Record {idx} must be an object")
        raw_map = record.get("map")
        if not isinstance(raw_map, str):
            raise ValueError(f"Record {idx} map must be a string")
        map_key = normalize_map_key(raw_map)
        if not map_key or map_key != raw_map.strip().lower():
            raise ValueError(f"Record {idx} map is invalid")

        name_zh_cn = record.get("name_zh_cn")
        if name_zh_cn is not None and not isinstance(name_zh_cn, str):
            raise ValueError(f"Record {idx} name_zh_cn must be a string or null")

        duration_raw = record.get("duration_raw")
        if duration_raw is not None and not isinstance(duration_raw, str):
            raise ValueError(f"Record {idx} duration_raw must be a string or null")

        cooldown_end_epoch = record.get("cooldown_end_epoch")
        if cooldown_end_epoch is not None:
            if isinstance(cooldown_end_epoch, bool):
                raise ValueError(f"Record {idx} cooldown_end_epoch must be an integer or null")
            if isinstance(cooldown_end_epoch, str):
                if not cooldown_end_epoch.isdigit():
                    raise ValueError(f"Record {idx} cooldown_end_epoch must be an integer or null")
                cooldown_end_epoch = int(cooldown_end_epoch)
            elif not isinstance(cooldown_end_epoch, int):
                raise ValueError(f"Record {idx} cooldown_end_epoch must be an integer or null")

        workshop_id = record.get("workshop_id")
        if workshop_id is not None:
            if isinstance(workshop_id, bool):
                raise ValueError(f"Record {idx} workshop_id must be an integer or null")
            if isinstance(workshop_id, str):
                if not workshop_id.isdigit():
                    raise ValueError(f"Record {idx} workshop_id must be an integer or null")
                workshop_id = int(workshop_id)
            elif not isinstance(workshop_id, int):
                raise ValueError(f"Record {idx} workshop_id must be an integer or null")

        workshop_url = record.get("workshop_url")
        if workshop_url is not None and not isinstance(workshop_url, str):
            raise ValueError(f"Record {idx} workshop_url must be a string or null")

        achievement = record.get("achievement")
        if achievement is not None and not isinstance(achievement, str):
            raise ValueError(f"Record {idx} achievement must be a string or null")

        name_zh_tw = record.get("name_zh_tw")
        if name_zh_tw is not None and not isinstance(name_zh_tw, str):
            raise ValueError(f"Record {idx} name_zh_tw must be a string or null")
        if not name_zh_tw and name_zh_cn:
            name_zh_tw = convert_to_traditional(name_zh_cn)

        cleaned.append(
            {
                "map": map_key,
                "name_zh_cn": name_zh_cn.strip() if isinstance(name_zh_cn, str) else None,
                "name_zh_tw": name_zh_tw.strip() if isinstance(name_zh_tw, str) else None,
                "duration_raw": duration_raw.strip() if isinstance(duration_raw, str) else None,
                "cooldown_end_epoch": cooldown_end_epoch,
                "workshop_id": workshop_id,
                "workshop_url": workshop_url.strip() if isinstance(workshop_url, str) else None,
                "achievement": achievement.strip() if isinstance(achievement, str) else None,
            }
        )

    return cleaned


def _process_records(
    records: Iterable[dict],
    settings,
    logger: logging.Logger,
    db: MySQLClient,
    cache: RedisCache,
) -> bool:
    map_keys = {record["map"] for record in records}
    now_epoch = int(time.time())
    db.ensure_maps_placeholder(map_keys, now_epoch)

    changed = False
    exg_changed = db.upsert_map_exg(records)
    if exg_changed:
        changed = True

    for record in records:
        name_cn = record.get("name_zh_cn")
        name_tw = record.get("name_zh_tw")
        updated = db.update_map_names_from_exg(record["map"], name_cn, name_tw)
        if updated:
            changed = True

    if changed:
        export_map_index(settings, logger, db)
        stamp = db.get_change_stamp()
        if stamp is not None:
            cache.set(INDEX_STAMP_KEY, str(stamp))
    else:
        logger.info("EXG ingest completed with no changes")
    return changed


def _client_allowed(
    allowlist: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...],
    client_ip: str,
) -> bool:
    if not allowlist:
        return True
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    return any(addr in net for net in allowlist)


def _extract_token(handler: BaseHTTPRequestHandler) -> str:
    auth_header = handler.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return handler.headers.get("X-Ingest-Token", "").strip()


def _read_body(handler: BaseHTTPRequestHandler, max_bytes: int) -> bytes:
    length_header = handler.headers.get("Content-Length")
    if not length_header:
        raise ValueError("Content-Length is required")
    try:
        length = int(length_header)
    except ValueError as exc:
        raise ValueError("Invalid Content-Length") from exc
    if length <= 0:
        raise ValueError("Content-Length must be positive")
    if length > max_bytes:
        raise ValueError("Payload too large")
    return handler.rfile.read(length)


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class IngestHandler(BaseHTTPRequestHandler):
    server_version = "cs2ze-exg-ingest/1.0"

    def setup(self) -> None:
        super().setup()
        timeout = self.server.request_timeout_seconds
        if timeout:
            self.connection.settimeout(timeout)

    def log_message(self, fmt: str, *args) -> None:
        self.server.logger.info("%s - %s", self.address_string(), fmt % args)

    def do_POST(self) -> None:
        if self.path != "/sidecar/exg/ingest":
            _json_response(self, 404, {"error": "not_found"})
            return

        client_ip = self.client_address[0]
        if not _client_allowed(self.server.allowlist, client_ip):
            _json_response(self, 403, {"error": "forbidden"})
            return

        token = _extract_token(self)
        if not token or token != self.server.ingest_token:
            _json_response(self, 401, {"error": "unauthorized"})
            return

        try:
            body = _read_body(self, self.server.max_bytes)
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            _json_response(self, 400, {"error": str(exc)})
            return

        try:
            records = _validate_records(payload)
        except ValueError as exc:
            _json_response(self, 400, {"error": str(exc)})
            return

        try:
            changed = _process_records(
                records,
                self.server.app_settings,
                self.server.logger,
                self.server.db,
                self.server.cache,
            )
            self.server.cache.set(EXG_LAST_INGEST_KEY, str(int(time.time())))
        except Exception as exc:
            self.server.logger.error("Ingest processing failed: %s", exc)
            _json_response(self, 500, {"error": "ingest_failed"})
            return

        _json_response(
            self,
            200,
            {
                "status": "ok",
                "changed": changed,
                "records": len(records),
            },
        )


class IngestHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, ingest_settings, app_settings, logger, db, cache):
        super().__init__(server_address, handler_class)
        self.ingest_token = ingest_settings.ingest_token
        self.allowlist = ingest_settings.allowlist
        self.max_bytes = ingest_settings.max_bytes
        self.request_timeout_seconds = ingest_settings.request_timeout_seconds
        self.app_settings = app_settings
        self.logger = logger
        self.db = db
        self.cache = cache
        self.daemon_threads = True
        self.request_queue_size = 8


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CS2ZE EXG ingest sidecar")
    parser.add_argument("--once", action="store_true", help="Handle a single request then exit")
    return parser


def main() -> int:
    ingest_settings = _load_ingest_settings()
    if not ingest_settings.ingest_token:
        print("INGEST_TOKEN is required", file=sys.stderr)
        return 1

    app_settings = load_settings()
    logger = setup_logging(app_settings.log_dir)
    logger.setLevel(logging.INFO)

    if not app_settings.mysql_host:
        logger.error("MYSQL_HOST is required")
        return 1

    db = MySQLClient(app_settings)
    cache = RedisCache(app_settings)

    parser = build_parser()
    args = parser.parse_args()

    server = IngestHTTPServer(
        (ingest_settings.bind_host, ingest_settings.bind_port),
        IngestHandler,
        ingest_settings,
        app_settings,
        logger,
        db,
        cache,
    )

    logger.info(
        "EXG ingest server listening on %s:%s",
        ingest_settings.bind_host,
        ingest_settings.bind_port,
    )

    try:
        if args.once:
            server.handle_request()
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        logger.info("EXG ingest server shutting down")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
