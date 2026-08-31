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
    assert tag_region("오사카 벚꽃 명소 총정리") is None
    assert tag_region("파리 올림픽 관광 특수") is None


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


def test_common_non_target_destinations_are_not_mistagged():
    """길이 규칙보다 이쪽이 진짜 방어선이다. 오탐이 곧 오보다."""
    for text in ("오사카 벚꽃 명소", "파리 올림픽 특수", "도쿄 여행 수요",
                 "방콕 호텔 요금", "세부 리조트 개장", "유류할증료 인상",
                 "여권 발급 수수료 변경", "발리 우기 정보"):
        assert tag_region(text) is None, text
