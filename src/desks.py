"""기사 서명(byline)을 정한다.

**사람 이름을 지어내지 않는다.** 실존하지 않는 기자 이름을 서명으로 붙이면
독자는 그것을 실제 기자로 읽는다. 한 명이라도 "이 기자 누구냐"고 물으면
매체 신뢰가 한 번에 끝나고, 광고·제휴 협상에서도 치명적이다.

대신 **부서로 나눈다.** 지면이 한 사람 손에서 나온 것처럼 보이지 않으면서
거짓이 아니다 — 실제로 데이터는 파이프라인이 만들고, 해설은 지역별로 쓴다.

**실명 바이라인으로 간다.** 네이버 뉴스 제휴는 4대보험 정규직 기자 5명 이상을
보고, 지어낸 이름이 아니라 실제로 일하는 사람의 이름을 본다(2026-09-16 편집국장).
기자가 정해지면 REPORTERS 에 이름을 올리고 초안의 `source_name` 에 그 이름을
적는다 — byline_for 는 적힌 이름을 그대로 존중한다. 그 전까지는 데스크명이다.
"""
from __future__ import annotations

from src.brand import SITE_NAME as BRAND  # noqa: E402 — 정본은 brand.py

# 실명 기자 명부. 결정 ③(기자 5명 — 누구를, 언제)이 나오면 채운다.
# 이름 → 맡은 지면. 여기에 없는 이름이 서명에 나오면 check_articles 가 짚는다.
# ★지어내지 않는다. 회사에 실제로 있는 사람만 올린다.
REPORTERS: dict[str, str] = {}

# 지역 해설 기사의 데스크
REGION_DESKS = {
    "guam": f"{BRAND} 괌 데스크",
    "saipan": f"{BRAND} 사이판 데스크",
    "hawaii": f"{BRAND} 하와이 데스크",
    "vietnam": f"{BRAND} 베트남 데스크",
    "kota": f"{BRAND} 코타키나발루 데스크",
    "laos": f"{BRAND} 라오스 데스크",
    "jeju": f"{BRAND} 제주 데스크",
    "japan": f"{BRAND} 일본 데스크",
    "thailand": f"{BRAND} 태국 데스크",
    "taiwan": f"{BRAND} 대만 데스크",
}
DATA_DESK = f"{BRAND} 데이터팀"
EDIT_DESK = f"{BRAND} 편집팀"
# 연예 채널의 기본 서명. 지역이 없으므로 데스크가 하나다.
ENT_DESK = f"{BRAND} 문화부"

# 연예 기사가 만들어지는 방식. 수집·자동 생성 경로가 없다 — 편집실에서 사람이
# 보도자료·현장 소스를 받아 쓰고 승인해야 나간다. 그래서 자동이 아니다.
ENT_HOW = "편집실 작성 · 사람 승인"

# 각 데스크가 맡는 일. 편집국 소개에 그대로 쓴다 —
# 독자가 "누가 이걸 만드나"를 알 수 있어야 한다.
#
# 만드는 방식은 **실제와 같아야 한다.** 2026-09-09 점검에서 지역 데스크가
# "사람" 으로 적혀 있었는데, 해설은 사람이 정한 취재 지침(docs/DAILY_COMMENTARY.md)
# 을 읽고 예약된 AI 가 쓰고 자동 발행한다. 신뢰도를 말하는 페이지에서 이걸
# 틀리면 페이지 전체가 무너진다. 사람이 쓰기 시작하면 그때 라벨을 바꾼다.
DESK_DUTIES = (
    (DATA_DESK, "환율·날씨를 매일 아침 직접 수집해 정리합니다. 데이터 기사도 여기서 만듭니다.",
     "자동"),
    (EDIT_DESK, "다른 매체의 보도를 골라 제목과 두 문장 요약에 원문 링크를 답니다.",
     "자동"),
    (REGION_DESKS["guam"], "괌 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["saipan"], "사이판 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["hawaii"], "하와이 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["vietnam"], "베트남 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["kota"], "코타키나발루 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["laos"], "라오스 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["jeju"], "제주 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["japan"], "일본 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["thailand"], "태국 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["taiwan"], "대만 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (ENT_DESK, "영화·드라마·방송·음악·공연·인물과 '스타의 여행' 기사를 맡습니다. "
               "소속사·배급사 보도자료와 현장 취재로 씁니다.", ENT_HOW),
)


def byline_for(item) -> str:
    """이 기사의 서명.

    B등급(큐레이션)은 원문 매체 이름을 그대로 둔다 — 그게 쓴 사람이다.
    바꾸면 남의 기사를 우리가 쓴 것처럼 보이게 만드는 것이라 하면 안 된다.
    """
    grade = getattr(item, "grade", "")
    if grade == "B":
        return getattr(item, "source_name", "") or EDIT_DESK
    if grade == "A":
        return DATA_DESK
    # C등급 — 우리가 쓴 글. 이미 필자가 적혀 있으면 존중한다.
    written_by = getattr(item, "source_name", "") or ""
    if written_by and written_by != BRAND:
        return written_by
    if getattr(item, "channel", "travel") == "ent":
        return ENT_DESK
    return REGION_DESKS.get(getattr(item, "region", ""), EDIT_DESK)
