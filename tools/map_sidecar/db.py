from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, List, Optional

import hashlib

import pymysql

from tools.map_sidecar.config import Settings


@dataclass
class MapRecord:
    map_key: str
    name_zh_cn: Optional[str]
    name_zh_tw: Optional[str]
    achievement: Optional[str]
    cooldown_end_epoch: Optional[int]
    workshop_id: Optional[int]
    workshop_url: Optional[str]


class MySQLClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @contextmanager
    def connect(self):
        conn = pymysql.connect(
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            database=self.settings.mysql_db,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        try:
            yield conn
        finally:
            conn.close()

    def ensure_maps_placeholder(self, map_keys: Iterable[str], now_epoch: int) -> int:
        rows = [(map_key, now_epoch) for map_key in map_keys]
        if not rows:
            return 0
        sql = (
            "INSERT INTO maps (map_key, name_zh_cn, name_zh_tw, name_locked, last_seen_epoch) "
            "VALUES (%s, NULL, NULL, 0, %s) "
            "ON DUPLICATE KEY UPDATE last_seen_epoch = VALUES(last_seen_epoch)"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
                return cur.rowcount

    def update_map_names_from_exg(
        self,
        map_key: str,
        name_zh_cn: Optional[str],
        name_zh_tw: Optional[str],
    ) -> int:
        if not name_zh_cn:
            return 0
        sql = (
            "UPDATE maps "
            "SET name_zh_cn = IF(name_locked = 0 AND %s IS NOT NULL AND %s != '', %s, name_zh_cn), "
            "    name_zh_tw = IF(name_locked = 0 AND (name_zh_tw IS NULL OR name_zh_tw = '') "
            "        AND %s IS NOT NULL AND %s != '', %s, name_zh_tw) "
            "WHERE map_key = %s"
        )
        params = (
            name_zh_cn,
            name_zh_cn,
            name_zh_cn,
            name_zh_tw,
            name_zh_tw,
            name_zh_tw,
            map_key,
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.rowcount

    def upsert_map_exg(self, records: Iterable[dict]) -> int:
        rows = [
            (
                rec["map"],
                rec.get("cooldown_end_epoch"),
                rec.get("workshop_id"),
                rec.get("workshop_url"),
                rec.get("achievement"),
                rec.get("duration_raw"),
            )
            for rec in records
        ]
        if not rows:
            return 0
        sql = (
            "INSERT INTO map_exg (map_key, cooldown_end_epoch, workshop_id, workshop_url, achievement, duration_raw) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "cooldown_end_epoch = VALUES(cooldown_end_epoch), "
            "workshop_id = VALUES(workshop_id), "
            "workshop_url = VALUES(workshop_url), "
            "achievement = VALUES(achievement), "
            "duration_raw = VALUES(duration_raw)"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, rows)
                return cur.rowcount

    def fetch_map_translations(self, map_keys: Iterable[str]) -> dict:
        keys = list(map_keys)
        if not keys:
            return {}
        placeholders = ",".join(["%s"] * len(keys))
        sql = (
            f"SELECT map_key, name_zh_cn, name_zh_tw FROM maps WHERE map_key IN ({placeholders})"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, keys)
                rows = cur.fetchall()
        result = {}
        for row in rows:
            result[row["map_key"]] = {
                "zh_cn": row.get("name_zh_cn") or "",
                "zh_tw": row.get("name_zh_tw") or "",
            }
        return result

    def fetch_map_index(self) -> List[MapRecord]:
        sql = (
            "SELECT m.map_key, m.name_zh_cn, m.name_zh_tw, "
            "e.achievement, e.cooldown_end_epoch, e.workshop_id, e.workshop_url "
            "FROM maps m "
            "LEFT JOIN map_exg e ON m.map_key = e.map_key"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        records: List[MapRecord] = []
        for row in rows:
            records.append(
                MapRecord(
                    map_key=row["map_key"],
                    name_zh_cn=row.get("name_zh_cn"),
                    name_zh_tw=row.get("name_zh_tw"),
                    achievement=row.get("achievement"),
                    cooldown_end_epoch=row.get("cooldown_end_epoch"),
                    workshop_id=row.get("workshop_id"),
                    workshop_url=row.get("workshop_url"),
                )
            )
        return records

    def get_change_stamp(self) -> Optional[int]:
        sql = (
            "SELECT GREATEST("
            "COALESCE((SELECT UNIX_TIMESTAMP(MAX(updated_at)) FROM maps), 0),"
            "COALESCE((SELECT UNIX_TIMESTAMP(MAX(updated_at)) FROM map_exg), 0)"
            ") AS stamp"
        )
        try:
            with self.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    row = cur.fetchone()
                    if row and row.get("stamp") is not None:
                        return int(row["stamp"])
        except Exception:
            pass

        records = self.fetch_map_index()
        if not records:
            return 0
        hasher = hashlib.sha256()
        for record in sorted(records, key=lambda item: item.map_key):
            payload = (
                f"{record.map_key}\x1f"
                f"{record.name_zh_cn or ''}\x1f"
                f"{record.name_zh_tw or ''}\x1f"
                f"{record.achievement or ''}\x1f"
                f"{record.cooldown_end_epoch or ''}\x1f"
                f"{record.workshop_id or ''}\x1f"
                f"{record.workshop_url or ''}\x1f"
            )
            hasher.update(payload.encode("utf-8"))
        return int(hasher.hexdigest(), 16)

    def get_maps_for_images(self) -> List[dict]:
        sql = (
            "SELECT m.map_key, e.workshop_id, e.workshop_url "
            "FROM maps m "
            "JOIN map_exg e ON m.map_key = e.map_key "
            "WHERE e.workshop_id IS NOT NULL OR e.workshop_url IS NOT NULL"
        )
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall()
