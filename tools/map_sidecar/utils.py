from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore
try:
    from opencc import OpenCC
except ImportError:  # pragma: no cover
    OpenCC = None  # type: ignore

BEIJING_TZ = ZoneInfo("Asia/Shanghai")
MAP_KEY_RE = re.compile(r"^[a-z0-9_]+$")
OPENCC_S2T = OpenCC("s2t") if OpenCC else None


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
    if not OPENCC_S2T:
        raise RuntimeError("OpenCC s2t is required for zh_tw conversion")
    return OPENCC_S2T.convert(str(text))


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
        "%m/%d/%Y, %I:%M:%S %p",
        "%m/%d/%Y, %I:%M %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
    ]
    for pattern in patterns:
        try:
            dt = datetime.strptime(cleaned, pattern)
            dt = dt.replace(tzinfo=BEIJING_TZ)
            return int(dt.timestamp())
        except ValueError:
            continue
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?", cleaned)
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
    match = re.search(
        r"(\d{1,2})/(\d{1,2})/(\d{4}),?\s+(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?\s*([AaPp][Mm])",
        cleaned,
    )
    if match:
        month, day, year, hour, minute, second, meridiem = match.groups()
        hour_int = int(hour)
        meridiem = meridiem.lower()
        if meridiem == "pm" and hour_int != 12:
            hour_int += 12
        if meridiem == "am" and hour_int == 12:
            hour_int = 0
        dt = datetime(
            int(year),
            int(month),
            int(day),
            hour_int,
            int(minute),
            int(second or 0),
            tzinfo=BEIJING_TZ,
        )
        return int(dt.timestamp())
    return None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)
