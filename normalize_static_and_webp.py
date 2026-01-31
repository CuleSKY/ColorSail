#!/usr/bin/env python3
import os
import re
import json
import argparse
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif"}
KEEP_EXTS = {".svg", ".ico", ".webp"}  # 不自动转这些（svg/ico通常另管，webp已是目标）

def slugify_filename(name: str) -> str:
    """
    规范化文件名（不含路径）：
    - 小写
    - 空格/下划线 -> '-'
    - 仅保留 [a-z0-9.-]
    - 连续 '-' 合并，去除首尾 '-'
    """
    name = name.strip().lower()
    # 分离扩展名
    stem, dot, ext = name.rpartition(".")
    if dot == "":
        stem, ext = name, ""
    else:
        ext = "." + ext

    stem = stem.replace("_", "-")
    stem = re.sub(r"\s+", "-", stem)
    stem = re.sub(r"[^a-z0-9.-]+", "-", stem)
    stem = re.sub(r"-{2,}", "-", stem).strip("-")

    # 防止空名
    if not stem:
        stem = "file"

    # 扩展名也小写
    ext = ext.lower()
    return stem + ext

def unique_path(path: Path) -> Path:
    """如果目标已存在，自动追加 -2, -3..."""
    if not path.exists():
        return path
    base = path.stem
    ext = path.suffix
    parent = path.parent
    i = 2
    while True:
        cand = parent / f"{base}-{i}{ext}"
        if not cand.exists():
            return cand
        i += 1

def convert_to_webp(src: Path, dst: Path, *, quality: int, effort: int, lossless: bool) -> None:
    """
    转 WebP：
    - PNG/带 alpha：lossless=True 时保持透明且无损
    - JPG：lossless=False, quality=90-95 一般很稳
    """
    with Image.open(src) as im:
        # 纠正 EXIF 方向（手机拍照常见）
        im = ImageOps.exif_transpose(im)

        # GIF 可能是动图：这里默认只取首帧（如果你需要动图 webp，可再扩展）
        if getattr(im, "is_animated", False):
            im.seek(0)

        # 统一处理 alpha
        has_alpha = ("A" in im.getbands())

        save_kwargs = {
            "format": "WEBP",
            "method": effort,   # 0-6 (Pillow), 越大压缩越好但慢
        }

        if lossless:
            save_kwargs["lossless"] = True
            # lossless 下 quality 参数没意义，但 Pillow 有时会接受；这里不传
        else:
            save_kwargs["quality"] = quality

        # 对没有 alpha 的图片，RGB 保存即可
        if has_alpha:
            im = im.convert("RGBA")
        else:
            im = im.convert("RGB")

        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, **save_kwargs)

def main():
    ap = argparse.ArgumentParser(description="Normalize static filenames and convert images to WebP.")
    ap.add_argument("static_dir", help="Path to static directory, e.g. ./static")
    ap.add_argument("--dry-run", action="store_true", help="Only print actions, do not modify files.")
    ap.add_argument("--quality", type=int, default=92, help="Quality for lossy WebP (JPG etc.). 0-100.")
    ap.add_argument("--effort", type=int, default=6, help="Compression effort/method for WebP. 0-6 (Pillow).")
    ap.add_argument("--no-convert", action="store_true", help="Only rename files, do not convert to WebP.")
    ap.add_argument("--keep-originals", action="store_true",
                    help="Keep original images even after conversion (default: keep; this flag is for clarity).")
    ap.add_argument("--write-map", default="static_rename_map.json", help="Write rename map JSON to this file.")
    args = ap.parse_args()

    static_dir = Path(args.static_dir).resolve()
    if not static_dir.exists() or not static_dir.is_dir():
        raise SystemExit(f"Not a directory: {static_dir}")

    rename_map = {}   # old_rel -> new_rel
    webp_map = {}     # new_rel(original) -> webp_rel

    # 1) 先收集所有文件（避免 rename 时递归混乱）
    files = [p for p in static_dir.rglob("*") if p.is_file()]

    # 2) 先做 rename（只改文件名，不改目录名；目录名若也要规范可再加）
    for src in files:
        rel = src.relative_to(static_dir)
        new_name = slugify_filename(src.name)
        if new_name == src.name:
            continue

        dst = unique_path(src.with_name(new_name))
        if args.dry_run:
            print(f"[RENAME] {rel} -> {dst.relative_to(static_dir)}")
        else:
            src.rename(dst)
        rename_map[str(rel).replace("\\", "/")] = str(dst.relative_to(static_dir)).replace("\\", "/")

    # 重新扫描（因为已 rename）
    files = [p for p in static_dir.rglob("*") if p.is_file()]

    # 3) 转 webp（默认不删原文件，安全）
    if not args.no_convert:
        for src in files:
            ext = src.suffix.lower()
            if ext in KEEP_EXTS:
                continue
            if ext not in IMAGE_EXTS:
                continue

            rel = src.relative_to(static_dir)
            # 输出 webp 放在同目录同名 .webp
            dst = src.with_suffix(".webp")
            dst = unique_path(dst)

            # 决策：PNG/带透明 -> lossless；JPG -> lossy
            # 对 PNG：即使无透明也用 lossless 更接近“无损”，但可能变大；按你要求优先“无损”
            lossless = (ext == ".png")

            if args.dry_run:
                mode = "LOSSLESS" if lossless else f"LOSSY q={args.quality}"
                print(f"[WEBP] {rel} -> {dst.relative_to(static_dir)} ({mode})")
            else:
                convert_to_webp(
                    src, dst,
                    quality=args.quality,
                    effort=args.effort,
                    lossless=lossless,
                )
            webp_map[str(rel).replace("\\", "/")] = str(dst.relative_to(static_dir)).replace("\\", "/")

    # 4) 写映射表，方便你批量替换前端引用
    out = {
        "static_dir": str(static_dir),
        "renames": rename_map,
        "webp": webp_map,
    }
    if args.dry_run:
        print("[INFO] dry-run: not writing map file.")
    else:
        map_path = Path(args.write_map).resolve()
        map_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Wrote map: {map_path}")

if __name__ == "__main__":
    main()
