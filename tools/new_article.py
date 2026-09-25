#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기사 초안을 만든다. 대표님은 본문만 채우면 된다.

YAML 을 직접 만지지 않게 하려는 도구다. 지역·부문·서명·날짜는 이 도구가
채우고, 사람은 제목과 본문만 쓴다.

    python3 tools/new_article.py guam "괌 PIC 리조트 실측 기록"
    python3 tools/new_article.py ent "영화 ○○ 제작발표회" --category=movie
    python3 tools/new_article.py ent "배우 ○○, 괌 화보 촬영지" --category=startrip
    python3 tools/new_article.py ent "현장" --field   국장 현장 소스(사진 2~3장 + 메모) 양식
    python3 tools/new_article.py --list          지역·부문 목록
    python3 tools/new_article.py --queue         지금 검수 대기 중인 초안

첫 인자가 `ent` 면 연예 기사다 — 지역면이 아니라 /ent/<부문>/ 에 실린다.

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
           "laos": "라오스", "jeju": "제주", "japan": "일본",
           "thailand": "태국", "taiwan": "대만"}
SECTIONS = {"news": "일반 소식·해설", "flight": "항공·노선",
            "data": "데이터·통계", "promo": "안내"}
# 연예 부문. src/topics.py ENT_TOPICS 와 같다.
CATEGORIES = {"movie": "영화", "drama": "드라마·방송", "music": "음악·공연",
              "star": "인물", "startrip": "스타의 여행 (촬영지·스타가 간 곳)"}

# 연예 기사 양식. 보도자료와 현장으로만 쓴다 — 루머·사생활은 편집원칙이 금한다.
TEMPLATE_ENT = """## 무엇이 있었나

<!-- 첫 문단에 사실을 놓는다. 누가·무엇을·언제·어디서. 소속사·배급사·제작사의
     공식 발표나 우리가 간 현장에서 확인한 것만. 열애설·불화설·추측은 쓰지 않는다. -->

## 현장

<!-- 우리가 갔다면 본 것. 안 갔다면 이 절은 지운다. 남의 현장 사진은 쓰지 않는다. -->

## 여행과 닿는 자리

<!-- 촬영지·공연 도시·이동 일정처럼 여행 채널과 이어지는 사실이 있으면 여기.
     우리 지역면 링크는 내부 경로로 — [괌 지역면](/guam/). 상품 링크는 넣지 않는다. -->

## 알아둘 점

<!-- 독자가 실제로 해야 할 일 — 개봉일, 예매 시작, 공연 일정. -->

**출처** · (보도자료를 낸 곳과 날짜, 또는 "현장 취재")
"""

# 국장 현장 소스 양식. "행사 사진 2~3장 + 내용 → 우리가 기사화. 가공할 필요 없이
# 다른 각도 사진째로."(2026-09-16 편집국장 01:07:22). 받은 그대로 적고 당일 낸다.
TEMPLATE_FIELD = """## 현장

<!-- 국장이 보낸 메모를 사실 단위로 옮긴다. 행사명·주최·장소·일시·참석·발표 내용.
     연합뉴스보다 빨리 — 받은 날 낸다. -->

## 사진

<!-- 받은 사진의 파일명과 촬영자·촬영 시각을 적는다. 반입은 photo_prepare 로 한다.
     얼굴이 식별되는 컷은 동의 없이는 쓰지 않는다. -->

## 알아둘 점

**출처** · 현장 취재 (제공: )
"""

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


def create(region: str, title: str, section: str = "news",
           category: str = "", field: bool = False) -> str:
    ent = region == "ent"
    if not ent and region not in REGIONS:
        raise SystemExit(f"모르는 지역: {region}\n가능: ent, {', '.join(REGIONS)}")
    if section not in SECTIONS:
        raise SystemExit(f"모르는 부문: {section}\n가능: {', '.join(SECTIONS)}")
    if category and category not in CATEGORIES:
        raise SystemExit(f"모르는 연예 부문: {category}\n가능: {', '.join(CATEGORIES)}")

    day = datetime.now(KST).date().isoformat()
    os.makedirs(REVIEW, exist_ok=True)
    path = os.path.join(REVIEW, slugify(title, day) + ".md")
    if os.path.exists(path):
        raise SystemExit(f"같은 이름의 초안이 이미 있다: {path}")

    key = f"ent-{category or 'star'}" if ent else region
    front = {
        "id": f"art-{key}-{day.replace('-', '')}",
        "channel": "ent" if ent else "travel",
        "region": "" if ent else region,
        "category": (category or "") if ent else "",
        "section": section,
        "title": title,
        # 비워두면 데스크 이름이 자동으로 붙는다(여행은 지역 데스크, 연예는 문화부).
        # 실제 필자가 있으면 그 이름을 적는다.
        "source_name": "",
        "source_url": "",
        "summary": "",
        "status": "draft",
    }
    body = TEMPLATE_FIELD if field else (TEMPLATE_ENT if ent else TEMPLATE)
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n\n" + body)
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
        where = (f"ent/{front.get('category') or 'star'}"
                 if front.get("channel") == "ent" else front.get("region", "?"))
        rows.append((front.get("status", "?"), where,
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
        print("지역 (여행 채널)")
        for k, v in REGIONS.items():
            print(f"  {k:9} {v}")
        print("\n연예 채널 — 첫 인자를 ent 로, 부문은 --category=")
        for k, v in CATEGORIES.items():
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

    section, category = "news", ""
    for a in argv:
        if a.startswith("--section="):
            section = a.split("=", 1)[1]
        if a.startswith("--category="):
            category = a.split("=", 1)[1]

    path = create(args[0], " ".join(args[1:]), section, category,
                  field="--field" in argv)
    print(f"만들었다: {os.path.relpath(path, ROOT)}")
    print("\n다음")
    print("  1. 본문을 채운다")
    print("  2. status 를 approved 로 바꾼다")
    print("  3. 커밋·푸시하면 다음 발행 때 지면에 나간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
