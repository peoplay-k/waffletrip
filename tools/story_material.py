#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘 쓸 기사거리를 묶어 낸다.

**남의 기사를 옮기는 것과 남의 기사를 바탕으로 쓰는 것은 다르다.**
사실에는 저작권이 없지만 남이 쓴 문장에는 있다. 그래서 이 도구는 문장을
넘기지 않고 **같은 사건을 쓴 매체들을 묶어서** 넘긴다. 다섯 곳이 같은 건을
쓰면 그건 실제로 일어난 일이고, 다섯 곳이 각각 무엇을 강조했는지가 곧
우리가 쓸 기사의 뼈대가 된다.

    python3 tools/story_material.py            # 오늘치
    python3 tools/story_material.py --days 2   # 이틀치에서 고른다
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import REGION_NAMES  # noqa: E402

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "story_material.md")
STOP = {"있다", "했다", "한다", "된다", "위해", "통해", "대한", "오는", "이번",
        "지난", "올해", "내년", "관련", "기자", "제공", "사진", "여행", "관광"}


# 사건·사고는 싣지 않는다(편집원칙 3항). 다만 태풍·정전·도로 통제처럼
# 여행자의 일정에 영향을 주는 것은 남긴다. 기존 `relevance.is_crime_report`
# 는 우리말만 보므로 영문 지역지 기사를 그대로 통과시켰다 —
# 2026-09-16 실측: 몬태나 교통사고와 와이키키 폭행이 괌·하와이 거리로 올라왔다.
_INCIDENT = re.compile(
    r"\b(dead|killed|injur\w*|crash|stabb\w*|shot|shooting|arrest\w*|"
    r"assault|robber\w*|homicide|lacerations|drug use|suspect\w*|"
    r"police|missing|fire\b|body found)\b", re.I)
_INCIDENT_KO = re.compile(
    r"(추락|사망|숨져|숨진|부상자|체포|구속|피살|폭행|살해|실종|자위대|"
    r"미사일|교전|시신|마약|음주운전|성추행|절도|강도)")
_TRAVEL_IMPACT = re.compile(
    r"\b(hurricane|typhoon|storm|flight|airport|airline|power restored|"
    r"reopen\w*|closure|closed|advisory|evacuat\w*|tsunami|volcano)\b", re.I)
_TRAVEL_IMPACT_KO = re.compile(
    r"(태풍|정전|결항|지연|운항|노선|공항 폐쇄|도로 통제|입국|비자|여권|"
    r"재개|복구|주의보|대피)")


def is_incident(title: str) -> bool:
    """사건·사고인가. 여행 일정에 영향을 주는 것은 사고여도 남긴다."""
    t = title or ""
    if _TRAVEL_IMPACT.search(t) or _TRAVEL_IMPACT_KO.search(t):
        return False
    return bool(_INCIDENT.search(t) or _INCIDENT_KO.search(t))


def is_korean_title(text: str) -> bool:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if "\uac00" <= c <= "\ud7a3") / len(letters) >= 0.4


def words(text: str) -> set[str]:
    t = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", text or "")
    return {w for w in t.split() if len(w) > 1 and w not in STOP}


def load(days: int) -> list[dict]:
    files = sorted(glob.glob(os.path.join("data", "items", "*.jsonl")))[-days:]
    out, seen = [], set()
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                out.append(row)
    return out


def cluster(items: list[dict]) -> list[list[dict]]:
    """제목이 겹치는 것끼리 묶는다. 같은 사건을 여러 곳이 쓴 것이다."""
    groups: list[list[dict]] = []
    for item in items:
        w = words(item.get("title"))
        if not w:
            continue
        for g in groups:
            base = words(g[0].get("title"))
            overlap = len(w & base) / max(1, min(len(w), len(base)))
            if overlap >= 0.45:
                g.append(item)
                break
        else:
            groups.append([item])
    return groups


