"""기사를 편집 부문으로 가른다.

지역면(괌·사이판·…)만으로 지면을 나누면 신문이 아니라 목적지 디렉터리로
보인다. 국내 여행 전문지는 전부 편집 축으로 나눈다 — 여행신문은
`여행BIZ · 이슈·동향 · 관광정책 · 기획·연재 · 국제 · 피플·오피니언 · 통계·리포트`.

**그 축을 그대로 베끼지 않았다.** 실제 기사 109건에 대보니 '관광정책'은 1건뿐이라
빈 메뉴가 되고, 어디에도 안 걸리는 기사가 30건(28%)이었다. 우리 콘텐츠에 맞춰
다시 잡았고, 모든 부문에 실제로 기사가 들어간다.

부문은 저장하지 않고 **렌더 시점에 계산한다.** Item 에 필드를 늘리면 기존
jsonl 을 전부 옮겨야 하는데, 분류 규칙은 앞으로도 손볼 것이라 그때마다
과거 데이터가 어긋난다. 규칙이 바뀌면 다음 빌드에 전체가 따라온다.
"""
from __future__ import annotations

import re

# (id, 이름, 한 줄 설명) — 표시 순서가 곧 네비 순서다
TOPICS = (
    ("news", "소식", "일곱 개 지역에서 오늘 들어온 여행 소식입니다."),
    ("flight", "항공", "신규취항·증편·감편·운항중단을 한자리에 모았습니다."),
    ("stay", "숙소", "호텔과 리조트 소식입니다."),
    ("eat", "먹거리", "식당과 음식 소식입니다."),
    ("play", "즐길거리", "투어·해변·축제·전시 소식입니다."),
    ("weather", "날씨·안전", "태풍·기상특보·여행경보 등 안전에 관한 소식입니다."),
    ("data", "데이터", "환율과 날씨. 매일 아침 저희가 직접 만드는 값입니다."),
    ("feature", "기획", "저희가 직접 취재하고 정리한 기사입니다."),
)
TOPIC_NAMES = {tid: name for tid, name, _ in TOPICS}
TOPIC_DESCS = {tid: desc for tid, _, desc in TOPICS}

# 한글은 조사가 붙어 오므로 부분일치, 영문은 단어 경계로 본다.
# 영문을 부분일치로 두면 'air' 가 'chair' 에, 'eat' 가 'great' 에 걸린다.
_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("weather",
     ("날씨", "태풍", "기상", "폭우", "폭염", "경보", "주의보", "안전", "지진", "해일"),
     ("weather", "storm", "hurricane", "typhoon", "cyclone", "alert", "warning",
      "forecast", "quake", "tsunami", "flood")),
    ("flight",
     ("항공", "취항", "노선", "공항", "탑승", "결항", "증편", "감편", "직항", "운항"),
     ("flight", "flights", "airline", "airlines", "airport", "route", "routes",
      "nonstop", "airfare")),
    ("stay",
     ("호텔", "리조트", "숙소", "숙박", "객실", "펜션"),
     ("hotel", "hotels", "resort", "resorts", "lodging", "accommodation")),
    ("eat",
     ("맛집", "식당", "음식", "뷔페", "레스토랑", "카페", "요리"),
     ("restaurant", "restaurants", "dining", "cuisine", "chef", "cafe")),
    ("play",
     ("투어", "액티비티", "해변", "비치", "축제", "전시", "공연", "체험", "골프",
      "스노클", "다이빙", "박람회", "테마파크"),
     ("tour", "tours", "beach", "beaches", "festival", "exhibit", "exhibition",
      "diving", "snorkel", "park", "cruise", "attraction")),
)


def _hit(text: str, korean: tuple[str, ...], english: tuple[str, ...]) -> bool:
    if any(w in text for w in korean):
        return True
    lowered = text.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", lowered) for w in english)


def topic_of(item) -> str:
    """기사의 부문. 어디에도 안 걸리면 '소식'으로 보낸다.

    등급이 부문을 이긴다 — 우리가 만든 데이터(A)와 우리가 쓴 기사(C)는
    소재가 무엇이든 그 부문에 속한다.
    """
    if getattr(item, "grade", "") == "A":
        return "data"
    if getattr(item, "grade", "") == "C":
        return "feature"
    if getattr(item, "section", "") == "flight":
        return "flight"

    text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}"
    for topic_id, korean, english in _RULES:
        if _hit(text, korean, english):
            return topic_id
    return "news"


def group_by_topic(items) -> dict:
    out: dict[str, list] = {tid: [] for tid, _, _ in TOPICS}
    for item in items:
        out[topic_of(item)].append(item)
    return out
