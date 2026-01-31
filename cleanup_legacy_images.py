#!/usr/bin/env python3
from pathlib import Path
import argparse

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
KEEP_NAMES = {
    "favicon.ico",
}

def main():
    ap = argparse.ArgumentParser(description="Remove legacy images replaced by WebP.")
    ap.add_argument("static_dir", help="Path to static directory")
    ap.add_argument("--dry-run", action="store_true", help="Only print files to be removed")
    args = ap.parse_args()

    static_dir = Path(args.static_dir).resolve()
    if not static_dir.is_dir():
        raise SystemExit("static_dir not found")

    removed = []

    for src in static_dir.rglob("*"):
        if not src.is_file():
            continue

        if src.name in KEEP_NAMES:
            continue

        if src.suffix.lower() not in IMAGE_EXTS:
            continue

        webp = src.with_suffix(".webp")
        if not webp.exists():
            continue  # 没有 webp，不删

        if args.dry_run:
            print(f"[DELETE] {src.relative_to(static_dir)}")
        else:
            src.unlink()
            removed.append(str(src.relative_to(static_dir)))

    if not args.dry_run:
        print(f"[OK] Removed {len(removed)} legacy files")

if __name__ == "__main__":
    main()
