from __future__ import annotations

import argparse
import logging
import os
import sys
import time

from .config import load_settings
from .db import MySQLClient
from .exporter import atomic_write_json
from .exg_maplist import MaplistParseError, fetch_and_parse
from .logging_utils import setup_logging
from .redis_cache import RedisCache
from .servers_poller import poll_servers
from .workshop_images import fetch_missing_images

INDEX_STAMP_KEY = "map_sidecar:index_stamp"


def export_map_index(settings, logger, db: MySQLClient) -> int:
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


def run_poll_servers(settings, logger, db, cache) -> None:
    poll_servers(settings, logger, db, cache)


def run_ingest_exg(settings, logger, db, cache) -> None:
    try:
        records = fetch_and_parse(settings, logger)
    except MaplistParseError as exc:
        logger.error("EXG maplist parse failed: %s", exc)
        return

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
        logger.info("EXG maplist ingestion completed with no changes")


def run_refresh_index(settings, logger, db, cache) -> None:
    stamp = db.get_change_stamp()
    cached_stamp = cache.get(INDEX_STAMP_KEY)
    if stamp is None:
        logger.warning("Unable to determine DB change stamp")
        return
    if cached_stamp and str(stamp) == cached_stamp:
        logger.info("map_index.json up-to-date (stamp %s)", stamp)
        return
    export_map_index(settings, logger, db)
    cache.set(INDEX_STAMP_KEY, str(stamp))


def run_fetch_images(settings, logger, db) -> None:
    fetch_missing_images(settings, logger, db)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CS2ZE map sidecar")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("poll-servers", help="Poll /servers.json and export translations")
    sub.add_parser("ingest-exg", help="Fetch EXG maplist and update DB/export index")
    sub.add_parser("refresh-index", help="Refresh map_index.json if DB changed")
    sub.add_parser("fetch-images", help="Fetch missing workshop images")

    return parser


def main() -> int:
    settings = load_settings()
    logger = setup_logging(settings.log_dir)
    logger.setLevel(logging.INFO)

    parser = build_parser()
    args = parser.parse_args()

    if not settings.mysql_host:
        logger.error("MYSQL_HOST is required")
        return 1

    db = MySQLClient(settings)
    cache = RedisCache(settings)

    if args.command == "poll-servers":
        run_poll_servers(settings, logger, db, cache)
    elif args.command == "ingest-exg":
        run_ingest_exg(settings, logger, db, cache)
    elif args.command == "refresh-index":
        run_refresh_index(settings, logger, db, cache)
    elif args.command == "fetch-images":
        run_fetch_images(settings, logger, db)
    else:
        logger.error("Unknown command: %s", args.command)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
