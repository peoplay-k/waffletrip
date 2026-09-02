"""기사 서명(byline)을 정한다.

**사람 이름을 지어내지 않는다.** 실존하지 않는 기자 이름을 서명으로 붙이면
독자는 그것을 실제 기자로 읽는다. 한 명이라도 "이 기자 누구냐"고 물으면
매체 신뢰가 한 번에 끝나고, 광고·제휴 협상에서도 치명적이다.

대신 **부서로 나눈다.** 지면이 한 사람 손에서 나온 것처럼 보이지 않으면서
거짓이 아니다 — 실제로 데이터는 파이프라인이 만들고, 해설은 지역별로 쓴다.
필자가 정해지면 그 사람 이름(또는 본인이 정한 필명)으로 바꾸면 된다.
"""
from __future__ import annotations

BRAND = "와플트립"

# 지역 해설 기사의 데스크
REGION_DESKS = {
    "guam": f"{BRAND} 괌 데스크",
    "saipan": f"{BRAND} 사이판 데스크",
    "hawaii": f"{BRAND} 하와이 데스크",
    "vietnam": f"{BRAND} 베트남 데스크",
    "kota": f"{BRAND} 코타키나발루 데스크",
    "laos": f"{BRAND} 라오스 데스크",
    "jeju": f"{BRAND} 제주 데스크",
}
DATA_DESK = f"{BRAND} 데이터팀"
EDIT_DESK = f"{BRAND} 편집팀"


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
    return REGION_DESKS.get(getattr(item, "region", ""), EDIT_DESK)
