from __future__ import annotations

import hashlib
import logging
from typing import Iterable, List

import requests

from tools.map_sidecar.config import Settings
from tools.map_sidecar.db import MySQLClient
from tools.map_sidecar.exporter import atomic_write_json
from tools.map_sidecar.redis_cache import RedisCache
from tools.map_sidecar.utils import normalize_map_key

SERVERS_ETAG_KEY = "map_sidecar:servers_etag"
SERVERS_MAP_KEYS_KEY = "map_sidecar:servers_map_keys"
USER_AGENT = "cs2ze-map-sidecar/1.0"
TRANS_CACHE_PREFIX = "map_sidecar:translations:"


def _extract_map_keys(payload: object, logger: logging.Logger) -> List[str]:
    map_keys = set()
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = []
        for value in payload.values():
            if isinstance(value, list):
                entries.extend(value)
    else:
        return []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_map = entry.get("map") or entry.get("map_name") or entry.get("mapName")
        map_key = normalize_map_key(raw_map)
        if map_key:
            map_keys.add(map_key)
        elif raw_map:
            logger.warning("Skipping invalid map key from /servers.json: %s", raw_map)
    return sorted(map_keys)


def poll_servers(
    settings: Settings,
    logger: logging.Logger,
    db: MySQLClient,
    cache: RedisCache,
) -> None:
    headers = {}
    cached_etag = cache.get(SERVERS_ETAG_KEY)
    if cached_etag:
        headers["If-None-Match"] = cached_etag

    headers["User-Agent"] = USER_AGENT
    response = requests.get(settings.main_servers_json_url, headers=headers, timeout=15)
    map_keys: Iterable[str] | None = None

    if response.status_code == 304:
        cached_keys = cache.get_json(SERVERS_MAP_KEYS_KEY)
        if cached_keys:
            map_keys = cached_keys
            logger.info("/servers.json 304 Not Modified; using cached map keys")
        else:
            logger.warning("/servers.json 304 but no cached map keys available")
            return
    elif response.ok:
        try:
            payload = response.json()
        except ValueError:
            logger.warning("/servers.json returned invalid JSON")
            return
        map_keys = _extract_map_keys(payload, logger)
        etag = response.headers.get("ETag") or response.headers.get("etag")
        if etag:
            cache.set(SERVERS_ETAG_KEY, etag)
        cache.set_json(SERVERS_MAP_KEYS_KEY, map_keys, ex=3600)
    else:
        logger.warning("/servers.json fetch failed: %s", response.status_code)
        return

    if not map_keys:
        logger.info("No active maps found in /servers.json")
        return

    logger.info("Active map keys: %s", len(map_keys))

    import time

    now_epoch = int(time.time())
    db.ensure_maps_placeholder(map_keys, now_epoch)

    cache_key = TRANS_CACHE_PREFIX + hashlib.sha256(",".join(map_keys).encode("utf-8")).hexdigest()
    translations = cache.get_json(cache_key)
    if translations is None:
        translations = db.fetch_map_translations(map_keys)
        cache.set_json(cache_key, translations, ex=300)
    translations_path = f"{settings.project_root}/map_translations.json"
    atomic_write_json(translations_path, translations)
    logger.info("map_translations.json exported (%s entries)", len(translations))
