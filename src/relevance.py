"""기사가 여행자에게 쓸모 있는가.

현지 종합지는 그 지역 **주민**을 위한 신문이다. 선거·범죄·행정 기사가 대부분이고,
그대로 실으면 여행 신문 1면에 살인 사건이 올라간다(실제로 그랬다).

이 필터는 완벽하지 않다. 키워드 방식이라 양방향 오류가 난다. 그래서 **1차 방어선은
소스 선정**이고 이건 그 뒤를 받는 그물이다. 놓치는 쪽(기사를 버리는 쪽)으로 틀리게
만들었다 — 여행 신문에 살인 기사가 실리는 것보다 여행 기사 몇 건을 놓치는 게 낫다.
"""
from __future__ import annotations

import re

TRAVEL_KEYWORDS: tuple[str, ...] = (
    # 이동·항공
    "항공", "취항", "노선", "증편", "감편", "직항", "공항", "비행", "결항",
    "수하물", "항공권",
    "flight", "airline", "airport", "airfare", "nonstop", "aviation", "route",
    # 숙박
    "호텔", "리조트", "숙소", "숙박", "펜션", "게스트하우스", "객실",
    "hotel", "resort", "accommodation", "lodging", "hostel",
    # 여행 일반
    "여행", "관광", "투어", "패키지", "명소", "여행객", "관광객", "입국",
    "비자", "여권", "성수기",
    "travel", "tourism", "tourist", "vacation", "holiday", "itinerary",
    "destination", "visa", "passport", "sightseeing",
    # 활동·현지
    "해변", "해수욕", "스노클", "다이빙", "크루즈", "요트", "골프", "면세",
    "맛집", "레스토랑", "카페", "축제",
    "beach", "snorkel", "diving", "cruise", "yacht", "golf", "duty-free",
    "festival", "dining", "restaurant", "attraction", "museum",
    # 여행에 영향을 주는 정보
    "환율", "날씨", "태풍", "수온", "여행경보",
    "weather", "typhoon", "forecast", "advisory",
    # 재난·교통 경보. 2026-09-09 실측: 허리케인 로웰로 카우아이 고속도로가 막히고 3만 3천 가구가 정전된 보도가 여행 키워드가 없어 전부 탈락했다. 여행자에게 이것보다 급한 뉴스는 없다.
    "hurricane", "storm", "tsunami", "earthquake", "eruption", "volcanic", "flood", "evacuation", "power outage", "highway", "road closure", "ferry", "terminal", "허리케인", "폭풍", "쓰나미", "지진", "화산", "홍수", "대피", "정전", "페리", "여객선", "도로 통제",
)

# 일부러 넣지 않은 것: "park"(주차된 차 사고·공원 민원이 통과했다),
# "trip"(외교 순방 "a 10-day trip" 이 통과했다), "fair"(공정성 기사).

# 여행 단어를 품고 있지만 여행 기사가 아닌 표현. 세기 전에 지운다.
# 실측 오탐: "여권통문"(1898년 여성인권선언)이 여권으로, "제2공항"·"한국공항공사"가
# 공항으로 잡혀 정치·행정 기사가 통과했다.
TRAVEL_EXCLUSIONS: tuple[str, ...] = ("여권통문", "제2공항", "한국공항공사", "공항공사")

# 영문 키워드에 붙여 허용할 어미. travel/travels/traveled 뿐 아니라 겹자음 형태인
# travelled·travelling 도 잡아야 한다 — 영국식 철자가 말레이시아·싱가포르·호주
# 영어권 소스의 표준이라, 안 잡으면 그쪽 기사를 통째로 놓친다.
_INFLECTION = r"(?:l?e?[sd]|l?ing)?"


# 여행 단어가 있어도 실을 수 없는 것. 사건 기사는 여행지 이름이나 "호텔"·"공항"·
# "식당"이 배경으로 나올 뿐 여행 정보가 아니다. 실측: 하와이 지면에 "호텔 직원
# 성범죄 유죄"가 hotel 로, "식당 살인미수"가 restaurant 로 통과해 실렸다.
#
# 대인 범죄 어휘로만 좁혔다. lawsuit·arrest 같은 넓은 말은 넣지 않는다 —
# "수하물 분실 소송"과 "기내 난동 승객 체포"는 여행자에게 쓸모 있는 기사다.
CRIME_KEYWORDS: tuple[str, ...] = (
    "convicted", "murder", "manslaughter", "homicide", "rape",
    "sexual assault", "sexually assaulted", "predator", "pervert",
    "stabbed", "stabbing", "shooting", "shot dead", "molest",
    "성폭행", "성추행", "강제추행", "살인", "살해", "흉기", "음주운전",
    # 2026-09-09 실측: '음주운전 기소된 식당 주인' 기사가 restaurant 로 통과했다.
    "dui", "drunk driving", "drunken driving", "robbery", "carjacking",
)


