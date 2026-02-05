from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from tools.map_sidecar.config import CnFetcherSettings, load_cn_fetcher_settings, validate_cn_fetcher_settings
from tools.map_sidecar.logging_utils import setup_logging
from tools.map_sidecar.utils import BEIJING_TZ, ensure_dir, normalize_map_key, parse_beijing_time
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug", "exg_html")
USER_AGENT = "cs2ze-exg-cn-fetcher/1.0"
SELECTOR_EXG_ROWS = "#data-tablebody tr"
POST_RENDER_WAIT_MS = 750


class MaplistParseError(RuntimeError):
    pass


def _cleanup_debug_html(logger: logging.Logger, retention_hours: int) -> None:
    ensure_dir(DEBUG_DIR)
    cutoff = datetime.now(tz=BEIJING_TZ) - timedelta(hours=retention_hours)
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


def _save_debug_html(logger: logging.Logger, html: str) -> str:
    ensure_dir(DEBUG_DIR)
    timestamp = datetime.now(tz=BEIJING_TZ).strftime("%Y%m%d_%H%M")
    filename = f"exg_maplist_{timestamp}.html"
    path = os.path.join(DEBUG_DIR, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    logger.warning("Saved EXG maplist HTML for debugging: %s", path)
    return path


def _normalize_header(text: str) -> str:
    return "".join(text.strip().lower().split())


def _find_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    tables = soup.find_all("table")
    if not tables:
        return None
    return max(tables, key=lambda table: len(table.find_all("tr")))


def _extract_headers(table: BeautifulSoup) -> List[str]:
    header_row = table.find("tr")
    if not header_row:
        return []
    return [cell.get_text(strip=True) for cell in header_row.find_all(["th", "td"])]


def _map_columns(headers: List[str]) -> dict:
    mapping: dict[str, int] = {}
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

    data_rows = table.find_all("tr")[1:] if headers else table.find_all("tr")
    if not data_rows:
        raise MaplistParseError("No data rows found in EXG maplist HTML")

    rows = []
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
            "duration_raw": duration_raw.strip() if duration_raw else None,
            "cooldown_end_epoch": cooldown_epoch,
            "workshop_id": workshop_id,
            "workshop_url": workshop_url,
            "achievement": achievement_raw.strip() if achievement_raw else None,
        }
        rows.append(record)

    if not rows:
        raise MaplistParseError("No valid rows parsed from EXG maplist HTML")
    return rows


def _fetch_exg_html_requests(settings: CnFetcherSettings) -> str:
    response = requests.get(
        settings.exg_maplist_url,
        timeout=settings.fetch_timeout_seconds,
        headers={"User-Agent": USER_AGENT},
    )
    if not response.ok:
        raise MaplistParseError(f"EXG maplist fetch failed: {response.status_code}")
    return response.text


def _fetch_exg_html_browser(settings: CnFetcherSettings, logger: logging.Logger, headless: bool) -> str:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is required for EXG maplist rendering. Install it with "
            "`pip install playwright` and then run "
            "`python -m playwright install --with-deps chromium`."
        ) from exc

    timeout_ms = settings.fetch_timeout_seconds * 1000
    logger.info("Fetching EXG maplist with Chromium (headless=%s)", headless)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            page.goto(settings.exg_maplist_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_selector(SELECTOR_EXG_ROWS, timeout=timeout_ms)
            page.wait_for_timeout(POST_RENDER_WAIT_MS)
            html = page.content()
        except PlaywrightTimeoutError as exc:
            raise MaplistParseError("Timed out waiting for EXG maplist rows to render") from exc
        finally:
            context.close()
            browser.close()

    return html


def _ensure_rendered_table(html: str) -> None:
    if "#data-tablebody" not in html:
        raise MaplistParseError("Rendered HTML missing #data-tablebody")
    if not re.search(r"<tbody[^>]*id=[\"']data-tablebody[\"'][^>]*>.*?<tr", html, re.S):
        raise MaplistParseError("Rendered HTML missing #data-tablebody rows")


def fetch_exg_html(
    settings: CnFetcherSettings,
    logger: logging.Logger,
    headless: bool = True,
    use_requests: bool = False,
) -> str:
    if use_requests:
        logger.warning("Using requests fallback for EXG maplist (debug only)")
        return _fetch_exg_html_requests(settings)
    return _fetch_exg_html_browser(settings, logger, headless)


def build_payload(records: List[dict]) -> dict:
    return {
        "source": "exg_maplist",
        "fetched_at_epoch": int(time.time()),
        "records": records,
    }


def post_payload(settings: CnFetcherSettings, payload: dict, logger: logging.Logger) -> None:
    headers = {
        "Authorization": f"Bearer {settings.ingest_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(
        settings.overseas_ingest_url,
        headers=headers,
        json=payload,
        timeout=settings.fetch_timeout_seconds,
    )
    if response.status_code == 401:
        raise RuntimeError("Ingest rejected: unauthorized")
    if response.status_code >= 400:
        raise RuntimeError(f"Ingest failed: {response.status_code} {response.text}")
    logger.info("Ingest accepted: %s", response.status_code)


def run_fetch(
    settings: CnFetcherSettings,
    logger: logging.Logger,
    dry_run: bool,
    dump_payload: bool,
    headless: bool = True,
    use_requests: bool = False,
) -> int:
    try:
        validate_cn_fetcher_settings(settings, dry_run=dry_run)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    _cleanup_debug_html(logger, settings.retention_hours)
    html = fetch_exg_html(settings, logger, headless=headless, use_requests=use_requests)
    try:
        _ensure_rendered_table(html)
        records = parse_maplist(html)
    except MaplistParseError:
        _save_debug_html(logger, html)
        raise

    if settings.debug:
        _save_debug_html(logger, html)

    payload = build_payload(records)

    if dry_run:
        logger.info("Dry run: parsed %s records", len(records))
        if dump_payload:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            preview = payload["records"][:3]
            print(json.dumps({"record_count": len(records), "preview": preview}, ensure_ascii=False, indent=2))
        return 0

    post_payload(settings, payload, logger)
    logger.info("Posted %s records to overseas ingest", len(records))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EXG maplist CN fetcher")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + parse only; do not POST")
    parser.add_argument("--dump-payload", action="store_true", help="Print full payload JSON")
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run Chromium with a visible window (debugging only)",
    )
    parser.add_argument(
        "--use-requests",
        action="store_true",
        help="Use requests instead of Chromium rendering (debugging only)",
    )
    return parser


def main() -> int:
    settings = load_cn_fetcher_settings()
    logger = setup_logging(settings.log_dir)
    logger.setLevel(logging.INFO)

    parser = build_parser()
    args = parser.parse_args()

    try:
        return run_fetch(
            settings,
            logger,
            args.dry_run,
            args.dump_payload,
            headless=not args.headed,
            use_requests=args.use_requests,
        )
    except MaplistParseError as exc:
        logger.error("EXG maplist parse failed: %s", exc)
        return 1
    except requests.RequestException as exc:
        logger.error("Network error: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Fetch failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
