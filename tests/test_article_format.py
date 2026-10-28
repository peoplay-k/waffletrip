"""신문 기사 형식 점검(2026-10-28 사장님 기준 기사)."""
from src.article_format import format_problems

GOOD = ("올마이투어가 인도 온라인 여행 플랫폼 메이크마이트립과 국내 호텔 숙박 공급 계약을 체결하고, "
        "직계약 숙소를 현지 앱과 웹에서 판매한다. 레지던스형 숙소와 결합 상품으로 장기 체류 수요를 반영한다.\n\n"
        "올마이투어는 27일 메이크마이트립과 한국 숙박 상품 공급 계약을 체결했다고 밝혔다. "
        "한국관광공사 한국관광데이터랩에 따르면 상반기 방한 인도 관광객은 전년 동기 대비 15.2% 증가했다.\n\n") * 4


def test_newspaper_paragraphs_pass():
    assert format_problems(GOOD) == []


def test_blog_style_is_flagged():
    body = GOOD + "\n## 알아둘 점\n\n- 요금은 아직 알려지지 않았다.\n\n| 구분 | 내용 |\n|---|---|\n\n**굵게** [괌 지역면](/guam/)"
    got = format_problems(body)
    for k in ("소제목 1개", "목록", "표", "굵은 글씨", "지역면 링크", "모르는 것 문장", "독자에게 말 거는 문장"):
        assert k in got, (k, got)


def test_length_and_exemptions():
    assert any(p.startswith("짧다") for p in format_problems("짧은 기사다."))
    assert format_problems("## 소제목\n\n" + GOOD, feature=True) == []
    assert format_problems("> **방송 정보**\n\n## 첫 장면", tv=True) == []
