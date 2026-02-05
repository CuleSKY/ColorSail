from __future__ import annotations

import argparse
import logging
import sys
import time

from tools.map_sidecar.cn_fetcher import run_fetch
from tools.map_sidecar.config import (
    EXG_LAST_INGEST_KEY,
    INDEX_STAMP_KEY,
    load_cn_fetcher_settings,
    load_ingest_settings,
    load_settings,
    validate_ingest_settings,
    validate_settings,
)
from tools.map_sidecar.db import MySQLClient
from tools.map_sidecar.exporter import export_map_index
from tools.map_sidecar.ingest_server import run_server
from tools.map_sidecar.logging_utils import setup_logging
from tools.map_sidecar.redis_cache import RedisCache
from tools.map_sidecar.servers_poller import poll_servers
from tools.map_sidecar.workshop_images import fetch_missing_images


def run_poll_servers(settings, logger, db, cache) -> None:
    poll_servers(settings, logger, db, cache)


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


def run_exg_health(settings, logger, cache) -> int:
    if not cache.client:
        logger.error("Redis settings are required for EXG health checks")
        return 1
    last_ingest = cache.get(EXG_LAST_INGEST_KEY)
    if not last_ingest:
        logger.error("EXG ingest timestamp not found in cache")
        return 1
    try:
        last_epoch = int(last_ingest)
    except ValueError:
        logger.error("EXG ingest timestamp is invalid: %s", last_ingest)
        return 1
    age = int(time.time()) - last_epoch
    max_age = settings.exg_health_max_age_seconds
    if age > max_age:
        logger.error("EXG ingest is stale (%s seconds ago)", age)
        return 1
    logger.info("EXG ingest is healthy (%s seconds ago)", age)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CS2ZE map sidecar")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-daemon", help="Run ingest server continuously")
    sub.add_parser("poll-servers", help="Poll /servers.json and export translations")
    sub.add_parser("refresh-index", help="Refresh map_index.json if DB changed")
    sub.add_parser("fetch-images", help="Fetch missing workshop images")
    sub.add_parser("exg-health", help="Check last EXG ingest timestamp")

    ingest_parser = sub.add_parser("ingest-server", help="Run the EXG ingest HTTP server")
    ingest_parser.add_argument("--once", action="store_true", help="Handle a single request then exit")

    cn_parser = sub.add_parser("cn-fetch", help="Fetch EXG maplist from CN and POST to overseas")
    cn_parser.add_argument("--dry-run", action="store_true", help="Fetch + parse only; do not POST")
    cn_parser.add_argument("--dump-payload", action="store_true", help="Print full payload JSON")
    cn_parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium with a visible window (debugging only)",
    )
    cn_parser.add_argument(
        "--use-requests",
        action="store_true",
        help="Use requests instead of Chromium rendering (debugging only)",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "cn-fetch":
        settings = load_cn_fetcher_settings()
        logger = setup_logging(settings.log_dir)
        logger.setLevel(logging.INFO)
        try:
            return run_fetch(
                settings,
                logger,
                args.dry_run,
                args.dump_payload,
                headless=not args.headed,
                use_requests=args.use_requests,
            )
        except Exception as exc:  # pragma: no cover - safety net
            logger.error("CN fetch failed: %s", exc)
            return 1

    settings = load_settings()
    logger = setup_logging(settings.log_dir)
    logger.setLevel(logging.INFO)

    if args.command in {"ingest-server", "run-daemon"}:
        ingest_settings = load_ingest_settings()
        try:
            validate_ingest_settings(ingest_settings)
            validate_settings(settings, require_mysql=True)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1
        db = MySQLClient(settings)
        cache = RedisCache(settings)
        return run_server(
            ingest_settings,
            settings,
            logger,
            db,
            cache,
            once=getattr(args, "once", False),
        )

    if args.command == "exg-health":
        try:
            validate_settings(settings, require_mysql=False)
        except ValueError as exc:
            logger.error("%s", exc)
            return 1
        cache = RedisCache(settings)
        return run_exg_health(settings, logger, cache)

    try:
        validate_settings(settings, require_mysql=True)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    db = MySQLClient(settings)
    cache = RedisCache(settings)

    if args.command == "poll-servers":
        run_poll_servers(settings, logger, db, cache)
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
