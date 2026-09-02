"""기사를 편집 부문으로 가른다.

부문 구성은 여행신문의 지면 구성을 그대로 따른다.
  여행BIZ · 이슈·동향 · 관광정책 · 기획·연재 · 국제 · 피플·오피니언 · 통계·리포트

부문은 저장하지 않고 렌더 시점에 계산한다. Item 에 필드를 늘리면 기존 jsonl 을
전부 옮겨야 하는데, 분류 규칙은 앞으로도 손볼 것이라 그때마다 과거 데이터가
어긋난다. 규칙이 바뀌면 다음 빌드에 전체가 따라온다.
"""
from __future__ import annotations

import re

# (id, 이름, 설명) — 표시 순서가 곧 네비 순서다
TOPICS = (
    ("biz", "여행BIZ", "항공사·여행사·호텔·플랫폼 등 여행업계 소식입니다."),
    ("issue", "이슈·동향", "지금 여행지에서 벌어지고 있는 일입니다."),
    ("policy", "관광정책", "관광청·정부·지자체의 정책과 발표입니다."),
    ("feature", "기획·연재", "저희가 직접 취재하고 정리한 기사입니다."),
    ("world", "국제", "현지 매체가 전하는 해외 소식입니다."),
    ("people", "피플·오피니언", "사람과 의견입니다."),
    ("data", "통계·리포트", "환율과 날씨. 매일 아침 저희가 직접 만드는 값입니다."),
)
TOPIC_NAMES = {tid: name for tid, name, _ in TOPICS}
TOPIC_DESCS = {tid: desc for tid, _, desc in TOPICS}

# 한글은 조사가 붙어 오므로 부분일치, 영문은 단어 경계로 본다.
# 영문을 부분일치로 두면 air 가 chair 에, eat 가 great 에 걸린다.
_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("policy",
     ("관광청", "관광공사", "지자체", "정부", "부처", "정책", "협약", "조례",
      "인허가", "규제", "비자", "입국"),
     ("tourism board", "government", "authority", "ministry", "policy",
      "regulation", "visa", "immigration")),
    ("people",
     ("인터뷰", "대표", "사장", "취임", "선임", "칼럼", "기고", "오피니언", "인사"),
     ("interview", "opinion", "column", "appointed", "ceo")),
    ("biz",
     ("항공사", "여행사", "랜드사", "호텔", "리조트", "취항", "노선", "증편",
      "감편", "운항", "예약", "플랫폼", "실적", "매출", "제휴", "출시", "판매"),
     ("airline", "airlines", "hotel", "hotels", "resort", "resorts", "route",
      "routes", "flight", "flights", "booking", "revenue", "partnership",
      "launch", "operator")),
    ("issue",
     ("태풍", "기상", "경보", "주의보", "안전", "사고", "지진", "폐쇄", "통제",
      "혼잡", "축제", "행사", "개장", "재개"),
     ("storm", "hurricane", "typhoon", "alert", "warning", "closed", "closure",
      "festival", "reopen", "quake", "crowd")),
)


def _hit(text: str, korean: tuple[str, ...], english: tuple[str, ...]) -> bool:
    if any(w in text for w in korean):
        return True
    lowered = text.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", lowered) for w in english)


def topic_of(item) -> str:
    """기사의 부문.

    등급이 부문을 이긴다 — 우리가 만든 데이터(A)와 우리가 쓴 기사(C)는
    소재가 무엇이든 그 부문에 속한다.
    어디에도 안 걸리면 국제로 보낸다. 우리 기사는 전부 해외발이고,
    버리면 지면에서 통째로 빠진다.
    """
    if getattr(item, "grade", "") == "A":
        return "data"
    # 우리가 만든 데이터 기사는 등급이 C(자체 생산)지만 성격은 통계·리포트다.
    # section 이 data 면 그쪽으로 보낸다.
    if getattr(item, "section", "") == "data":
        return "data"
    if getattr(item, "grade", "") == "C":
        return "feature"
    if getattr(item, "section", "") == "flight":
        return "biz"

    text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}"
    for topic_id, korean, english in _RULES:
        if _hit(text, korean, english):
            return topic_id
    return "world"


def group_by_topic(items) -> dict:
    out: dict[str, list] = {tid: [] for tid, _, _ in TOPICS}
    for item in items:
        out[topic_of(item)].append(item)
    return out
