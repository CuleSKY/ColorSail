from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import time
from dataclasses import asdict
from datetime import datetime
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

from tools.map_sidecar.config import load_cn_fetcher_settings
from tools.map_sidecar.exporter import atomic_write_json
from tools.map_sidecar.logging_utils import setup_logging
from tools.map_sidecar.utils import BEIJING_TZ, ensure_dir
from tools.normalize_maplist_from_html import (
    MAP_RE,
    MapEntry,
    norm,
    split_tags,
    workshop_id_from_url,
)

USER_AGENT = "cs2ze-exg-cn-pipeline/1.0"
SELECTOR_ROWS = "#data-tablebody tr"
CHALLENGE_MARKERS = (
    "captcha",
    "cloudflare",
    "challenge",
    "attention required",
    "verify you are human",
)


class MaplistNormalizationError(RuntimeError):
    pass


def _project_root() -> str:
    return os.environ.get("PROJECT_ROOT", os.getcwd())


def _default_html_path() -> str:
    return os.path.join(_project_root(), "tools", "map_sidecar", "state", "exg_maplist_latest.html")


def _default_json_path() -> str:
    return os.path.join(_project_root(), "maplist_normalized.json")


def _timestamped_name(prefix: str, suffix: str) -> str:
    stamp = datetime.now(tz=BEIJING_TZ).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}{suffix}"


def _debug_html_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "debug", "exg_html")


def _debug_screenshot_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "debug", "exg_screenshots")


def _save_debug_html(html: str) -> str:
    ensure_dir(_debug_html_dir())
    filename = _timestamped_name("exg_maplist", ".html")
    path = os.path.join(_debug_html_dir(), filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return path


def _save_debug_screenshot(page, logger: logging.Logger) -> Optional[str]:
    ensure_dir(_debug_screenshot_dir())
    filename = _timestamped_name("exg_maplist", ".png")
    path = os.path.join(_debug_screenshot_dir(), filename)
    try:
        page.screenshot(path=path, full_page=True)
    except Exception as exc:
        logger.warning("Failed to capture screenshot: %s", exc)
        return None
    return path


def _require_playwright():
    if importlib.util.find_spec("playwright") is None:
        raise RuntimeError(
            "Playwright is required for EXG maplist rendering. Install it with "
            "`pip install playwright` and then run "
            "`python -m playwright install --with-deps chromium`."
        )
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    return sync_playwright, PlaywrightTimeoutError


def _html_looks_like_challenge(html: str) -> bool:
    if not html:
        return False
    lowered = html.lower()
    return any(marker in lowered for marker in CHALLENGE_MARKERS)


def _summarize_page(logger: logging.Logger, page, html: str) -> None:
    try:
        title = page.title()
    except Exception:
        title = ""
    try:
        url = page.url
    except Exception:
        url = ""
    row_count = 0
    try:
        row_count = page.eval_on_selector_all(SELECTOR_ROWS, "els => els.length")
    except Exception:
        row_count = 0
    logger.info("Rendered page title=%s url=%s rows=%s", title, url, row_count)
    if _html_looks_like_challenge(html):
        logger.warning("Rendered HTML looks like a challenge/captcha page")


def fetch_rendered_html(
    url: str,
    save_html: str,
    logger: logging.Logger,
    timeout_seconds: int,
    headless: bool,
    debug: bool,
) -> str:
    sync_playwright, PlaywrightTimeoutError = _require_playwright()
    ensure_dir(os.path.dirname(save_html) or ".")
    html = ""
    failed = False
    debug_html_path = None
    screenshot_path = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            executable_path="/usr/bin/chromium-browser",
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_seconds * 1000)
            end_time = time.time() + timeout_seconds
            row_count = 0
            while time.time() < end_time:
                row_count = page.eval_on_selector_all(SELECTOR_ROWS, "els => els.length")
                if row_count > 0:
                    break
                page.wait_for_timeout(500)
            if row_count == 0:
                logger.warning("No rows found after render; saving HTML for debugging")
            html = page.content()
        except PlaywrightTimeoutError as exc:
            failed = True
            html = page.content()
            logger.error("Render timeout: %s", exc)
        except Exception as exc:
            failed = True
            html = page.content()
            logger.error("Render failed: %s", exc)
        finally:
            if not html:
                try:
                    html = page.content()
                except Exception:
                    html = ""
            _summarize_page(logger, page, html)
            with open(save_html, "w", encoding="utf-8") as handle:
                handle.write(html)
            logger.info("Saved EXG HTML: %s", save_html)
            if debug or failed:
                debug_html_path = _save_debug_html(html)
            if debug or failed:
                screenshot_path = _save_debug_screenshot(page, logger)
            context.close()
            browser.close()

    if debug_html_path:
        logger.warning("Saved debug HTML: %s", debug_html_path)
    if screenshot_path:
        logger.warning("Saved debug screenshot: %s", screenshot_path)
    return html


