import pytest

from src.region_tag import tag_region, REGION_KEYWORDS, SINGLE_CHAR_ALLOWED
from src.models import REGIONS


def test_tags_guam_from_korean_title():
    assert tag_region("진에어, 괌 노선 증편 결정") == "guam"


def test_tags_from_english_name():
    assert tag_region("United adds Guam service") == "guam"


def test_is_case_insensitive():
    assert tag_region("HAWAII tourism rebounds") == "hawaii"


def test_tags_vietnam_from_city_name():
    assert tag_region("다낭 신규 리조트 오픈") == "vietnam"
    assert tag_region("나트랑 직항 재개") == "vietnam"


def test_tags_saipan_from_landmark():
    assert tag_region("마나가하 섬 입장료 인상") == "saipan"


def test_tags_kota_only_on_the_full_city_name():
    """'말레이시아'나 '사바'만으로 코타키나발루라고 단정하지 않는다.

    쿠알라룸푸르 기사를 코타키나발루로 태깅하면 우리 신문이 사실을 틀리는 것이다.
    재현율보다 정확도를 택한다."""
    assert tag_region("코타키나발루 신규 취항") == "kota"
    assert tag_region("말레이시아 관광객 증가") is None


def test_tags_laos():
    assert tag_region("루앙프라방 야시장 재개장") == "laos"


def test_tags_jeju():
    assert tag_region("제주 렌터카 요금 인하") == "jeju"


def test_returns_none_for_destinations_we_do_not_cover():
    """지역면이 열 곳으로 늘었다. 오사카·방콕·타이베이는 이제 우리 지면이다."""
    assert tag_region("파리 올림픽 관광 특수") is None
    assert tag_region("두바이 신규 호텔 개장") is None


def test_returns_none_for_empty_text():
    assert tag_region("") is None


def test_picks_the_region_with_more_hits():
    """여러 지역이 언급되면 더 많이 언급된 쪽으로 정한다."""
    assert tag_region("괌 여행 인기, 괌 호텔 만실 — 하와이도 회복세") == "guam"


def test_ties_break_by_fixed_region_order():
    """동점이면 항상 같은 결과가 나와야 한다. 실행마다 달라지면 안 된다."""
    assert tag_region("괌·사이판 공동 프로모션") == "guam"


def test_every_keyword_bucket_is_a_real_region():
    assert set(REGION_KEYWORDS) == set(REGIONS)


def test_single_character_keywords_come_from_an_explicit_allowlist():
    """한 글자 키워드는 오탐을 부르므로 명시 허용 목록에 있는 것만 쓴다.

    '괌'은 한국어에서 다른 단어의 부분문자열로 거의 나타나지 않아 안전하다.
    새 한 글자 키워드를 넣으려면 허용 목록에 추가하고 근거를 남겨야 한다.
    """
    for region, words in REGION_KEYWORDS.items():
        for w in words:
            assert len(w) > 1 or w in SINGLE_CHAR_ALLOWED, (
                f"{region} 의 한 글자 키워드 '{w}' 가 허용 목록에 없다")


def test_airline_name_containing_a_region_is_not_the_destination():
    """제주항공은 제주가 아니라 전 세계로 날아가는 항공사다.

    실측에서 이 한 단어가 중국 계림·일본 나고야·오사카 기사를 제주로 잘못
    태깅했다. 항공사명은 목적지가 아니다.
    """
    assert tag_region("제주항공, 부산~구이린 노선 취항") is None
    # 제주항공이 지워진 뒤 남는 목적지로 정해진다. 일본 지역면이 생겨
    # 이제 버려지지 않고 제대로 일본으로 간다.
    assert tag_region("제주항공, 오사카 노선 증편") == "japan"
    assert tag_region("노랑풍선, 일본 나고야 상품 — 제주항공 나고야 4일") == "japan"


def test_real_jeju_articles_still_tag_after_the_exclusion():
    """제외 규칙이 진짜 제주 기사까지 잡아먹으면 안 된다."""
    assert tag_region("제주 렌터카 요금 인하") == "jeju"
    assert tag_region("모두를 위한 제주, 열린 관광 페스타") == "jeju"
    assert tag_region("에어서울, 제주 노선 탑승률 96.6%") == "jeju"


