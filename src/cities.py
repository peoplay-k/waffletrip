"""도시 페이지.

한국 사람은 "일본 여행"보다 "오사카 항공권", "후쿠오카 3박4일"로 검색한다.
지역면(일본·태국·대만)만 있으면 그 검색이 우리 페이지로 떨어지지 않는다.
그래서 도시마다 모아보기 페이지를 따로 낸다.

**얇은 페이지는 만들지 않는다.** 기사 몇 건짜리 페이지를 잔뜩 찍어내면
검색엔진이 사이트 전체를 낮게 본다. MIN_ARTICLES 를 못 넘긴 도시는
페이지를 내지 않고, 기사가 쌓이면 그날 빌드에서 저절로 생긴다.

도시는 저장하지 않고 렌더 시점에 계산한다 — topics.py 와 같은 이유로,
규칙을 고치면 과거 기사까지 다음 빌드에 따라오게 하려는 것이다.
"""
from __future__ import annotations

# (slug, 표시이름, region, 매칭어)
# 매칭어에는 공항·인근 지명을 함께 넣는다. "하네다 증편"은 도쿄 기사다.
CITIES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("tokyo",    "도쿄",    "japan",    ("도쿄", "동경", "하네다", "나리타")),
    ("osaka",    "오사카",  "japan",    ("오사카", "간사이", "교토", "고베", "난바")),
    ("fukuoka",  "후쿠오카", "japan",   ("후쿠오카", "하카타", "규슈")),
    ("sapporo",  "삿포로",  "japan",    ("삿포로", "홋카이도", "신치토세")),
    ("nagoya",   "나고야",  "japan",    ("나고야", "주부공항")),
    ("okinawa",  "오키나와", "japan",   ("오키나와", "나하")),
    ("bangkok",  "방콕",    "thailand", ("방콕", "수완나품")),
    ("chiangmai", "치앙마이", "thailand", ("치앙마이",)),
    ("phuket",   "푸켓",    "thailand", ("푸켓", "푸껫")),
    ("taipei",   "타이베이", "taiwan",  ("타이베이", "타이페이", "타오위안")),
    ("kaohsiung", "가오슝", "taiwan",   ("가오슝",)),
    ("danang",   "다낭",    "vietnam",  ("다낭", "호이안", "바나힐")),
    ("nhatrang", "나트랑",  "vietnam",  ("나트랑", "냐짱")),
    ("hanoi",    "하노이",  "vietnam",  ("하노이",)),
    ("hochiminh", "호치민", "vietnam",  ("호치민", "호찌민")),
    ("phuquoc",  "푸꾸옥",  "vietnam",  ("푸꾸옥", "푸꿕")),
)

CITY_NAMES = {slug: name for slug, name, _, _ in CITIES}
CITY_REGION = {slug: region for slug, _, region, _ in CITIES}

# 이 아래면 페이지를 내지 않는다. 검색엔진이 빈약한 페이지를 싫어한다.
MIN_ARTICLES = 8


def cities_of(item) -> list[str]:
    """기사가 걸리는 도시들. 한 기사가 여러 도시에 걸릴 수 있다
    ("도쿄·오사카 노선 증편")."""
    text = f"{getattr(item, 'title', '') or ''} {getattr(item, 'summary', '') or ''}"
    return [slug for slug, _, _, words in CITIES
            if any(w in text for w in words)]


def group_by_city(items) -> dict[str, list]:
    """도시별 기사. 기사 수가 MIN_ARTICLES 를 넘는 도시만 돌려준다.

    A등급(환율·날씨)은 도시 기사가 아니므로 뺀다 — 지역 단위 데이터라
    도시 페이지에 넣으면 같은 값이 여섯 도시에 반복된다.
    """
    out: dict[str, list] = {slug: [] for slug, _, _, _ in CITIES}
    for item in items:
        if getattr(item, "grade", "") == "A":
            continue
        for slug in cities_of(item):
            out[slug].append(item)
    return {slug: got for slug, got in out.items() if len(got) >= MIN_ARTICLES}