def already_written(items: list[dict]) -> set[str]:
    """우리가 이미 쓴 해설의 낱말. 같은 걸 또 쓰지 않게 대조한다."""
    out: set[str] = set()
    for row in items:
        if row.get("grade") == "C" and row["id"].startswith("c-"):
            out |= words(row.get("title"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--per-region", type=int, default=3)
    args = ap.parse_args()

    items = load(args.days)
    mine = already_written(items)
    by_region: dict[str, list[dict]] = defaultdict(list)
    ent_rows: list[dict] = []
    for row in items:
        title = row.get("title") or ""
        if row.get("grade") != "B" or not title:
            continue
        if is_incident(title):
            continue                      # 사건·사고는 싣지 않는다
        if row.get("channel") == "ent":
            ent_rows.append(row)          # 연예는 지역이 없다. 따로 묶는다
            continue
        by_region[row.get("region", "")].append(row)

    today = datetime.now(KST).strftime("%Y-%m-%d")
    lines = [f"# 오늘 쓸 기사거리 ({today})", "",
             "여러 매체가 같은 건을 쓴 것부터 놓았다. **문장을 옮기지 말고**",
             "사실만 가져다 우리 문장으로 쓴다. 인용한 매체는 본문에 밝힌다.", ""]
    total = 0
    for region in REGION_NAMES:
        rows = by_region.get(region) or []
        if not rows:
            continue
        groups = cluster(rows)
        # 고르는 순서 — 우리말 제목 먼저, 그다음 여러 곳이 쓴 것, 그다음 최신.
        #
        # 우리말 제목을 앞에 두는 이유: 한국 여행 매체가 그 목적지를 다뤘다는
        # 것 자체가 우리 독자와 맞닿았다는 뜻이다. 영문 지역지는 그 지역
        # 주민을 위한 기사가 대부분이라 재료로서 값이 떨어진다.
        groups.sort(key=lambda g: (
            0 if any(is_korean_title(i.get("title")) for i in g) else 1,
            -len(g),
            -max((i.get("published_at") or "") for i in g).__hash__()))
        # 이미 우리가 쓴 것과 겹치면 뺀다. 같은 걸 또 쓰는 것이 가장 나쁘다.
        groups = [g for g in groups
                  if not (len(g) == 1 and len(words(g[0]["title"]) & mine) >= 3)]
        # 영문 단독 기사는 재료로 쓰지 않는다. 여러 곳이 쓴 것이면 남긴다.
        groups = [g for g in groups
                  if len(g) > 1 or any(is_korean_title(i.get("title")) for i in g)]
        picked = groups[:args.per_region]
        if not picked:
            continue
        lines.append(f"## {REGION_NAMES[region]}")
        lines.append("")
        for g in picked:
            total += 1
            outlets = sorted({(i.get("source_name") or "").strip()
                              for i in g if i.get("source_name")})
            lines.append(f"### {g[0]['title']}")
            lines.append(f"- 매체 {len(outlets)}곳 · {' · '.join(outlets) or '미상'}"
                         f"{'  ← 여러 곳이 썼다' if len(g) > 1 else ''}")
            for i in g[:4]:
                summ = re.sub(r"\s+", " ", (i.get("summary") or "")).strip()
                lines.append(f"  - {i.get('source_name', '?')}: {summ[:160]}")
                if i.get("source_url"):
                    lines.append(f"    {i['source_url']}")
            lines.append("")
    # 연예 거리. 지역이 없으므로 한 절에 모은다. 여기 있는 것은 **편집실에서 사람이
    # 쓴다** — 예약 해설 에이전트는 연예 기사를 쓰지 않는다(DAILY_COMMENTARY.md).
    # 가십은 edit 단계에서 이미 걸렀지만, 보도자료성 발표만 재료로 삼는다.
    if ent_rows:
        groups = cluster(ent_rows)
        groups.sort(key=lambda g: (-len(g),
                                   -max((i.get("published_at") or "") for i in g).__hash__()))
        picked = groups[:args.per_region * 2]
        if picked:
            lines.append("## 연예 (편집실이 쓴다 — 자동 해설 대상 아님)")
            lines.append("")
            for g in picked:
                total += 1
                outlets = sorted({(i.get("source_name") or "").strip()
                                  for i in g if i.get("source_name")})
                cat = g[0].get("category") or "star"
                lines.append(f"### [{cat}] {g[0]['title']}")
                lines.append(f"- 매체 {len(outlets)}곳 · {' · '.join(outlets) or '미상'}"
                             f"{'  ← 여러 곳이 썼다' if len(g) > 1 else ''}")
                for i in g[:4]:
                    summ = re.sub(r"\s+", " ", (i.get("summary") or "")).strip()
                    lines.append(f"  - {i.get('source_name', '?')}: {summ[:160]}")
                    if i.get("source_url"):
                        lines.append(f"    {i['source_url']}")
                lines.append("")
    lines.append(f"---\n거리 {total}건. 쓸 만한 것만 고른다 — 억지로 채우지 않는다.")

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"기사거리 {total}건 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
