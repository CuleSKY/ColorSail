from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import re
import signal
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable, Optional

from tools.map_sidecar.config import (
    EXG_LAST_INGEST_KEY,
    IngestSettings,
    load_ingest_settings,
    load_settings,
    validate_ingest_settings,
    validate_settings,
)
from tools.map_sidecar.db import MySQLClient
from tools.map_sidecar.exporter import atomic_write_json
from tools.map_sidecar.logging_utils import setup_logging
from tools.map_sidecar.redis_cache import RedisCache
from tools.map_sidecar.utils import convert_to_traditional, normalize_map_key, parse_beijing_time

MAP_RE = re.compile(r"^[a-z0-9]+_[a-z0-9][a-z0-9_\-]*$", re.I)


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _validate_records(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Payload source must be a non-empty string")
    fetched_at_epoch = payload.get("fetched_at_epoch")
    if not isinstance(fetched_at_epoch, int):
        raise ValueError("Payload fetched_at_epoch must be an integer")
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
        map_key = raw_map.strip().lower()
        if not MAP_RE.match(map_key):
            raise ValueError(f"Record {idx} map is invalid")
        normalized_key = normalize_map_key(map_key)
        if not normalized_key or normalized_key != map_key:
            raise ValueError(f"Record {idx} map is invalid")

        name_zh = record.get("name_zh")
        if not isinstance(name_zh, str):
            raise ValueError(f"Record {idx} name_zh must be a string")

        difficulty = record.get("difficulty")
        if not isinstance(difficulty, str):
            raise ValueError(f"Record {idx} difficulty must be a string")

        tags = record.get("tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError(f"Record {idx} tags must be a list of strings")

        cooldown = record.get("cooldown")
        if not isinstance(cooldown, dict):
            raise ValueError(f"Record {idx} cooldown must be an object")
        duration_raw = cooldown.get("duration_raw")
        if not isinstance(duration_raw, str):
            raise ValueError(f"Record {idx} cooldown.duration_raw must be a string")
        deadline = cooldown.get("deadline")
        if deadline is not None and not isinstance(deadline, str):
            raise ValueError(f"Record {idx} cooldown.deadline must be a string or null")

        workshop = record.get("workshop")
        if not isinstance(workshop, dict):
            raise ValueError(f"Record {idx} workshop must be an object")
        workshop_id_raw = workshop.get("id")
        if workshop_id_raw is None or (isinstance(workshop_id_raw, str) and not workshop_id_raw.strip()):
            workshop_id_raw = "0"
        if not isinstance(workshop_id_raw, str):
            raise ValueError(f"Record {idx} workshop.id must be a string")
        if not workshop_id_raw.isdigit():
            raise ValueError(f"Record {idx} workshop.id must be numeric")
        workshop_url = workshop.get("url")
        if not isinstance(workshop_url, str):
            raise ValueError(f"Record {idx} workshop.url must be a string")

        achievement = record.get("achievement")
        if not isinstance(achievement, str):
            raise ValueError(f"Record {idx} achievement must be a string")

        name_zh_cn = _empty_to_none(name_zh)
        try:
            name_zh_tw = convert_to_traditional(name_zh_cn) if name_zh_cn else None
        except RuntimeError as exc:
            raise ValueError(f"Record {idx} zh_tw conversion failed: {exc}") from exc
        duration_raw = _empty_to_none(duration_raw)
        deadline = _empty_to_none(deadline)
        cooldown_end_epoch = parse_beijing_time(deadline) if deadline else None
        if deadline and cooldown_end_epoch is None:
            raise ValueError(f"Record {idx} cooldown.deadline parse failed: {deadline}")
        achievement = _empty_to_none(achievement)
        workshop_id = None if workshop_id_raw == "0" else int(workshop_id_raw)
        workshop_url = _empty_to_none(workshop_url)

        cleaned.append(
            {
                "map": normalized_key,
                "name_zh_cn": name_zh_cn,
                "name_zh_tw": name_zh_tw,
                "duration_raw": duration_raw,
                "cooldown_end_epoch": cooldown_end_epoch,
                "workshop_id": workshop_id,
                "workshop_url": workshop_url,
                "achievement": achievement,
            }
        )

    return cleaned


def _write_normalized_maplist(settings, logger: logging.Logger, records: Iterable[dict]) -> None:
    output_path = os.path.join(settings.project_root, settings.static_dir_name, "data", "maplist_normalized.json")
    payload = list(records)
    try:
        atomic_write_json(output_path, payload)
        logger.info("maplist_normalized.json updated (%s records)", len(payload))
    except OSError as exc:
        logger.warning("Failed to write maplist_normalized.json: %s", exc)


def _process_records(
    records: Iterable[dict],
    settings,
    logger: logging.Logger,
    db: MySQLClient,
    cache: RedisCache,
    raw_records: Iterable[dict],
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
        logger.info("EXG ingest updated DB; exporter will refresh on next timer tick")
    else:
        logger.info("EXG ingest completed with no changes")
    _write_normalized_maplist(settings, logger, raw_records)
    return changed


def _safe_cache_set(cache: RedisCache, logger: logging.Logger, key: str, value: str) -> None:
    try:
        cache.set(key, value)
    except Exception as exc:
        logger.warning("Redis write failed for %s: %s", key, exc)


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
                payload.get("records", []),
            )
            _safe_cache_set(
                self.server.cache,
                self.server.logger,
                EXG_LAST_INGEST_KEY,
                str(int(time.time())),
            )
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


def run_server(
    ingest_settings: IngestSettings,
    app_settings,
    logger: logging.Logger,
    db: MySQLClient,
    cache: RedisCache,
    once: bool = False,
) -> int:
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

    def handle_sigterm(signum, frame):  # noqa: ARG001
        logger.info("EXG ingest server received SIGTERM")
        server.shutdown()

    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        if once:
            server.handle_request()
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        logger.info("EXG ingest server shutting down")
    finally:
        server.server_close()
    return 0


def main() -> int:
    ingest_settings = load_ingest_settings()
    app_settings = load_settings()
    logger = setup_logging(app_settings.log_dir)
    logger.setLevel(logging.INFO)

    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_ingest_settings(ingest_settings)
        validate_settings(app_settings, require_mysql=True)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    db = MySQLClient(app_settings)
    cache = RedisCache(app_settings)
    return run_server(
        ingest_settings,
        app_settings,
        logger,
        db,
        cache,
        once=args.once,
    )


if __name__ == "__main__":
    sys.exit(main())
