from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict

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
from tools.map_sidecar.utils import BEIJING_TZ, ensure_dir

MAP_RE = re.compile(r"^[a-z0-9]+_[a-z0-9][a-z0-9_\-]*$", re.I)
DEBUG_DIR = os.path.join(os.path.dirname(__file__), "debug", "exg_html")
USER_AGENT = "cs2ze-exg-cn-fetcher/1.0"
SELECTOR_EXG_ROWS = "#data-tablebody tr"
POST_RENDER_WAIT_MS = 750


class MaplistParseError(RuntimeError):
    pass

@dataclass
class MapEntry:
    map: str
    name_zh: str
    difficulty: str
    tags: List[str]
    cooldown: Dict[str, Any]
    achievement: str
    workshop: Dict[str, Any]


def norm(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = re.sub(r"\s+", " ", str(s)).strip()
    if s in ("无", "N/A", "-", "—", ""):
        return ""
    return s


def split_tags(tag_cell: str) -> List[str]:
    tag_cell = norm(tag_cell)
    if not tag_cell:
        return []
    parts = re.split(r"[,\uFF0C]", tag_cell)
    return [p.strip() for p in parts if p.strip()]


def workshop_id_from_url(url: str) -> str:
    if not url:
        return "0"
    m = re.search(r"(\d{8,})", url)
    return m.group(1) if m else "0"


def validate_entries(entries: List[MapEntry]) -> None:
    required = {"map", "name_zh", "difficulty", "tags", "cooldown", "achievement", "workshop"}
    for idx, entry in enumerate(entries):
        data = asdict(entry)
        missing = required - data.keys()
        if missing:
            raise MaplistParseError(f"Entry {idx} missing keys: {sorted(missing)}")
        if not isinstance(data["map"], str):
            raise MaplistParseError(f"Entry {idx} map must be a string")
        if not isinstance(data["name_zh"], str):
            raise MaplistParseError(f"Entry {idx} name_zh must be a string")
        if not isinstance(data["difficulty"], str):
            raise MaplistParseError(f"Entry {idx} difficulty must be a string")
        if not isinstance(data["tags"], list) or any(not isinstance(t, str) for t in data["tags"]):
            raise MaplistParseError(f"Entry {idx} tags must be a list of strings")
        cooldown = data["cooldown"]
        if not isinstance(cooldown, dict):
            raise MaplistParseError(f"Entry {idx} cooldown must be an object")
        if not isinstance(cooldown.get("duration_raw", ""), str):
            raise MaplistParseError(f"Entry {idx} cooldown.duration_raw must be a string")
        deadline = cooldown.get("deadline")
        if deadline is not None and not isinstance(deadline, str):
            raise MaplistParseError(f"Entry {idx} cooldown.deadline must be a string or null")
        workshop = data["workshop"]
        if not isinstance(workshop, dict):
            raise MaplistParseError(f"Entry {idx} workshop must be an object")
        if not isinstance(workshop.get("id", ""), str):
            raise MaplistParseError(f"Entry {idx} workshop.id must be a string")
        if not isinstance(workshop.get("url", ""), str):
            raise MaplistParseError(f"Entry {idx} workshop.url must be a string")


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
    thead = table.find("thead")
    header_row = thead.find("tr") if thead else None
    if not header_row:
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
        elif any(token in normalized for token in ["名称", "中文", "name", "zh", "cn"]):
            mapping["name"] = idx
        elif any(token in normalized for token in ["难度", "difficulty", "等级"]):
            mapping["difficulty"] = idx
        elif any(token in normalized for token in ["标签", "tag"]):
            mapping["tags"] = idx
        elif any(token in normalized for token in ["冷却", "cd", "cooldown", "时长", "duration"]):
            if any(token in normalized for token in ["截止", "结束", "到期", "deadline"]):
                mapping["deadline"] = idx
            else:
                mapping["duration"] = idx
        elif any(token in normalized for token in ["成就", "achievement"]):
            mapping["achievement"] = idx
        elif any(token in normalized for token in ["工坊", "workshop", "link", "链接", "id"]):
            mapping["workshop"] = idx
    return mapping

def _cell_text(cells: List[BeautifulSoup], idx: Optional[int]) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return norm(cells[idx].get_text(" ", strip=True))


def _cell_workshop(cells: List[BeautifulSoup], idx: Optional[int]) -> tuple[str, str]:
    if idx is None or idx >= len(cells):
        return "", ""
    cell = cells[idx]
    link = cell.find("a", href=True)
    url = norm(link["href"]) if link else norm(cell.get_text(" ", strip=True))
    return workshop_id_from_url(url), url


def parse_maplist(html: str, logger: Optional[logging.Logger] = None) -> List[MapEntry]:
    soup = BeautifulSoup(html, "html.parser")
    tbody = soup.select_one("tbody#data-tablebody")
    if not tbody:
        raise MaplistParseError(
            "No tbody#data-tablebody found in EXG maplist HTML. "
            "Ensure the HTML is fully rendered and contains the EXG table body."
        )

    table = tbody.find_parent("table")
    headers = _extract_headers(table) if table else []
    mapping = _map_columns(headers)

    entries: List[MapEntry] = []
    rows = tbody.find_all("tr")
    if logger:
        logger.info("EXG maplist rows found: %s", len(rows))
    for row in rows:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        map_raw = _cell_text(cells, mapping.get("map", 0) if mapping else 0)
        if not map_raw or not MAP_RE.match(map_raw):
            continue

        name_raw = _cell_text(cells, mapping.get("name") if mapping else 1)
        difficulty_raw = _cell_text(cells, mapping.get("difficulty") if mapping else 2)
        tags_raw = _cell_text(cells, mapping.get("tags") if mapping else 3)
        duration_raw = _cell_text(cells, mapping.get("duration") if mapping else 4)
        deadline_raw = _cell_text(cells, mapping.get("deadline") if mapping else 5)
        achievement_raw = _cell_text(cells, mapping.get("achievement") if mapping else 6)
        workshop_id, workshop_url = _cell_workshop(
            cells, mapping.get("workshop") if mapping else 7
        )

        entries.append(
            MapEntry(
                map=map_raw,
                name_zh=name_raw,
                difficulty=difficulty_raw or "未标注",
                tags=split_tags(tags_raw),
                cooldown={"duration_raw": duration_raw, "deadline": deadline_raw or None},
                achievement=achievement_raw,
                workshop={"id": workshop_id, "url": workshop_url},
            )
        )

    if not entries:
        raise MaplistParseError("No valid rows parsed from EXG maplist HTML")
    validate_entries(entries)
    if logger:
        logger.info("EXG maplist valid entries: %s", len(entries))
    return entries


def serialize_entries(entries: List[MapEntry]) -> List[dict]:
    return [asdict(entry) for entry in entries]


def write_normalized_json(entries: List[MapEntry], output_path: str) -> None:
    data = serialize_entries(entries)
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)



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
    min_rows = 50
    logger.info("Fetching EXG maplist with Chromium (headless=%s)", headless)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            executable_path="/usr/bin/chromium-browser", 
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            page.goto(settings.exg_maplist_url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_function(
                f"document.querySelectorAll('#data-tablebody tr').length > {min_rows}",
                timeout=timeout_ms,
            )
            page.wait_for_timeout(POST_RENDER_WAIT_MS)
            html = page.content()
        except PlaywrightTimeoutError as exc:
            html = page.content()
            title = page.title()
            row_count = page.eval_on_selector_all(SELECTOR_EXG_ROWS, "els => els.length")
            logger.error("EXG maplist render timeout: title=%s rows=%s", title, row_count)
            _save_debug_html(logger, html)
            raise MaplistParseError("Timed out waiting for EXG maplist rows to render") from exc
        except Exception:
            html = page.content()
            title = page.title()
            row_count = page.eval_on_selector_all(SELECTOR_EXG_ROWS, "els => els.length")
            logger.error("EXG maplist render failed: title=%s rows=%s", title, row_count)
            _save_debug_html(logger, html)
            raise
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


def build_payload(entries: List[MapEntry]) -> dict:
    return {
        "source": "exg_maplist",
        "fetched_at_epoch": int(time.time()),
        "records": serialize_entries(entries),
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
    input_html: Optional[str] = None,
    parse_only: bool = False,
) -> int:
    effective_dry_run = dry_run or parse_only
    try:
        validate_cn_fetcher_settings(settings, dry_run=effective_dry_run)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    _cleanup_debug_html(logger, settings.retention_hours)
    if input_html:
        with open(input_html, "r", encoding="utf-8", errors="ignore") as handle:
            html = handle.read()
        logger.info("Loaded HTML from %s", input_html)
    else:
        html = fetch_exg_html(settings, logger, headless=headless, use_requests=use_requests)
    try:
        _ensure_rendered_table(html)
        entries = parse_maplist(html, logger=logger)
    except MaplistParseError:
        _save_debug_html(logger, html)
        raise

    if settings.debug:
        _save_debug_html(logger, html)

    normalized_path = os.path.join(settings.project_root, "maplist.normalized.json")
    write_normalized_json(entries, normalized_path)
    logger.info("Normalized maplist written: %s", normalized_path)

    payload = build_payload(entries)

    if effective_dry_run:
        logger.info("Dry run: parsed %s records", len(entries))
        if entries:
            sample = entries[0]
            logger.info(
                "Dry run sample: %s",
                {
                    "map": sample.map,
                    "name_zh": sample.name_zh,
                    "difficulty": sample.difficulty,
                    "tags": sample.tags,
                    "cooldown": sample.cooldown,
                    "workshop_id": sample.workshop.get("id", ""),
                },
            )
        if dump_payload:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            preview = payload["records"][:3]
            print(json.dumps({"record_count": len(entries), "preview": preview}, ensure_ascii=False, indent=2))
        return 0

    post_payload(settings, payload, logger)
    logger.info("Posted %s records to overseas ingest", len(entries))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EXG maplist CN fetcher")
    parser.add_argument("--dry-run", action="store_true", help="Fetch + parse only; do not POST")
    parser.add_argument("--dump-payload", action="store_true", help="Print full payload JSON")
    parser.add_argument("--input-html", help="Parse a saved EXG HTML file instead of fetching")
    parser.add_argument(
        "--parse-only",
        action="store_true",
        help="Parse HTML (optionally from --input-html) and exit without POST",
    )
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
            input_html=args.input_html,
            parse_only=args.parse_only,
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
