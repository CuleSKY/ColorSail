from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from typing import Any, Iterable, List, Optional

import pymysql
import redis
import requests
from bs4 import BeautifulSoup

if importlib.util.find_spec("zoneinfo") is not None:
    from zoneinfo import ZoneInfo
else:
    from backports.zoneinfo import ZoneInfo  # type: ignore


@dataclass(frozen=True)
class Settings:
    mysql_host: str
    mysql_port: int
    mysql_db: str
    mysql_user: str
    mysql_password: str
    redis_url: str | None
    redis_host: str | None
    redis_port: int | None
    redis_password: str | None
    main_servers_json_url: str
    project_root: str
    static_dir_name: str
    log_dir: str
    debug: bool


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def load_settings() -> Settings:
    mysql_port = int(_get_env("MYSQL_PORT", "3306"))
    redis_port = _get_env("REDIS_PORT")
    redis_port_int = int(redis_port) if redis_port else None
    project_root = _get_env(
        "PROJECT_ROOT",
        "/opt/1panel/www/sites/www.cs2ze.org/NERV_CS2ZE",
    )
    static_dir_name = _get_env("STATIC_DIR_NAME", "static")
    log_dir = _get_env("MAP_SIDECAR_LOG_DIR", os.path.join(project_root, "logs"))

    return Settings(
        mysql_host=_get_env("MYSQL_HOST", ""),
        mysql_port=mysql_port,
        mysql_db=_get_env("MYSQL_DB", ""),
        mysql_user=_get_env("MYSQL_USER", ""),
        mysql_password=_get_env("MYSQL_PASSWORD", ""),
        redis_url=_get_env("REDIS_URL"),
        redis_host=_get_env("REDIS_HOST"),
        redis_port=redis_port_int,
        redis_password=_get_env("REDIS_PASSWORD"),
        main_servers_json_url=_get_env(
            "MAIN_SERVERS_JSON_URL",
            "https://www.cs2ze.org/servers.json",
        ),
        project_root=project_root,
        static_dir_name=static_dir_name,
        log_dir=log_dir,
        debug=str(_get_env("DEBUG", "false")).lower() in {"1", "true", "yes"},
    )


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


class RedisCache:
    def __init__(self, settings: Settings) -> None:
        if settings.redis_url:
            self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        elif settings.redis_host and settings.redis_port:
            self.client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                decode_responses=True,
            )
        else:
            self.client = None

    def get(self, key: str) -> Optional[str]:
        if not self.client:
            return None
        return self.client.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        if not self.client:
            return
        self.client.set(key, value, ex=ex)

    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        self.set(key, payload, ex=ex)


def setup_logging(log_dir: str, log_level: str = "INFO") -> logging.Logger:
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger("map_sidecar")
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "map_sidecar.log"),
        when="D",
        interval=1,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


BEIJING_TZ = ZoneInfo("Asia/Shanghai")
MAP_KEY_RE = re.compile(r"^[a-z0-9_]+$")


def normalize_map_key(raw: str | None) -> Optional[str]:
    if not raw:
        return None
    map_clean = str(raw).strip().lower()
    map_clean = map_clean.replace("\\", "/").split("?", 1)[0]
    if map_clean.endswith(".bsp"):
        map_clean = map_clean[:-4]
    if map_clean.startswith("workshop/"):
        parts = map_clean.split("/")
        map_clean = parts[-1] if parts else map_clean
    else:
        map_clean = map_clean.split("/")[-1]
    map_clean = map_clean.strip()
    if not map_clean or not MAP_KEY_RE.match(map_clean):
        return None
    return map_clean


def convert_to_traditional(text: str) -> str:
    if not text:
        return ""
    fallback_map = str.maketrans({
        "汉": "漢",
        "龙": "龍",
        "门": "門",
        "风": "風",
        "画": "畫",
        "楼": "樓",
        "体": "體",
        "云": "雲",
        "战": "戰",
        "峡": "峽",
        "岛": "島",
        "台": "臺",
    })
    return str(text).translate(fallback_map)


