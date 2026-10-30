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

# 지역·문화 부문은 config/site.json(편집실이 고치는 정본)에서 읽는다.
sys.path.insert(0, ROOT)
from src import site_config as _sc  # noqa: E402
REGIONS = {r["id"]: r["name"] for r in _sc.CONFIG["regions"] if r.get("visible", True)}
SECTIONS = {"news": "일반 소식·해설", "flight": "항공·노선",
            "data": "데이터·통계", "promo": "안내"}
CATEGORIES = {tid: name for tid, name, _ in _sc.culture_sections(_sc.CONFIG)}
# 옛 id 도 받는다 — 발행 경로가 새 부문으로 붙인다
CATEGORIES.update({old: f"(옛) {old} → {CATEGORIES.get(new, new)}"
                   for old, new in (_sc.CONFIG.get("culture_aliases") or {}).items()})

# 연예 기사 양식. 보도자료와 현장으로만 쓴다 — 루머·사생활은 편집원칙이 금한다.
# 기사 양식 — 신문 기사(2026-10-28 사장님 기준: 퍼블릭뉴스통신 「올마이투어, 메이크마이트립과
# 한국 숙박 상품 공급 계약 체결」). 소제목·목록·표·'알아둘 점' 없이 문단만. 주석은 지우고 쓴다.
_PARAGRAPHS = """<!-- 1. 요약 문단: 기사 전체를 두 문장으로. 무엇을 하는지와 그 결과를 현재형으로. -->

<!-- 2. 발표 문단: "○○는 N일 …했다고 밝혔다." + 배경 숫자(공식 기관을 밝혀서). -->

<!-- 3. 세부 문단 서너 개: 한 문단에 한 가지(내용·운영·고객이 할 수 있는 것·계획). 2~3문장씩. -->

<!-- 4. 관계자 말: 발표 주체가 공식 발표에서 한 말이 있을 때만 그대로. 상대 → 우리 쪽 대표 순서.
     없으면 지우고 3번의 계획 문단으로 끝낸다. 지어내지 않는다. -->
"""

TEMPLATE_ENT = """<!-- 연예: 소속사·배급사·제작사의 공식 발표나 우리가 간 현장에서 확인한 것만.
     열애설·불화설·추측은 쓰지 않는다. 남의 현장 사진은 쓰지 않는다. -->

""" + _PARAGRAPHS

# 국장 현장 소스 양식. "행사 사진 2~3장 + 내용 → 우리가 기사화."(2026-09-16 편집국장 01:07:22).
# 받은 그대로 사실 단위로 옮기고 당일 낸다. 사진 반입은 photo_prepare 로, 얼굴은 동의 없이 쓰지 않는다.
TEMPLATE_FIELD = """<!-- 현장: 행사명·주최·장소·일시·참석·발표 내용. 받은 날 낸다.
     사진 파일명·촬영자·촬영 시각은 앞머리 photo_note 에. -->

""" + _PARAGRAPHS

TEMPLATE = """<!-- 직접 확인한 사실이 있으면 2번 문단에 "피플로드가 N일 확인한 결과" 로 넣는다.
     가격은 소비자가와 실제 결제가만. -->

""" + _PARAGRAPHS


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

    key = f"ent-{category or 'startrip'}" if ent else region
    front = {
        "id": f"art-{key}-{day.replace('-', '')}",
        "channel": "ent" if ent else "travel",
        "region": "" if ent else region,
        "category": (category or "") if ent else "",
        "section": section,
        "title": title,
        # 비워두면 그 지면 담당 기자가 붙는다(src/desks.py REPORTERS).
        # 다른 기자가 맡으면 명부의 이름을 적는다. 명부 밖 이름은 적지 않는다.
        "source_name": "",
        # 취재·기획·인터뷰가 자체 기사다. 네이버 심사는 그 비중을 본다(50% 이상).
        "kind": "취재",
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
        where = (f"ent/{front.get('category') or 'startrip'}"
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
