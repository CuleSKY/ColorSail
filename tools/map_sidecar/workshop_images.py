from __future__ import annotations

import logging
import os
import requests
from bs4 import BeautifulSoup

from tools.map_sidecar.config import Settings
from tools.map_sidecar.db import MySQLClient
from tools.map_sidecar.utils import ensure_dir

IMAGE_CLASS = "workshopItemPreviewImageEnlargeable"
USER_AGENT = "cs2ze-map-sidecar/1.0"


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