def parse_beijing_time(value: str) -> Optional[int]:
    if not value:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned in {"无", "無", "-", "N/A"}:
        return None
    patterns = [
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]
    for pattern in patterns:
        try:
            dt = datetime.strptime(cleaned, pattern)
            dt = dt.replace(tzinfo=BEIJING_TZ)
            return int(dt.timestamp())
        except ValueError:
            continue
    match = re.search(
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?",
        cleaned,
    )
    if match:
        year, month, day, hour, minute, second = match.groups()
        dt = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second or 0),
            tzinfo=BEIJING_TZ,
        )
        return int(dt.timestamp())
    return None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


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

    now_epoch = int(time.time())
    db.ensure_maps_placeholder(map_keys, now_epoch)

    cache_key = TRANS_CACHE_PREFIX + hashlib.sha256(",".join(map_keys).encode("utf-8")
    ).hexdigest()
    translations = cache.get_json(cache_key)
    if translations is None:
        translations = db.fetch_map_translations(map_keys)
        cache.set_json(cache_key, translations, ex=300)
    translations_path = f"{settings.project_root}/map_translations.json"
    atomic_write_json(translations_path, translations)
    logger.info("map_translations.json exported (%s entries)", len(translations))


EXG_URL = "https://list.darkrp.cn:9000/serverlist/cs2maplist"
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug", "exg_html")


class MaplistParseError(RuntimeError):
    pass


def _cleanup_debug_html(logger: logging.Logger) -> None:
    ensure_dir(DEBUG_DIR)
    cutoff = datetime.now(tz=BEIJING_TZ) - timedelta(hours=72)
    for name in os.listdir(DEBUG_DIR):
        if not name.startswith("exg_maplist_"):
            continue
        path = os.path.join(DEBUG_DIR, name)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path), tz=BEIJING_TZ)
            if mtime < cutoff:
                os.remove(path)
                logger.info("Removed old debug HTML: %s", name)
        except OSError:
            continue


