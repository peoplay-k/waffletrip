from src.relevance import is_travel_related, TRAVEL_KEYWORDS


def test_travel_articles_pass():
    for text in (
        "진에어 괌 노선 신규 취항",
        "다낭 신규 리조트 오픈",
        "괌 투몬 해변 스노클링 명소 정리",
        "First Alert Forecast: Tropical Storm Lowell strengthening",
        "제주 해수욕장 순찰·계도요원 배치",
    ):
        assert is_travel_related(text), text


def test_words_containing_travel_terms_are_not_travel():
    """여행 단어를 품었다고 여행 기사는 아니다.

    실측 오탐: "여권통문"(1898년 여성인권선언)이 여권으로, "제2공항"이 공항으로
    잡혀 정치·행정 기사가 여행 신문에 실렸다.
    """
    assert not is_travel_related("제주 양성평등주간 여권통문의 날 기념")
    assert not is_travel_related("제2공항 건설 '도민 결정권'...출발부터 '삐걱'")
    assert not is_travel_related("[사설] 한국공항공사 제주로 이전해야")


def test_real_airport_and_passport_articles_still_pass():
    """제외 규칙이 진짜 기사까지 먹으면 안 된다."""
    assert is_travel_related("인천공항 3터미널 개장 일정 확정")
    assert is_travel_related("여권 발급 수수료 인하")


def test_english_keywords_use_word_boundaries():
    """부분일치를 허용하면 "travel" 이 엉뚱한 단어에 걸린다."""
    assert is_travel_related("Korean Air launched a new route to Guam")
    assert is_travel_related("The couple travelled across Vietnam")   # 영국식
    assert is_travel_related("The couple traveled across Vietnam")    # 미국식
    assert is_travel_related("Travelling to Guam next month")
    assert not is_travel_related("Local council approves new budget")


def test_known_misses_are_documented():
    """알면서 놓치는 것들. 이 필터는 완벽하지 않다.

    "Guam Micronesia Island Fair" 는 관광객이 갈 만한 행사인데 여행 단어가 없다.
    "fair" 를 키워드로 넣으면 공정성·박람회 기사가 함께 통과해서 넣지 않았다.
    1차 방어선은 소스 선정이고 이 필터는 그 뒤를 받는 그물이라, 이런 건 놓친다.
    놓치는 쪽으로 틀리는 것이 살인 기사를 싣는 것보다 낫다.
    """
    assert not is_travel_related(
        "Guam Micronesia Island Fair to celebrate Pacific cultures")


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


def test_crime_reports_are_flagged():
    """사건 기사는 여행지 이름이 배경으로 나올 뿐 여행 정보가 아니다.

    실측: 하와이 지면에 "호텔 직원 성범죄 유죄"가 hotel 로,
    "식당 살인미수"가 restaurant 로 통과해 실렸다.
    """
    from src.relevance import is_crime_report
    for text in (
        "'A predator and a pervert': Former hotel clerk convicted of sexual assault",
        "Former attorney convicted of attempted murder after restaurant shooting",
        "호텔 직원 성추행 혐의로 구속",
    ):
        assert is_crime_report(text), text


def test_useful_travel_news_is_not_flagged_as_crime():
    """넓은 말을 넣으면 쓸모 있는 기사까지 막는다.

    수하물 분실 소송과 기내 난동 승객 체포는 여행자가 알아야 할 일이다.
    """
    from src.relevance import is_crime_report
    for text in (
        "$521K Hawaii Airport Lawsuit Exposes Checked Bag Risk",
        "Passenger arrested after being restrained with duct tape",
        "'안전문자 41건' 제주 해수욕장 사망사고는 0건",
        "진에어 괌 노선 신규 취항",
    ):
        assert not is_crime_report(text), text


# ── 재난·교통 경보는 여행 뉴스다 ───────────────────────────────────────
# 2026-09-09 실측: 허리케인 로웰 고속도로 통제·정전 보도가 전부 탈락했다.

def test_재난_교통_경보는_여행_관련이다():
    from src.relevance import is_travel_related
    for t in ("Severe storm damage shuts down major Kauai highways, roads",
              "33,000 without power on Kauai after hurricane damages electric grid",
              "Flights canceled, airports shut over Indonesia volcanic eruption",
              "제주 태풍 북상에 여객선 전면 결항"):
        assert is_travel_related(t), t


def test_영문_음주운전은_범죄_보도다():
    from src.relevance import is_crime_report
    assert is_crime_report("Restaurant owner charged with DUI after deadly pedestrian crash")
    assert not is_crime_report("Restaurant week returns to Waikiki with 40 venues")


# ── 카지노 스팸 ──────────────────────────────────────────────────────
# 2026-09-09 실측: 구글뉴스 "호텔" 검색에 카지노 홍보 글이 하루 33건 섞여 왔다.

def test_카지노_스팸은_거른다():
    from src.relevance import is_spam
    assert is_spam("도쿄 호텔 카지노 의 역사와 발전: 과거에서 현재까지 - 전문가의 관점에서")
    assert is_spam("오사카 호텔 카지노 : 완벽한 비교 가이드 (2025년 최신판)")
    assert is_spam("Guam hotel deals", source_name="Histoire pour tous")


def test_보통_호텔_기사는_스팸이_아니다():
    from src.relevance import is_spam
    assert not is_spam("힐튼, 방콕과 후쿠오카에 새 호텔 오픈", source_name="싱글리스트")


def test_블로그_플랫폼_글은_출처만_보고_버린다():
    """브런치·네이버 블로그 글이 구글뉴스 검색 피드로 들어온다. 뉴스가 아니다."""
    assert is_spam("하와이 호텔 추천 리스트 5선 총정리", source_name="브런치")
    assert is_spam("롯데면세점, 괌공항서 철수", source_name="네이버 블로그 | 딜사이트")
    assert not is_spam("롯데면세점, 괌공항서 철수", source_name="딜사이트")