def test_hawaiian_airlines_is_not_a_hawaii_destination():
    """하와이안항공은 나리타(일본) 노선도 다닌다. 항공사명은 목적지가 아니다.

    목적지는 나리타 쪽이다 — 항공사 이름에 하와이가 들어 있다고 하와이 기사가
    되지는 않는다.
    """
    assert tag_region("하와이안항공, 나리타 노선 신규 취항") == "japan"
    assert tag_region("하와이안항공, 신규 기재 도입") is None


def test_hawaiian_airlines_article_about_hawaii_still_tags():
    """진짜 하와이 기사는 지명이 따로 나온다. 제외 규칙이 그것까지 먹으면 안 된다."""
    assert tag_region("하와이안항공, 인천~호놀룰루 증편") == "hawaii"
    assert tag_region("하와이안항공, 하와이 노선 확대") == "hawaii"


def test_common_non_target_destinations_are_not_mistagged():
    """길이 규칙보다 이쪽이 진짜 방어선이다. 오탐이 곧 오보다."""
    for text in ("파리 올림픽 특수", "세부 리조트 개장", "유류할증료 인상",
                 "여권 발급 수수료 변경", "발리 우기 정보", "두바이 공항 확장"):
        assert tag_region(text) is None, text


def test_tags_hawaii_from_island_names():
    """섬 이름 철자가 틀리면 조용히 아무것도 안 잡는다. 철자를 고정한다."""
    assert tag_region("오아후 해변 여행 특집") == "hawaii"
    assert tag_region("마우이 산불 복구 현황") == "hawaii"
    assert tag_region("와이키키 호텔 요금 인상") == "hawaii"


# ── 새 지역 (일본·태국·대만) ──────────────────────────────────────
@pytest.mark.parametrize("title,expected", [
    ("아시아나항공, 인천~고베 매일 띄운다", None),
    ("피치항공, 오사카 당일치기 여행 상품 선보여", "japan"),
    ("도쿄 관광객 역대 최다", "japan"),
    ("후쿠오카 노선 증편", "japan"),
    ("태국 방콕 호텔 예약 급증", "thailand"),
    ("대만 타이베이 항공 노선 확대", "taiwan"),
])
def test_new_regions_are_tagged(title, expected):
    assert tag_region(title) == expected


def test_every_region_has_keywords():
    """지역을 늘리고 키워드를 잊으면 그 지역이 통째로 비어 버린다."""
    from src.models import REGIONS
    from src.region_tag import REGION_KEYWORDS
    missing = [r for r in REGIONS if not REGION_KEYWORDS.get(r)]
    assert not missing, f"키워드 없는 지역: {missing}"


def test_missing_keywords_do_not_crash():
    """키워드를 잊어도 빌드가 통째로 죽으면 안 된다."""
    import src.region_tag as rt
    saved = rt.REGION_KEYWORDS.pop("japan")
    try:
        assert tag_region("오사카 노선 증편") is None
    finally:
        rt.REGION_KEYWORDS["japan"] = saved


def test_hanja_abbreviation_counts_as_the_country():
    """국내 매체는 제목에서 '日항공사', '泰 관광청'처럼 줄여 쓴다."""
    assert tag_region("日항공사, 유류할증료 2배 인상") == "japan"
    assert tag_region("泰 관광청, 한국인 유치 확대") == "thailand"


def test_a_date_is_not_a_country():
    """'30日'은 날짜다. 숫자 뒤의 한자를 나라로 읽으면 안 된다."""
    assert tag_region("오는 30日 신규 물류센터 개장") is None


def test_airport_name_alone_identifies_the_destination():
    """'나리타 증편'에는 '일본'이라는 말이 없다. 놓치면 기사를 통째로 버린다."""
    assert tag_region("에어프레미아, 나리타 노선 주 7회→10회 증편") == "japan"
    assert tag_region("수완나품 공항 이용객 회복") == "thailand"


def test_mentions_region_keeps_articles_about_two_places():
    """제주·후쿠오카를 함께 다룬 기사는 두 지역 다 맞다.
    tag_region 은 하나만 고르므로 목적지 피드 검증에는 쓸 수 없다."""
    from src.region_tag import mentions_region
    title = "추석 여행 어디로…국내 '제주', 해외 '후쿠오카' 검색 1위"
    assert mentions_region(title, "japan")
    assert mentions_region(title, "jeju")
    assert not mentions_region(title, "thailand")


def test_mentions_region_still_rejects_unrelated_articles():
    from src.region_tag import mentions_region
    assert not mentions_region("항공물류 운임 상승세, 3분기 실적 갈린다", "japan")
    assert not mentions_region("오는 30日 신규 물류센터 개장", "japan")