def _save_debug_html(logger: logging.Logger, html: str) -> None:
    ensure_dir(DEBUG_DIR)
    timestamp = datetime.now(tz=BEIJING_TZ).strftime("%Y%m%d_%H%M")
    filename = f"exg_maplist_{timestamp}.html"
    path = os.path.join(DEBUG_DIR, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    logger.warning("Saved EXG maplist HTML for debugging: %s", path)


def _normalize_header(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def _find_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    tables = soup.find_all("table")
    if not tables:
        return None
    return max(tables, key=lambda table: len(table.find_all("tr")))


def _extract_headers(table: BeautifulSoup) -> List[str]:
    header_row = table.find("tr")
    if not header_row:
        return []
    headers = [cell.get_text(strip=True) for cell in header_row.find_all(["th", "td"])]
    return headers


def _map_columns(headers: List[str]) -> dict:
    mapping = {}
    for idx, header in enumerate(headers):
        normalized = _normalize_header(header)
        if not normalized:
            continue
        if any(token in normalized for token in ["地图", "map"]):
            mapping["map"] = idx
        elif any(token in normalized for token in ["名称", "中文", "zh", "cn"]):
            mapping["name"] = idx
        elif any(token in normalized for token in ["冷却", "cd", "结束", "时间", "cooldown"]):
            mapping["cooldown"] = idx
        elif any(token in normalized for token in ["工坊", "workshop", "id"]):
            mapping["workshop"] = idx
        elif any(token in normalized for token in ["成就", "achievement"]):
            mapping["achievement"] = idx
        elif any(token in normalized for token in ["时长", "duration", "时间"]):
            mapping.setdefault("duration", idx)
    return mapping


def _parse_workshop(value: str) -> tuple[Optional[int], Optional[str]]:
    if not value:
        return None, None
    text = value.strip()
    url_match = re.search(
        r"https?://steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)",
        text,
    )
    if url_match:
        workshop_id = int(url_match.group(1))
        return workshop_id, url_match.group(0)
    id_match = re.search(r"(\d{5,})", text)
    if id_match:
        workshop_id = int(id_match.group(1))
        return workshop_id, f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
    return None, None


def parse_maplist(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table(soup)
    if not table:
        raise MaplistParseError("No table found in EXG maplist HTML")
    headers = _extract_headers(table)
    mapping = _map_columns(headers)
    if headers and ("map" not in mapping or "name" not in mapping):
        raise MaplistParseError("Unexpected maplist table structure")
    rows = []
    data_rows = table.find_all("tr")[1:] if headers else table.find_all("tr")
    if not data_rows:
        raise MaplistParseError("No data rows found in EXG maplist HTML")
    if not headers:
        first_cells = data_rows[0].find_all(["td", "th"])
        if len(first_cells) < 2:
            raise MaplistParseError("Unexpected maplist table structure")

    for row in data_rows:
        cells = [cell.get_text(strip=True) for cell in row.find_all(["td", "th"])]
        if not cells:
            continue
        if mapping:
            map_raw = cells[mapping.get("map", 0)] if len(cells) > mapping.get("map", 0) else None
            name_raw = cells[mapping.get("name", 1)] if len(cells) > mapping.get("name", 1) else None
            cooldown_raw = cells[mapping.get("cooldown", 2)] if len(cells) > mapping.get("cooldown", 2) else None
            workshop_raw = cells[mapping.get("workshop", 3)] if len(cells) > mapping.get("workshop", 3) else None
            achievement_raw = cells[mapping.get("achievement", 4)] if len(cells) > mapping.get("achievement", 4) else None
            duration_raw = cells[mapping.get("duration", 5)] if len(cells) > mapping.get("duration", 5) else None
        else:
            map_raw = cells[0] if len(cells) > 0 else None
            name_raw = cells[1] if len(cells) > 1 else None
            cooldown_raw = cells[2] if len(cells) > 2 else None
            workshop_raw = cells[3] if len(cells) > 3 else None
            achievement_raw = cells[4] if len(cells) > 4 else None
            duration_raw = cells[5] if len(cells) > 5 else None

        map_key = normalize_map_key(map_raw)
        if not map_key:
            continue
        cooldown_epoch = parse_beijing_time(cooldown_raw or "")
        workshop_id, workshop_url = _parse_workshop(workshop_raw or "")
        name_zh_cn = name_raw.strip() if name_raw else None
        record = {
            "map": map_key,
            "name_zh_cn": name_zh_cn,
            "name_zh_tw": convert_to_traditional(name_zh_cn) if name_zh_cn else None,
            "cooldown_end_epoch": cooldown_epoch,
            "workshop_id": workshop_id,
            "workshop_url": workshop_url,
            "achievement": achievement_raw.strip() if achievement_raw else None,
            "duration_raw": duration_raw.strip() if duration_raw else None,
        }
        rows.append(record)

    if not rows:
        raise MaplistParseError("No valid rows parsed from EXG maplist HTML")
    return rows


def fetch_and_parse(settings: Settings, logger: logging.Logger) -> List[dict]:
    _cleanup_debug_html(logger)
    response = requests.get(EXG_URL, timeout=20, headers={"User-Agent": USER_AGENT})
    if not response.ok:
        raise MaplistParseError(f"EXG maplist fetch failed: {response.status_code}")
    html = response.text
    try:
        rows = parse_maplist(html)
    except MaplistParseError:
        _save_debug_html(logger, html)
        raise

    if settings.debug:
        _save_debug_html(logger, html)
    return rows


IMAGE_CLASS = "workshopItemPreviewImageEnlargeable"


def _existing_images(static_map_dir: str) -> set[str]:
    if not os.path.exists(static_map_dir):
        return set()
    existing = set()
    for name in os.listdir(static_map_dir):
        if name.lower().endswith(".jpg"):
            existing.add(os.path.splitext(name)[0].lower())
    return existing


def _fetch_workshop_image_url(workshop_url: str) -> str | None:
    response = requests.get(workshop_url, timeout=20, headers={"User-Agent": USER_AGENT})
    if not response.ok:
        return None
    soup = BeautifulSoup(response.text, "html.parser")
    img = soup.find("img", class_=IMAGE_CLASS)
    if img and img.get("src"):
        return img["src"]
    return None


def fetch_missing_images(settings: Settings, logger: logging.Logger, db: MySQLClient) -> None:
    static_map_dir = os.path.join(settings.project_root, settings.static_dir_name, "maps")
    ensure_dir(static_map_dir)
    existing = _existing_images(static_map_dir)

    maps = db.get_maps_for_images()
    logger.info("Checking workshop images for %s maps", len(maps))

    for entry in maps:
        map_key = (entry.get("map_key") or "").lower()
        if not map_key or map_key in existing:
            continue
        workshop_id = entry.get("workshop_id")
        workshop_url = entry.get("workshop_url")
        if not workshop_url and workshop_id:
            workshop_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
        if not workshop_url:
            continue

        image_url = _fetch_workshop_image_url(workshop_url)
        if not image_url:
            logger.warning("No workshop image found for %s", map_key)
            continue

        try:
            image_response = requests.get(image_url, timeout=20, headers={"User-Agent": USER_AGENT})
            if not image_response.ok:
                logger.warning("Failed to download image for %s", map_key)
                continue
            target_path = os.path.join(static_map_dir, f"{map_key}.jpg")
            with open(target_path, "wb") as handle:
                handle.write(image_response.content)
            existing.add(map_key)
            logger.info("Saved workshop image for %s", map_key)
        except Exception as exc:
            logger.warning("Image download failed for %s: %s", map_key, exc)


INDEX_STAMP_KEY = "map_sidecar:index_stamp"
EXG_LAST_INGEST_KEY = "map_sidecar:exg_last_ingest"


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


def cmd_poll_servers(settings, logger, db, cache) -> None:
    poll_servers(settings, logger, db, cache)


def cmd_ingest_exg(settings, logger, db, cache) -> None:
    logger.warning("EXG ingestion is disabled on overseas hosts; use the ingest sidecar endpoint.")


def cmd_exg_health(settings, logger, cache) -> None:
    max_age = int(os.environ.get("EXG_HEALTH_MAX_AGE_SECONDS", "7200"))
    last_ingest = cache.get(EXG_LAST_INGEST_KEY)
    if not last_ingest:
        logger.warning("EXG ingest timestamp not found in cache")
        return
    try:
        last_epoch = int(last_ingest)
    except ValueError:
        logger.warning("EXG ingest timestamp is invalid: %s", last_ingest)
        return
    age = int(time.time()) - last_epoch
    if age > max_age:
        logger.warning("EXG ingest is stale (%s seconds ago)", age)
    else:
        logger.info("EXG ingest is healthy (%s seconds ago)", age)


def cmd_refresh_index(settings, logger, db, cache) -> None:
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


def cmd_fetch_images(settings, logger, db) -> None:
    fetch_missing_images(settings, logger, db)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CS2ZE map sidecar")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("poll-servers", help="Poll /servers.json and export translations")
    sub.add_parser("ingest-exg", help="(disabled) formerly fetched EXG maplist")
    sub.add_parser("exg-health", help="Check last EXG ingest timestamp")
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
        cmd_poll_servers(settings, logger, db, cache)
    elif args.command == "ingest-exg":
        cmd_ingest_exg(settings, logger, db, cache)
    elif args.command == "exg-health":
        cmd_exg_health(settings, logger, cache)
    elif args.command == "refresh-index":
        cmd_refresh_index(settings, logger, db, cache)
    elif args.command == "fetch-images":
        cmd_fetch_images(settings, logger, db)
    else:
        logger.error("Unknown command: %s", args.command)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
