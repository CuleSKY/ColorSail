import json
import os
import tempfile
from typing import Any

from .utils import ensure_dir


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