def is_crime_report(text: str) -> bool:
    """사건 기사인가. 여행 전용 매체에는 적용하지 않는다.

    VnExpress Travel 처럼 여행 지면이 낸 기사는 범죄를 다뤄도 여행 기사다
    ("문제 관광객 경고" 같은 것). 그래서 이 게이트는 종합지에만 건다.
    """
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in CRIME_KEYWORDS)

def is_travel_related(text: str) -> bool:
    """여행자에게 쓸모 있는 기사인가. 빈 문자열·None 은 아니다.

    영문 키워드는 단어 경계로 맞춘다 — 부분일치를 허용하면 "travel" 이
    "travelling" 을 넘어 엉뚱한 곳까지 걸린다. 한글은 조사가 붙어 오므로
    부분일치를 유지하되, 실측으로 확인된 오탐 표현만 미리 지운다.
    """
    if not text:
        return False

    lowered = text.lower()
    for phrase in TRAVEL_EXCLUSIONS:
        lowered = lowered.replace(phrase.lower(), " ")

    for keyword in TRAVEL_KEYWORDS:
        lowered_keyword = keyword.lower()
        if lowered_keyword.isascii():
            pattern = r"\b" + re.escape(lowered_keyword) + _INFLECTION + r"\b"
            if re.search(pattern, lowered):
                return True
        elif lowered_keyword in lowered:
            return True
    return False

# ── 스팸 ─────────────────────────────────────────────────────────────
# 구글뉴스 검색 피드에 "호텔" 을 넣으면 카지노 홍보 스팸이 섞여 온다. 2026-09-09
# 실측: "도쿄 호텔 카지노의 역사와 발전: 과거에서 현재까지 - 전문가의 관점에서",
# "오사카 호텔 카지노 완벽한 비교 가이드 (2025년 최신판)" 같은 틀에 박힌 제목이
# 하루 33건, 전부 og:site_name 이 "Histoire pour tous"(탈취된 프랑스 역사 사이트)로
# 풀렸다. '호텔' 키워드로 여행 필터를 통과해 지면에 실릴 뻔했다.
#
# 낱말 차단은 큐레이션(여행 전문지) 소스에는 걸지 않는다 — 인스파이어 리조트
# 카지노 개장 같은 업계 뉴스는 진짜 여행 뉴스다. 스팸은 검색 피드로만 들어온다.
SPAM_KEYWORDS: tuple[str, ...] = (
    "카지노", "casino", "바카라", "baccarat", "슬롯머신", "슬롯 머신", "토토",
    "먹튀", "온라인 도박", "사설 베팅", "betting site", "online gambling",
)
# 실측으로 확인된 스팸 출처. 이름이 이렇게 풀리면 내용과 무관하게 버린다.
SPAM_SOURCES: frozenset[str] = frozenset({"Histoire pour tous"})
# 블로그 플랫폼. 구글뉴스 검색 피드는 브런치·네이버 블로그 글도 기사처럼 돌려준다.
# 2026-09-09 실측: "하와이 호텔 추천 리스트 5선 총정리"(브런치)가 하와이면에 실렸다.
# 개인 글은 인용 매체가 아니다 — 출처 이름에 이 낱말이 있으면 버린다.
NON_NEWS_SOURCES: tuple[str, ...] = ("브런치", "네이버 블로그", "티스토리", "유튜브", "youtube")


def is_spam(text: str, source_name: str = "") -> bool:
    """검색 피드에 섞여 오는 도박 홍보 글인가."""
    if source_name and source_name in SPAM_SOURCES:
        return True
    if source_name and any(k in source_name.lower() for k in NON_NEWS_SOURCES):
        return True
    if not text:
        return False
    lowered = text.lower()
    return any(k.lower() in lowered for k in SPAM_KEYWORDS)
