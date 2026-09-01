from src.relevance import is_travel_related, TRAVEL_KEYWORDS


def test_travel_articles_pass():
    for text in (
        "진에어 괌 노선 신규 취항",
        "다낭 신규 리조트 오픈",
        "Guam Micronesia Island Fair to celebrate Pacific cultures",
        "First Alert Forecast: Tropical Storm Lowell strengthening",
        "제주 해수욕장 순찰·계도요원 배치",
    ):
        assert is_travel_related(text), text


def test_local_politics_and_crime_are_dropped():
    """여행 신문 1면에 살인과 선거가 실리던 것을 막는 장치다."""
    for text in (
        "Teen shot and killed by her ex-boyfriend, police say",
        "Man suffers burns as fire spreads to nine factory lots",
        "Guam Republicans up the ante; former governors join campaign",
        "Autonomous salary structure proposed for Guam education department",
        "Kennedy reappointed as federal magistrate judge",
    ):
        assert not is_travel_related(text), text


def test_park_does_not_match_parked_or_parks():
    """"park" 를 키워드로 두면 주차된 차 사고와 공원 민원이 통과한다.

    실측에서 정확히 그렇게 샜다: "Woman in parked vehicle injured in hit-and-run",
    "Letter: Stop feeding feral cats, return parks to people".
    """
    assert not is_travel_related("Woman, 54, in parked vehicle injured in hit-and-run")
    assert not is_travel_related("Letter: Stop feeding feral cats, return parks to people")


def test_empty_text_is_not_travel():
    assert not is_travel_related("")
    assert not is_travel_related(None)


def test_no_keyword_is_a_bare_english_word_prone_to_substring_hits():
    """"park" 같은 단어를 다시 넣지 못하게 고정한다."""
    assert "park" not in TRAVEL_KEYWORDS
    assert "trip" not in TRAVEL_KEYWORDS   # "a 10-day trip" (외교 순방) 오탐
