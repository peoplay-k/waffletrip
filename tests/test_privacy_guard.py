"""개인정보·거래단가 가드. 놓치는 쪽이 아니라 막는 쪽으로 틀려야 한다."""
from __future__ import annotations

import pytest

from src.guards.privacy_guard import find_violations


@pytest.mark.parametrize("text,kind", [
    ("고객 주민등록번호 901231-1234567 확인", "주민등록번호"),
    ("여권 M12345678 로 예약", "여권번호"),
    ("연락처 010-1234-5678 입니다", "휴대전화"),
    ("카드 1234-5678-9012-3456 결제", "카드번호"),
    ("문의는 hong@example.com 으로", "이메일"),
    ("예약번호: ABC12345 확인", "예약번호"),
    ("고객 김철수님이 요청하셨다", "고객 실명"),
])
def test_personal_information_is_caught(text, kind):
    assert kind in [k for k, _ in find_violations(text)]


@pytest.mark.parametrize("term", ["넷가", "도매가", "마진율", "랜드피", "계약단가"])
def test_trade_terms_are_caught(term):
    assert ("거래단가", term) in find_violations(f"이번 {term}는 낮았다")


def test_our_own_contact_is_allowed():
    """우리 회사 연락처는 실어도 된다."""
    assert find_violations("문의 reservation@guamplay.com") == []


def test_clean_article_passes():
    text = ("괌 직항이 주 3회에서 5회로 늘어난다. 실제 결제가는 1박 18만원이었다.\n\n"
            "| 항목 | 값 |\n|---|---|\n| 주간 운항 | 5회 |")
    assert find_violations(text) == []


def test_empty_text_passes():
    assert find_violations("") == []
    assert find_violations(None) == []


def test_consumer_price_is_not_blocked():
    """공개해도 되는 소비자가까지 막으면 예산 기사를 못 쓴다."""
    assert find_violations("1박 실제 결제가는 180,000원이었다") == []
