"""등급을 매기고 오늘 검수할 해설 기사 후보를 고른다.

C등급 후보 상한(5건)이 있는 이유: 검수량이 하루 감당 가능한 양을 넘으면
검수 자체가 중단된다. 상한이 없는 검수 큐는 곧 아무도 안 보는 큐가 된다.
"""
from __future__ import annotations

import re

from src.models import Item

MAX_C_PER_DAY = 5
MIN_OUTLETS_FOR_CLUSTER = 3  # 대표 1 + related 2 = 3개 매체

# 영문 키워드에 붙여 허용할 어미. launch/launches/launched/launching 은 잡고
# launcher/launchers 는 잡지 않는다.
_INFLECTION = r"(?:e?[sd]|ing)?"

FLIGHT_KEYWORDS = (
    "취항", "증편", "감편", "신규 노선", "노선 확대", "운항 중단", "직항",
    "new route", "new service", "nonstop", "adds flight", "launch",
    "increase frequency", "suspend service",
)


def classify(item: Item) -> str:
    """사실 데이터인가 인용인가. 해설(C)은 여기서 정하지 않는다."""
    return "A" if item.section == "data" else "B"


def apply_grades(items: list[Item]) -> list[Item]:
    for item in items:
        # 이미 C(해설)인 항목은 건드리지 않는다. classify 는 A/B 만 판정하므로
        # 덮어쓰면 우리가 쓴 해설 기사가 매 실행 B 로 강등된다.
        if item.grade != "C":
            item.grade = classify(item)
        # 항공 노선 변동 기사는 항공 섹션으로 옮긴다. 전 지역 항공 페이지의 재료가
        # 되고, 여행객이 예약 결정에 직접 쓰는 정보라 따로 모을 값어치가 있다.
        if item.section == "news" and is_flight_event(item.title):
            item.section = "flight"
    return items


def is_flight_event(title: str) -> bool:
    """제목이 항공 노선 변동을 말하는가.

    영문 키워드는 **단어 경계**로 맞춘다. 부분일치를 허용하면 "launch" 가
    군사 기사의 "launchers" 에 걸린다 — 실측에서 이란 관련 기사가 항공 섹션으로
    올라오고 검수 후보까지 됐다. 대신 흔한 어미(-s/-es/-ed/-ing)는 허용한다.
    "launched a new route" 를 놓치면 안 되기 때문이다.

    한글 키워드는 부분일치 그대로 둔다. 한국어는 조사가 붙어 오므로
    ("취항한다", "증편했다") 단어 경계를 요구하면 대부분을 놓친다.
    """
    lowered = title.lower()
    for keyword in FLIGHT_KEYWORDS:
        lowered_keyword = keyword.lower()
        if lowered_keyword.isascii():
            pattern = r"\b" + re.escape(lowered_keyword) + _INFLECTION + r"\b"
            if re.search(pattern, lowered):
                return True
        elif lowered_keyword in lowered:
            return True
    return False


def pick_c_candidates(items: list[Item], trending: list[str],
                      max_n: int = MAX_C_PER_DAY) -> list[tuple[Item, str]]:
    """해설 기사 후보를 우선순위대로 고른다.

    우선순위: ①3개 이상 매체가 보도 ②검색 급상승 키워드와 겹침 ③항공 노선 변동.
    셋 다 해당해도 한 번만 뽑히고, 가장 앞선 사유가 기록된다.
    """
    lowered_trending = [t.lower() for t in trending if t]

    by_cluster: list[tuple[Item, str]] = []
    by_trend: list[tuple[Item, str]] = []
    by_flight: list[tuple[Item, str]] = []

    for item in items:
        if item.grade == "A":
            continue  # 사실 데이터에 해설을 붙이지 않는다

        outlets = 1 + len(item.related)
        if outlets >= MIN_OUTLETS_FOR_CLUSTER:
            by_cluster.append((item, f"{outlets}개 매체가 보도"))
            continue

        lowered_title = item.title.lower()
        hit = next((t for t in lowered_trending if t in lowered_title), None)
        if hit:
            by_trend.append((item, f"검색 급상승 키워드 '{hit}'"))
            continue

        if is_flight_event(item.title):
            by_flight.append((item, "항공 노선 변동"))

    return (by_cluster + by_trend + by_flight)[:max_n]
