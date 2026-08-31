from src.grade import (classify, apply_grades, is_flight_event,
                       pick_c_candidates, MAX_C_PER_DAY)
from src.models import Item

NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, section="news", related=None):
    return Item(id=item_id, grade="B", region="guam", section=section,
                title=title, summary="s", source_name="A",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h",
                related=list(related or []))


def test_data_section_is_grade_a():
    assert classify(make("1", "오늘의 환율", section="data")) == "A"


def test_news_section_is_grade_b():
    assert classify(make("1", "괌 소식", section="news")) == "B"


def test_flight_section_is_grade_b():
    assert classify(make("1", "괌 항공 소식", section="flight")) == "B"


def test_apply_grades_mutates_in_place():
    items = [make("1", "환율", section="data"), make("2", "뉴스")]
    apply_grades(items)
    assert [i.grade for i in items] == ["A", "B"]


def test_apply_grades_moves_flight_stories_to_the_flight_section():
    items = [make("1", "진에어 괌 노선 신규 취항")]
    apply_grades(items)
    assert items[0].section == "flight"


def test_apply_grades_leaves_ordinary_news_in_news():
    items = [make("1", "투몬 해변 청소 행사")]
    apply_grades(items)
    assert items[0].section == "news"


def test_apply_grades_does_not_move_data_items():
    items = [make("1", "오늘의 환율 — 1 USD 신규 취항", section="data")]
    apply_grades(items)
    assert items[0].section == "data"


def test_is_flight_event_detects_korean_terms():
    assert is_flight_event("진에어 괌 노선 신규 취항")
    assert is_flight_event("대한항공 괌 노선 증편")
    assert is_flight_event("티웨이 괌 노선 감편 결정")


def test_is_flight_event_detects_english_terms():
    assert is_flight_event("United adds new nonstop route to Guam")
    assert is_flight_event("Korean Air to launch Guam service")


def test_english_keywords_need_word_boundaries():
    """"launch" 가 부분일치하면 군사 기사의 "launchers" 에 걸린다.

    실측에서 "U.S. forces strike two Iranian launchers" 가 항공 섹션으로
    올라오고 검수 후보까지 됐다. 여행 신문에 군사 기사가 실릴 뻔했다.
    """
    assert not is_flight_event("U.S. forces strike two Iranian launchers")
    assert not is_flight_event("New product launcher for travel agencies")


def test_english_verb_endings_still_match():
    """단어 경계를 걸어도 "launched a new route" 는 잡아야 한다."""
    assert is_flight_event("Korean Air launched a new route to Guam")
    assert is_flight_event("United launches Guam service in October")
    assert is_flight_event("Jeju Air to launch Saipan flights")


def test_korean_keywords_still_match_with_particles():
    """한국어는 조사가 붙어 오므로 부분일치를 유지한다."""
    assert is_flight_event("진에어가 괌 노선에 신규 취항한다")
    assert is_flight_event("대한항공이 괌 노선을 증편했다")


def test_is_flight_event_ignores_unrelated_titles():
    assert not is_flight_event("투몬 해변 청소 행사")


# --- 후보 선정 우선순위: ①3개 이상 매체 ②트렌드 ③항공 ---

def test_cluster_of_three_outlets_is_a_candidate():
    items = [make("1", "괌 호텔 요금 인상", related=["2", "3"])]
    picked = pick_c_candidates(items, trending=[])
    assert [i.id for i, _ in picked] == ["1"]
    assert "매체" in picked[0][1]


def test_cluster_of_two_outlets_is_not_enough():
    items = [make("1", "괌 호텔 요금 인상", related=["2"])]
    assert pick_c_candidates(items, trending=[]) == []


def test_trending_keyword_match_is_a_candidate():
    items = [make("1", "사이판 마나가하 섬 입장료 변경")]
    picked = pick_c_candidates(items, trending=["마나가하"])
    assert [i.id for i, _ in picked] == ["1"]
    assert "검색" in picked[0][1]


def test_flight_event_is_a_candidate():
    items = [make("1", "진에어 괌 노선 신규 취항", section="flight")]
    picked = pick_c_candidates(items, trending=[])
    assert [i.id for i, _ in picked] == ["1"]
    assert "항공" in picked[0][1]


def test_priority_order_when_over_the_cap():
    """상한을 넘으면 3매체 > 트렌드 > 항공 순으로 남는다."""
    items = (
        [make(f"f{i}", f"진에어 {i}호 노선 신규 취항", section="flight")
         for i in range(4)]
        + [make(f"t{i}", f"마나가하 소식 {i}") for i in range(4)]
        + [make(f"c{i}", f"클러스터 기사 {i}", related=["x", "y"])
           for i in range(4)]
    )
    picked = pick_c_candidates(items, trending=["마나가하"], max_n=5)
    ids = [i.id for i, _ in picked]
    assert len(ids) == 5
    assert ids[:4] == ["c0", "c1", "c2", "c3"]
    assert ids[4].startswith("t")


def test_never_exceeds_the_daily_cap():
    items = [make(f"c{i}", f"클러스터 {i}", related=["x", "y"])
             for i in range(20)]
    assert len(pick_c_candidates(items, trending=[])) == MAX_C_PER_DAY


def test_item_qualifying_twice_appears_once():
    items = [make("1", "진에어 괌 노선 신규 취항", section="flight",
                  related=["2", "3"])]
    picked = pick_c_candidates(items, trending=["괌"])
    assert len(picked) == 1


def test_grade_a_items_are_never_c_candidates():
    """환율 같은 사실 데이터에 해설을 붙일 이유가 없다."""
    item = make("1", "오늘의 환율 — 1 USD", section="data", related=["2", "3"])
    item.grade = "A"
    assert pick_c_candidates([item], trending=[]) == []


def test_empty_input_yields_no_candidates():
    assert pick_c_candidates([], trending=["괌"]) == []
