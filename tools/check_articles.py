#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘 쓴 해설이 약속대로 됐는지 본다.

2026-10-21 부터 출처는 지면에 안 나간다(사장님). 대신 앞머리 sources: 에 참고한
원문 주소가 남아 있는지, 길이가 맞는지, 본문에 매체 이름이 없는지, 신문 기사 형식(문단만,
소제목·목록·표·"알아둘 점" 없음 — 2026-10-28 사장님)을 지켰는지 본다.

    python3 tools/check_articles.py            # 오늘치
    python3 tools/check_articles.py --day 20260916
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.attribution import find_media_attribution, media_names  # noqa: E402
from src.article_format import format_problems  # noqa: E402

KST = timezone(timedelta(hours=9))
MIN_CHARS = 900          # 이보다 짧으면 재료가 얇았다는 뜻이다


def check(day: str) -> int:
    paths = sorted(glob.glob(os.path.join("content", "review", f"{day}*.md")))
    if not paths:
        print(f"{day} 초안이 없다.")
        return 0
    bad = 0
    for path in paths:
        text = open(path, encoding="utf-8").read()
        body = text.split("---", 2)[-1].strip()
        title = re.search(r"^title:\s*(.+)", text, re.M)
        name = (title.group(1).strip().strip("'\"") if title else os.path.basename(path))
        외부 = re.findall(r"\]\((https?://[^)]+)\)", body)
        # 연예·현장 취재 기사는 원문이 우리 자신이다. 보도자료를 정리했으면 링크가
        # 있어야 하지만 "현장 취재"라고 밝힌 글에는 링크를 요구하지 않는다.
        연예 = re.search(r"^channel:\s*ent\s*$", text, re.M) is not None
        현장 = "현장 취재" in body
        문제 = []
        # 2026-10-21: 출처는 지면에 안 나간다. 대신 앞머리 sources: 에 근거 주소가 있어야 한다.
        근거 = re.search(r"^sources:\s*\n(\s+-\s+https?://\S+\s*\n?)+", text, re.M)
        if not 근거 and not (연예 and 현장):
            문제.append("근거 주소(sources:) 없음")
        # 2026-10-28: 신문 기사 형식(문단만). 길이도 여기서 본다. 방송 회차 기사는 따로 정한 형식.
        방송 = re.search(r"^category:\s*tv\s*$", text, re.M) is not None
        기획 = "[기획]" in name
        if 방송 and len(body) < MIN_CHARS:
            문제.append(f"{len(body)}자")
        문제 += format_problems(body, tv=방송, feature=기획)
        # 본문에 매체 인용 금지(2026-10-19). 발행 단계가 이런 원고는 내보내지 않는다.
        인용 = find_media_attribution(body, media_names(body))
        if 인용:
            문제.append(f"매체 인용 {len(인용)}곳 — 예: {인용[0][:50]}")
        if 문제:
            bad += 1
            print(f"  ✗ {name[:44]} — {' · '.join(문제)}")
        else:
            print(f"  ✓ {name[:44]} — {len(body)}자")
    print(f"\n{len(paths)}편 중 {bad}편에 문제.")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=datetime.now(KST).strftime("%Y%m%d"))
    ap.add_argument("--strict", action="store_true", help="문제가 있으면 실패로 끝낸다")
    args = ap.parse_args()
    rc = check(args.day)
    return rc if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
