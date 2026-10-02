#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기사 내역 — 월별로 몇 편을, 누가, 어떤 종류로 냈는지.

2026-10-01 편집국장: "몇 월부터 몇 월까지 내역을 달라." 네이버 제휴 심사는 자체 기사
(취재·기획·인터뷰) 비중을 본다 — 50~70%, 적어도 50%. 그 비중을 매달 눈으로 보려고 만든다.

    python3 tools/article_ledger.py                       이번 달
    python3 tools/article_ledger.py --from 2026-09 --to 2026-10
    python3 tools/article_ledger.py --from 2026-10 --csv 내역.csv

세는 것은 **지면에 실제로 나간 우리 기사(C등급)** 다. data/items/*.jsonl 이 정본이다 —
초안 파일(content/review)은 종류(kind)를 읽으려고만 본다. 인용(B)·환율·날씨(A)는 세지 않는다.
종류가 적히지 않은 기사는 '미분류'로 센다. 자체 기사로 치지 않는다 — 부풀리지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

from src.desks import OWN_KINDS, byline_for  # noqa: E402
from src.models import item_from_dict  # noqa: E402

KST = timezone(timedelta(hours=9))
AUTO = "자동"          # 오늘의 데이터 기사·주간 소식 묶음 — 사람도 AI 해설도 아니다
UNSET = "미분류"


def kinds_by_published_id(review_dir: str) -> dict[str, str]:
    """발행된 초안의 id → 종류."""
    out: dict[str, str] = {}
    for path in glob.glob(os.path.join(review_dir, "*.md")):
        try:
            raw = open(path, encoding="utf-8").read()
            front = yaml.safe_load(raw.split("---", 2)[1]) if raw.startswith("---") else {}
        except Exception:
            continue
        pid = (front or {}).get("published_id")
        if pid:
            out[str(pid)] = str(front.get("kind") or UNSET)
    return out


def kind_of(item, kinds: dict[str, str]) -> str:
    if item.id in kinds:
        return kinds[item.id]
    # 옛 제호(와플트립) 시절 데이터 기사도 데이터팀으로 적혀 있다
    if (item.source_name or "").endswith("데이터팀") or item.title.startswith("이번 주 "):
        return AUTO
    return UNSET


def load_articles(data_dir: str, review_dir: str, start: str, end: str) -> list[dict]:
    """[start, end] 달(YYYY-MM)에 나간 우리 기사. 같은 id 는 한 번만."""
    kinds = kinds_by_published_id(review_dir)
    seen: set[str] = set()
    rows: list[dict] = []
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl"))):
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            item = item_from_dict(json.loads(line))
            month = (item.published_at or "")[:7]
            if item.grade != "C" or item.id in seen or not (start <= month <= end):
                continue
            seen.add(item.id)
            from src.render.site import article_url
            rows.append({"date": item.published_at[:10], "month": month,
                         "byline": byline_for(item), "kind": kind_of(item, kinds),
                         "channel": getattr(item, "channel", "travel"),
                         "title": item.title, "url": article_url(item)})
    rows.sort(key=lambda r: r["date"])
    return rows


def report(rows: list[dict]) -> str:
    by_month: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_month[r["month"]].append(r)
    out = ["# 기사 내역", "",
           "자체 기사 = 취재·기획·인터뷰. 해설·보도자료·자동·미분류는 자체로 세지 않는다.", "",
           "| 월 | 전체 | 자체 | 해설 | 보도자료 | 자동 | 미분류 | 자체 비율 |",
           "|---|---|---|---|---|---|---|---|"]
    for month in sorted(by_month):
        c = Counter(r["kind"] for r in by_month[month])
        total = sum(c.values())
        own = sum(c[k] for k in OWN_KINDS)
        out.append(f"| {month} | {total} | {own} | {c['해설']} | {c['보도자료']} | "
                   f"{c[AUTO]} | {c[UNSET]} | {own / total * 100:.0f}% |" if total else "")
    out += ["", "## 기자별", ""]
    for month in sorted(by_month):
        c = Counter(r["byline"] for r in by_month[month])
        out.append(f"- **{month}** · " + " · ".join(f"{k} {v}" for k, v in c.most_common()))
    return "\n".join(out) + "\n"


def main() -> int:
    this_month = datetime.now(KST).strftime("%Y-%m")
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default=this_month)
    ap.add_argument("--to", dest="end", default=this_month)
    ap.add_argument("--csv", default="", help="기사 한 줄씩 CSV 로도 남긴다")
    args = ap.parse_args()
    rows = load_articles(os.path.join(ROOT, "data"), os.path.join(ROOT, "content", "review"),
                         args.start, args.end)
    print(report(rows))
    if args.csv:
        with open(args.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["date", "byline", "kind", "channel", "title", "url"],
                               extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"CSV {len(rows)}줄 → {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
