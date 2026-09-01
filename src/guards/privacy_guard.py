"""해설 기사가 개인정보나 거래 단가를 싣고 나가는 것을 막는다.

해설 기사(C등급)는 여행사 운영 기록 — 답사·정산·문의 로그 — 에서 나온다.
그 원천에는 고객 개인정보와 거래처 계약 숫자가 섞여 있다. 한 번 나가면
되돌릴 수 없으므로 **사람 주의력이 아니라 발행 경로에서 막는다.**

놓치는 쪽이 아니라 **막는 쪽으로 틀리게** 만들었다. 오탐이 나면 글을 고치면
되지만, 놓치면 고객 정보가 공개된다.
"""
from __future__ import annotations

import re

# 고객 개인정보
PII_PATTERNS = (
    ("주민등록번호", r"\b\d{6}\s*[-–]\s*[1-4]\d{6}\b"),
    ("여권번호", r"\b[MSRODmsrod]\d{8}\b"),
    ("휴대전화", r"\b01[016-9]\s*[-.]?\s*\d{3,4}\s*[-.]?\s*\d{4}\b"),
    ("카드번호", r"\b(?:\d{4}[\s-]){3}\d{4}\b"),
    ("이메일", r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b"),
    ("예약번호", r"예약번호\s*[:：]?\s*[A-Z0-9]{6,}"),
    ("고객 실명", r"(?:고객|손님)\s*[가-힣]{2,4}\s*(?:님|씨)"),
)

# 거래처 계약 숫자. 공개하는 가격은 소비자가와 실제 결제가뿐이다.
TRADE_TERMS = (
    "넷가", "넷 가", "net가", "net rate", "netrate", "도매가", "매입가",
    "랜드피", "랜드 피", "마진율", "수수료율", "커미션율", "정산단가", "계약단가",
)

# 우리 회사 연락처는 실어도 된다.
ALLOWED = ("reservation@guamplay.com", "bot@waffletrip.com")


def find_violations(text: str) -> list[tuple[str, str]]:
    """(종류, 걸린 것) 목록. 비어 있으면 통과."""
    if not text:
        return []
    scrubbed = text
    for allowed in ALLOWED:
        scrubbed = scrubbed.replace(allowed, "")

    hits: list[tuple[str, str]] = []
    for name, pattern in PII_PATTERNS:
        for m in re.finditer(pattern, scrubbed):
            hits.append((name, m.group(0)[:40]))
    lowered = scrubbed.lower()
    for term in TRADE_TERMS:
        if term.lower() in lowered:
            hits.append(("거래단가", term))
    return hits
