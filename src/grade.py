"""등급을 매기고 오늘 검수할 해설 기사 후보를 고른다.

C등급 후보 상한(5건)이 있는 이유: 검수량이 하루 감당 가능한 양을 넘으면
검수 자체가 중단된다. 상한이 없는 검수 큐는 곧 아무도 안 보는 큐가 된다.
"""
from __future__ import annotations

from src.models import Item

MAX_C_PER_DAY = 5
MIN_OUTLETS_FOR_CLUSTER = 3  # 대표 1 + related 2 = 3개 매체

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
        item.grade = classify(item)
        # 항공 노선 변동 기사는 항공 섹션으로 옮긴다. 전 지역 항공 페이지의 재료가
        # 되고, 여행객이 예약 결정에 직접 쓰는 정보라 따로 모을 값어치가 있다.
        if item.section == "news" and is_flight_event(item.title):
            item.section = "flight"
    return items


def is_flight_event(title: str) -> bool:
    lowered = title.lower()
    return any(k.lower() in lowered for k in FLIGHT_KEYWORDS)


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
