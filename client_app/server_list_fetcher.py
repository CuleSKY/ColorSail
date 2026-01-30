"""Polling utilities for CS2ZE server lists.

These modules are scaffolding only and are not imported by the web server.
"""
from __future__ import annotations

import json
import random
import time
import urllib.request
import urllib.error
import gzip
from typing import Callable, Dict, Optional, Tuple

DEFAULT_GLOBAL_URL = "https://www.cs2ze.org/servers.json"
SERVER_LIST_URLS = [DEFAULT_GLOBAL_URL]

_ETAG_CACHE: Dict[str, str] = {}


def _read_response_body(resp) -> bytes:
    raw = resp.read()
    encoding = resp.headers.get("Content-Encoding", "").lower()
    if encoding == "gzip":
        return gzip.decompress(raw)
    return raw


def fetch_once(url: str) -> Tuple[Optional[dict], Optional[str], bool]:
    """Fetch a single server list snapshot.

    Returns (data_json, etag, not_modified).
    """
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "cs2ze-client-scaffold/0.1",
    }
    etag = _ETAG_CACHE.get(url)
    if etag:
        headers["If-None-Match"] = etag

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status == 304:
                return None, etag, True
            body = _read_response_body(resp)
            data = json.loads(body.decode("utf-8")) if body else None
            new_etag = resp.headers.get("ETag") or etag
            if new_etag:
                _ETAG_CACHE[url] = new_etag
            return data, new_etag, False
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return None, etag, True
        raise


def poll_loop(callback_on_update: Callable[[str, dict], None], foreground: bool = True) -> None:
    """Continuously poll configured server list URLs and invoke the callback on updates."""
    rng = random.Random()
    while True:
        for url in SERVER_LIST_URLS:
            data, _, not_modified = fetch_once(url)
            if data is not None and not not_modified:
                callback_on_update(url, data)
        interval = rng.uniform(6, 10) if foreground else rng.uniform(15, 20)
        time.sleep(interval)


def test_poll_intervals(seed: int = 0, foreground: bool = True, iterations: int = 5) -> list[float]:
    """Deterministic harness for validating polling interval jitter without network calls."""
    rng = random.Random(seed)
    intervals = []
    for _ in range(iterations):
        interval = rng.uniform(6, 10) if foreground else rng.uniform(15, 20)
        intervals.append(round(interval, 3))
    return intervals
