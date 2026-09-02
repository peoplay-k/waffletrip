#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기사 초안을 만든다. 대표님은 본문만 채우면 된다.

YAML 을 직접 만지지 않게 하려는 도구다. 지역·부문·서명·날짜는 이 도구가
채우고, 사람은 제목과 본문만 쓴다.

    python3 tools/new_article.py guam "괌 PIC 리조트 실측 기록"
    python3 tools/new_article.py --list          지역·부문 목록
    python3 tools/new_article.py --queue         지금 검수 대기 중인 초안

만든 파일은 content/review/ 에 들어간다. 본문을 채우고 status 를 approved 로
바꾸면 다음 발행 때 지면에 나간다. GitHub 웹에서 직접 고쳐도 된다.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(ROOT, "content/review")
KST = timezone(timedelta(hours=9))

REGIONS = {"guam": "괌", "saipan": "사이판", "hawaii": "하와이",
           "vietnam": "베트남", "kota": "코타키나발루",
           "laos": "라오스", "jeju": "제주"}
SECTIONS = {"news": "일반 소식·해설", "flight": "항공·노선",
            "data": "데이터·통계", "promo": "안내"}

TEMPLATE = """## 무엇을 확인했나

<!-- 첫 문단에 이 기사에만 있는 사실을 놓는다. 언제 갔고 무엇을 쟀는지.
     웹에서 찾을 수 있는 설명은 여기 오지 않는다. -->

## 실측

<!-- 표는 이 신문의 핵심 포맷이다. 문장으로 풀지 말고 숫자로 놓는다.
     공개하는 가격은 소비자가와 실제 결제가뿐이다. -->

| 항목 | 값 | 확인일 |
|---|---|---|
|  |  |  |

## 정리

<!-- 직접 겪은 것만 적는다. 일반론은 쓰지 않는다. -->
"""


def slugify(title: str, day: str) -> str:
    s = re.sub(r"[^\w가-힣\s-]", "", title).strip()
    s = re.sub(r"\s+", "-", s)[:40].strip("-")
    return f"{day.replace('-', '')}_{s or 'article'}"


def create(region: str, title: str, section: str = "news") -> str:
    if region not in REGIONS:
        raise SystemExit(f"모르는 지역: {region}\n가능: {', '.join(REGIONS)}")
    if section not in SECTIONS:
        raise SystemExit(f"모르는 부문: {section}\n가능: {', '.join(SECTIONS)}")

    day = datetime.now(KST).date().isoformat()
    os.makedirs(REVIEW, exist_ok=True)
    path = os.path.join(REVIEW, slugify(title, day) + ".md")
    if os.path.exists(path):
        raise SystemExit(f"같은 이름의 초안이 이미 있다: {path}")

    front = {
        "id": f"art-{region}-{day.replace('-', '')}",
        "region": region,
        "section": section,
        "title": title,
        # 비워두면 지역 데스크 이름이 자동으로 붙는다.
        # 실제 필자가 있으면 그 이름을 적는다.
        "source_name": "",
        "source_url": "",
        "summary": "",
        "status": "draft",
    }
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n\n" + TEMPLATE)
    return path


def queue() -> None:
    if not os.path.isdir(REVIEW):
        print("검수 대기 초안이 없다.")
        return
    rows = []
    for name in sorted(os.listdir(REVIEW)):
        if not name.endswith(".md"):
            continue
        try:
            with open(os.path.join(REVIEW, name), encoding="utf-8") as f:
                front = yaml.safe_load(f.read().split("---")[1]) or {}
        except Exception:
            continue
        rows.append((front.get("status", "?"), front.get("region", "?"),
                     front.get("title", name)[:44], name))
    if not rows:
        print("검수 대기 초안이 없다.")
        return
    order = {"draft": 0, "approved": 1, "published": 2}
    print(f"{'상태':<10}{'지역':<8}제목")
    print("─" * 70)
    for st, rg, ti, _ in sorted(rows, key=lambda r: (order.get(r[0], 9), r[1])):
        label = {"draft": "작성중", "approved": "발행대기", "published": "발행됨"}.get(st, st)
        pad = 10 - sum(1 for c in label if ord(c) > 0x2E80)
        print(f"{label:<{pad}}{REGIONS.get(rg, rg):<8}{ti}")


def main(argv) -> int:
    if "--list" in argv:
        print("지역")
        for k, v in REGIONS.items():
            print(f"  {k:9} {v}")
        print("\n부문")
        for k, v in SECTIONS.items():
            print(f"  {k:9} {v}")
        return 0
    if "--queue" in argv:
        queue()
        return 0

    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        print(__doc__.strip())
        return 1

    section = "news"
    for a in argv:
        if a.startswith("--section="):
            section = a.split("=", 1)[1]

    path = create(args[0], " ".join(args[1:]), section)
    print(f"만들었다: {os.path.relpath(path, ROOT)}")
    print("\n다음")
    print("  1. 본문을 채운다")
    print("  2. status 를 approved 로 바꾼다")
    print("  3. 커밋·푸시하면 다음 발행 때 지면에 나간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
