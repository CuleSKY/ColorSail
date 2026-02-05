#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
from collections import defaultdict, Counter

from bs4 import BeautifulSoup

# 地图名：ze_xxx / bhop_24 / surf_xxx ...
MAP_RE = re.compile(r"^[a-z0-9]+_[a-z0-9][a-z0-9_\-]*$", re.I)

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
    # 支持英文逗号/中文逗号
    parts = re.split(r"[,\uFF0C]", tag_cell)
    return [p.strip() for p in parts if p.strip()]

def workshop_id_from_url(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"(\d{8,})", url)
    return m.group(1) if m else ""

@dataclass
class MapEntry:
    map: str
    name_zh: str
    difficulty: str
    tags: List[str]
    cooldown: Dict[str, Any]     # { "duration_raw": "...", "deadline": "YYYY/.. or None" }
    achievement: str
    workshop: Dict[str, Any]     # { "id": "...", "url": "..." }

def parse_html_file(path: str) -> List[MapEntry]:
    html = open(path, "r", encoding="utf-8", errors="ignore").read()
    soup = BeautifulSoup(html, "html.parser")

    tbody = soup.select_one("tbody#data-tablebody")
    if not tbody:
        raise RuntimeError("找不到 tbody#data-tablebody。请确认下载的 HTML 是完整页面。")

    entries: List[MapEntry] = []
    for tr in tbody.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue

        map_name = norm(tds[0].get_text(" ", strip=True))
        if not map_name or not MAP_RE.match(map_name):
            continue  # 过滤异常行

        cn_name = norm(tds[1].get_text(" ", strip=True))
        difficulty = norm(tds[2].get_text(" ", strip=True)) or "未标注"
        tag_raw = norm(tds[3].get_text(" ", strip=True))
        tags = split_tags(tag_raw)

        cooldown_duration = norm(tds[4].get_text(" ", strip=True))

        # 冷却截止列：td.small 可能是 “无”
        deadline = norm(tds[5].get_text(" ", strip=True)) or None

        achievement = norm(tds[6].get_text(" ", strip=True))

        a = tds[7].find("a", href=True)
        wurl = norm(a["href"]) if a else ""
        wid = workshop_id_from_url(wurl) if wurl else ""

        entries.append(MapEntry(
            map=map_name,
            name_zh=cn_name,
            difficulty=difficulty,
            tags=tags,
            cooldown={"duration_raw": cooldown_duration, "deadline": deadline},
            achievement=achievement,
            workshop={"id": wid, "url": wurl}
        ))

    return entries

def write_outputs(entries: List[MapEntry], out_json: str, out_grouped: str, out_summary: str):
    # 1) 规范化列表 JSON
    data = [asdict(e) for e in entries]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 2) 归类：difficulty -> tag -> maps（多标签会重复出现）
    grouped = defaultdict(lambda: defaultdict(list))
    for e in entries:
        diff = e.difficulty or "未标注"
        tag_list = e.tags if e.tags else ["无标签"]
        for t in tag_list:
            grouped[diff][t].append(e.map)

    grouped_plain = {d: {t: sorted(set(maps)) for t, maps in tagmap.items()} for d, tagmap in grouped.items()}
    with open(out_grouped, "w", encoding="utf-8") as f:
        json.dump(grouped_plain, f, ensure_ascii=False, indent=2)

    # 3) summary
    diff_counter = Counter([e.difficulty for e in entries])
    tag_counter = Counter()
    for e in entries:
        for t in (e.tags if e.tags else ["无标签"]):
            tag_counter[t] += 1

    lines = []
    lines.append("# Maplist Summary\n\n")
    lines.append(f"- total: {len(entries)}\n\n")
    lines.append("## difficulty\n")
    for d, c in diff_counter.most_common():
        lines.append(f"- {d}: {c}\n")
    lines.append("\n## top tags\n")
    for t, c in tag_counter.most_common(30):
        lines.append(f"- {t}: {c}\n")

    with open(out_summary, "w", encoding="utf-8") as f:
        f.write("".join(lines))

def main():
    html_path = sys.argv[1] if len(sys.argv) > 1 else "cs2maplist.html"
    out_json = sys.argv[2] if len(sys.argv) > 2 else "maplist.normalized.json"
    out_grouped = sys.argv[3] if len(sys.argv) > 3 else "maplist.grouped.json"
    out_summary = sys.argv[4] if len(sys.argv) > 4 else "maplist.summary.md"

    entries = parse_html_file(html_path)
    if not entries:
        raise SystemExit("解析结果为 0：请确认 HTML 内含 tbody#data-tablebody 且其中有 tr/td 数据行。")

    write_outputs(entries, out_json, out_grouped, out_summary)

    print("Done.")
    print("-", out_json)
    print("-", out_grouped)
    print("-", out_summary)
    print("\nSanity (first 5):")
    for e in entries[:5]:
        print(e.map, "|", e.difficulty, "|", (",".join(e.tags) if e.tags else "无标签"), "|", e.cooldown["duration_raw"], "|", (e.cooldown["deadline"] or "无"), "|", (e.workshop["id"] or "-"))

if __name__ == "__main__":
    main()
