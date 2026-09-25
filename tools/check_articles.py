#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘 쓴 해설이 약속대로 됐는지 본다.

편집원칙에 "원문 링크까지 싣는다"고 적어 두었다. 적어만 두고 안 하면
그게 제일 나쁘다 — 2026-09-16 실측: 그날 여섯 편 전부 외부 링크가 0개였다.

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
        if not 외부 and not (연예 and 현장):
            문제.append("원문 링크 없음")
        if len(body) < MIN_CHARS:
            문제.append(f"{len(body)}자")
        if 문제:
            bad += 1
            print(f"  ✗ {name[:44]} — {' · '.join(문제)}")
        else:
            print(f"  ✓ {name[:44]} — {len(body)}자 · 링크 {len(외부)}")
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
