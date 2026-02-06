from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from tools.map_sidecar.config import Settings
from tools.map_sidecar.utils import (
    BEIJING_TZ,
    convert_to_traditional,
    ensure_dir,
    normalize_map_key,
    parse_beijing_time,
)

EXG_URL = "https://list.darkrp.cn:9000/serverlist/cs2maplist"
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug", "exg_html")
USER_AGENT = "cs2ze-map-sidecar/1.0"


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
    url_match = re.search(r"https?://steamcommunity\.com/sharedfiles/filedetails/\?id=(\d+)", text)
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
        cooldown_raw_clean = (cooldown_raw or "").strip()
        cooldown_epoch = parse_beijing_time(cooldown_raw_clean)
        if cooldown_raw_clean and cooldown_epoch is None and cooldown_raw_clean not in {"无", "無", "-", "N/A"}:
            raise MaplistParseError(f"Invalid cooldown deadline: {cooldown_raw_clean}")
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
