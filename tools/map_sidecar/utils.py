from __future__ import annotations

import logging
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
OPENCC_PROFILE = "s2tw"
_OPENCC_CONVERTER = None
_OPENCC_INIT_ATTEMPTED = False
_OPENCC_WARNING_EMITTED = False
logger = logging.getLogger(__name__)


def _warn_opencc_unavailable(message: str) -> None:
    global _OPENCC_WARNING_EMITTED
    if _OPENCC_WARNING_EMITTED:
        return
    _OPENCC_WARNING_EMITTED = True
    logger.warning(message)


def _get_opencc_converter():
    global _OPENCC_INIT_ATTEMPTED, _OPENCC_CONVERTER
    if _OPENCC_INIT_ATTEMPTED:
        return _OPENCC_CONVERTER
    _OPENCC_INIT_ATTEMPTED = True
    if OpenCC is None:
        _warn_opencc_unavailable("OpenCC is unavailable; zh_tw conversion will be skipped.")
        return None
    try:
        _OPENCC_CONVERTER = OpenCC(OPENCC_PROFILE)
    except Exception as exc:  # pragma: no cover - defensive
        _warn_opencc_unavailable(f"OpenCC init failed; zh_tw conversion will be skipped: {exc}")
        _OPENCC_CONVERTER = None
    return _OPENCC_CONVERTER


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


def convert_to_traditional(text: str | None) -> Optional[str]:
    """Convert zh_cn to zh_tw using OpenCC s2tw (Taiwan traditional).

    Returns None when conversion is unavailable, preserving manual edits by allowing
    callers to skip updating name_zh_tw if a non-empty value already exists.
    """
    if not text:
        return None
    converter = _get_opencc_converter()
    if not converter:
        return None
    try:
        return converter.convert(str(text))
    except Exception as exc:  # pragma: no cover - defensive
        _warn_opencc_unavailable(f"OpenCC conversion failed; zh_tw conversion will be skipped: {exc}")
        return None


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


def _self_check_opencc() -> int:
    converter = _get_opencc_converter()
    print(f"opencc_profile={OPENCC_PROFILE}")
    if not converter:
        print("opencc_status=unavailable")
        return 0
    print(f"地图 -> {convert_to_traditional('地图')}")
    print(f"后台 -> {convert_to_traditional('后台')}")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Map sidecar utilities")
    parser.add_argument(
        "--self-check-opencc",
        action="store_true",
        help="Print OpenCC profile and sample conversions for zh_tw.",
    )
    args = parser.parse_args()
    if args.self_check_opencc:
        raise SystemExit(_self_check_opencc())