def parse_maplist_html(html_path: str) -> list[MapEntry]:
    html = open(html_path, "r", encoding="utf-8", errors="ignore").read()
    soup = BeautifulSoup(html, "html.parser")
    tbody = soup.select_one("tbody#data-tablebody")
    if not tbody:
        raise MaplistNormalizationError(
            f"Missing tbody#data-tablebody in HTML. Check rendered HTML at: {html_path}"
        )

    entries: list[MapEntry] = []
    for tr in tbody.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue

        map_name = norm(tds[0].get_text(" ", strip=True))
        if not map_name or not MAP_RE.match(map_name):
            continue

        cn_name = norm(tds[1].get_text(" ", strip=True))
        difficulty = norm(tds[2].get_text(" ", strip=True)) or "未标注"
        tag_raw = norm(tds[3].get_text(" ", strip=True))
        tags = split_tags(tag_raw)

        cooldown_duration = norm(tds[4].get_text(" ", strip=True))
        deadline = norm(tds[5].get_text(" ", strip=True)) or None
        achievement = norm(tds[6].get_text(" ", strip=True))

        a = tds[7].find("a", href=True)
        wurl = norm(a["href"]) if a else ""
        wid = workshop_id_from_url(wurl) if wurl else ""

        entries.append(
            MapEntry(
                map=map_name,
                name_zh=cn_name,
                difficulty=difficulty,
                tags=tags,
                cooldown={"duration_raw": cooldown_duration, "deadline": deadline},
                achievement=achievement,
                workshop={"id": wid, "url": wurl},
            )
        )

    if not entries:
        raise MaplistNormalizationError(
            f"No valid rows parsed from HTML. Check rendered HTML at: {html_path}"
        )
    return entries


def _load_existing_json(path: str) -> list[dict] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def write_normalized_json(entries: Iterable[MapEntry], output_path: str) -> bool:
    data = [asdict(entry) for entry in entries]
    existing = _load_existing_json(output_path)
    if existing == data:
        return False
    ensure_dir(os.path.dirname(output_path) or ".")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return True


def post_normalized_payload(ingest_url: str, ingest_token: str, payload: dict) -> None:
    headers = {
        "Authorization": f"Bearer {ingest_token}",
        "Content-Type": "application/json",
    }
    response = requests.post(ingest_url, headers=headers, json=payload, timeout=20)
    if response.status_code == 401:
        raise RuntimeError("Ingest rejected: unauthorized")
    if response.status_code >= 400:
        raise RuntimeError(f"Ingest failed: {response.status_code} {response.text}")


