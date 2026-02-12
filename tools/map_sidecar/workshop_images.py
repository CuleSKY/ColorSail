from __future__ import annotations

import logging
import os
import random
import time

import requests
from bs4 import BeautifulSoup

from tools.map_sidecar.config import Settings
from tools.map_sidecar.db import MySQLClient
from tools.map_sidecar.utils import ensure_dir

IMAGE_CLASS = "workshopItemPreviewImageEnlargeable"
USER_AGENT = "cs2ze-map-sidecar/1.0"
MAX_IMAGES_PER_MINUTE = 5
MIN_IMAGE_BYTES = 1024
WORKSHOP_URL_PREFIX = os.environ.get(
    "WORKSHOP_URL_PREFIX",
    "https://example.com/sharedfiles/filedetails/?id=",
).strip()


def _existing_images(static_map_dir: str) -> tuple[set[str], set[str]]:
    if not os.path.exists(static_map_dir):
        return set(), set()
    ok_keys = set()
    bad_keys = set()
    for name in os.listdir(static_map_dir):
        if name.lower().endswith(".jpg"):
            key = os.path.splitext(name)[0].lower()
            path = os.path.join(static_map_dir, name)
            size = os.path.getsize(path)
            if size < MIN_IMAGE_BYTES:
                bad_keys.add(key)
            else:
                ok_keys.add(key)
    return ok_keys, bad_keys


def _sleep_jitter(min_seconds: float, max_seconds: float) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def _request_with_retry(
    session: requests.Session,
    url: str,
    logger: logging.Logger,
    context: str,
    timeout: int = 20,
    max_retries: int = 2,
) -> tuple[requests.Response | None, bool]:
    for attempt in range(max_retries + 1):
        try:
            response = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            if attempt >= max_retries:
                logger.warning("%s request failed after retries: %s", context, exc)
                return None, False
            backoff = (2**attempt) * 2 + random.uniform(0.5, 1.5)
            _sleep_jitter(backoff, backoff + 0.5)
            continue
        if response.status_code in {403, 429}:
            logger.warning("%s request rate limited (%s)", context, response.status_code)
            _sleep_jitter(60, 120)
            return None, True
        if 500 <= response.status_code < 600:
            if attempt >= max_retries:
                return response, False
            backoff = (2**attempt) * 2 + random.uniform(0.5, 1.5)
            _sleep_jitter(backoff, backoff + 0.5)
            continue
        return response, False
    return None, False


def _fetch_workshop_image_url(
    session: requests.Session,
    logger: logging.Logger,
    workshop_url: str,
) -> tuple[str | None, bool]:
    response, throttled = _request_with_retry(
        session,
        workshop_url,
        logger,
        "Workshop page",
    )
    if throttled or not response or not response.ok:
        return None, throttled
    soup = BeautifulSoup(response.text, "html.parser")
    img = soup.find("img", class_=IMAGE_CLASS)
    if img and img.get("src"):
        return img["src"], False
    return None, False


def fetch_missing_images(settings: Settings, logger: logging.Logger, db: MySQLClient) -> None:
    static_map_dir = os.path.join(settings.project_root, settings.static_dir_name, "maps")
    ensure_dir(static_map_dir)
    ok_keys, bad_keys = _existing_images(static_map_dir)
    for key in bad_keys:
        bad_path = os.path.join(static_map_dir, f"{key}.jpg")
        try:
            os.remove(bad_path)
            logger.info("Removed junk workshop image %s", bad_path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning("Failed to remove junk workshop image %s: %s", bad_path, exc)

    maps = db.get_maps_for_images()
    logger.info("Checking workshop images for %s maps", len(maps))
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    window_start = time.monotonic()
    window_count = 0

    for entry in maps:
        map_key = (entry.get("map_key") or "").lower()
        if not map_key or map_key in ok_keys:
            continue
        workshop_id = entry.get("workshop_id")
        workshop_url = entry.get("workshop_url")
        if not workshop_url and workshop_id:
            workshop_url = f"{WORKSHOP_URL_PREFIX}{workshop_id}"
        if not workshop_url:
            continue

        image_url, throttled = _fetch_workshop_image_url(session, logger, workshop_url)
        if throttled:
            continue
        if not image_url:
            logger.warning("No workshop image found for %s", map_key)
            _sleep_jitter(6, 12)
            continue

        try:
            image_response, throttled = _request_with_retry(
                session,
                image_url,
                logger,
                f"Image for {map_key}",
            )
            if throttled:
                continue
            if not image_response or not image_response.ok:
                logger.warning("Failed to download image for %s", map_key)
                _sleep_jitter(6, 12)
                continue
            content_type = (image_response.headers.get("Content-Type") or "").lower()
            if "image/" not in content_type:
                logger.warning("Invalid content type for %s: %s", map_key, content_type)
                _sleep_jitter(6, 12)
                continue
            target_path = os.path.join(static_map_dir, f"{map_key}.jpg")
            tmp_path = f"{target_path}.tmp"
            try:
                with open(tmp_path, "wb") as handle:
                    handle.write(image_response.content)
                size = os.path.getsize(tmp_path)
                if size < MIN_IMAGE_BYTES:
                    logger.warning("Discarding small image for %s (%s bytes)", map_key, size)
                    _sleep_jitter(6, 12)
                    continue
                os.replace(tmp_path, target_path)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            ok_keys.add(map_key)
            logger.info("Saved workshop image for %s", map_key)
            window_count += 1
            if window_count >= MAX_IMAGES_PER_MINUTE:
                elapsed = time.monotonic() - window_start
                if elapsed < 60:
                    time.sleep(60 - elapsed)
                window_start = time.monotonic()
                window_count = 0
            _sleep_jitter(10, 14)
        except Exception as exc:
            logger.warning("Image download failed for %s: %s", map_key, exc)
            _sleep_jitter(6, 12)
