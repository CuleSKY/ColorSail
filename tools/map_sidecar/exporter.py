from __future__ import annotations

import json
import os
import tempfile
import time
from typing import TYPE_CHECKING, Any

from tools.map_sidecar.utils import ensure_dir

if TYPE_CHECKING:
    from tools.map_sidecar.config import Settings
    from tools.map_sidecar.db import MySQLClient
    import logging


def atomic_write_json(path: str, payload: Any) -> None:
    dir_name = os.path.dirname(path) or "."
    ensure_dir(dir_name)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp.", suffix=".json", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def export_time_json(settings: "Settings", logger: "logging.Logger") -> None:
    payload = {"server_now_epoch": int(time.time())}
    target_path = os.path.join(settings.project_root, "time.json")
    atomic_write_json(target_path, payload)
    logger.info("time.json exported")


def export_map_index(settings: "Settings", logger: "logging.Logger", db: "MySQLClient") -> int:
    records = db.fetch_map_index()
    payload: dict[str, dict[str, object]] = {}
    for record in sorted(records, key=lambda item: item.map_key):
        map_cn = record.name_zh_cn or record.map_key
        payload[record.map_key] = {
            "map_cn": map_cn,
            "deadline": record.cooldown_end_epoch,
            "achievement": record.achievement or "",
        }
    target_path = os.path.join(settings.project_root, "map_index.json")
    atomic_write_json(target_path, payload)
    export_time_json(settings, logger)
    logger.info("map_index.json exported (%s maps)", len(records))
    return len(records)