def load_json_payload(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Normalized JSON must be a list")
    return data


def push_normalized_json(
    input_json: str,
    logger: logging.Logger,
    dry_run: bool,
    mode: str,
    ingest_url: str,
    ingest_token: str,
    output_path: str,
) -> None:
    payload = load_json_payload(input_json)
    if dry_run:
        logger.info("Dry run: skipping push (%s entries)", len(payload))
        return
    if mode == "file":
        atomic_write_json(output_path, payload)
        logger.info("Normalized maplist written to %s", output_path)
        return
    if mode == "ingest":
        if not ingest_url or not ingest_token:
            raise RuntimeError("Ingest requires OVERSEAS_INGEST_URL and INGEST_TOKEN")
        post_payload = {
            "source": "exg_maplist",
            "fetched_at_epoch": int(time.time()),
            "records": payload,
        }
        post_normalized_payload(ingest_url, ingest_token, post_payload)
        logger.info("Posted %s records to ingest", len(payload))
        return
    raise RuntimeError(f"Unknown push mode: {mode}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EXG CN maplist pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch rendered EXG HTML")
    fetch.add_argument("--save-html", default=_default_html_path())
    fetch.add_argument("--debug", action="store_true")
    fetch.add_argument("--headed", action="store_true")

    normalize = sub.add_parser("normalize", help="Normalize local EXG HTML")
    normalize.add_argument("--input-html")
    normalize.add_argument("--output-json", default=_default_json_path())
    normalize.add_argument("--save-html", default=_default_html_path())

    push = sub.add_parser("push", help="Push normalized JSON to ingest or file")
    push.add_argument("--input-json", default=_default_json_path())
    push.add_argument("--dry-run", action="store_true")
    push.add_argument("--output-json", default=_default_json_path())

    run = sub.add_parser("run", help="Fetch -> normalize -> push")
    run.add_argument("--input-html")
    run.add_argument("--output-json", default=_default_json_path())
    run.add_argument("--save-html", default=_default_html_path())
    run.add_argument("--debug", action="store_true")
    run.add_argument("--headed", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    for command in (push, run):
        command.add_argument(
            "--push-mode",
            choices=("ingest", "file"),
            default=os.environ.get("EXG_MAPLIST_PUSH_MODE", "file"),
        )
        command.add_argument(
            "--output-path",
            default=os.environ.get("EXG_MAPLIST_OUTPUT_PATH", _default_json_path()),
            help="Destination path when push-mode=file",
        )
    return parser


def main() -> int:
    settings = load_cn_fetcher_settings()
    logger = setup_logging(settings.log_dir)
    logger.setLevel(logging.INFO)
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "fetch":
            fetch_rendered_html(
                settings.exg_maplist_url,
                args.save_html,
                logger,
                settings.fetch_timeout_seconds,
                headless=not args.headed,
                debug=args.debug or settings.debug,
            )
            return 0
        if args.command == "normalize":
            input_html = args.input_html or args.save_html
            entries = parse_maplist_html(input_html)
            changed = write_normalized_json(entries, args.output_json)
            logger.info(
                "Normalized maplist %s: %s entries",
                "written" if changed else "unchanged",
                len(entries),
            )
            return 0
        if args.command == "push":
            push_normalized_json(
                args.input_json,
                logger,
                args.dry_run,
                args.push_mode,
                settings.overseas_ingest_url,
                settings.ingest_token,
                args.output_path,
            )
            return 0
        if args.command == "run":
            input_html = args.input_html
            if not input_html:
                fetch_rendered_html(
                    settings.exg_maplist_url,
                    args.save_html,
                    logger,
                    settings.fetch_timeout_seconds,
                    headless=not args.headed,
                    debug=args.debug or settings.debug,
                )
                input_html = args.save_html
            entries = parse_maplist_html(input_html)
            changed = write_normalized_json(entries, args.output_json)
            logger.info(
                "Normalized maplist %s: %s entries",
                "written" if changed else "unchanged",
                len(entries),
            )
            if changed:
                push_normalized_json(
                    args.output_json,
                    logger,
                    args.dry_run,
                    args.push_mode,
                    settings.overseas_ingest_url,
                    settings.ingest_token,
                    args.output_path,
                )
            else:
                logger.info("Skipping push: normalized maplist unchanged")
            return 0
    except MaplistNormalizationError as exc:
        logger.error("Normalization failed: %s", exc)
        return 1
    except requests.RequestException as exc:
        logger.error("Network error: %s", exc)
        return 1
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
