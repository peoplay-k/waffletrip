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
