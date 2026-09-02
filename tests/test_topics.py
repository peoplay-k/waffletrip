"""편집 부문 분류. 여행신문의 지면 구성을 따른다.

빈 메뉴를 만들지 않는 것, 그리고 어떤 기사도 지면에서 사라지지 않는 것이
이 모듈이 지켜야 할 두 가지다.
"""
from __future__ import annotations

import pytest

from src.models import Item, title_hash
from src.topics import TOPICS, group_by_topic, topic_of


def make(title, grade="B", section="news", summary=""):
    return Item(id="x", grade=grade, region="guam", section=section, title=title,
                summary=summary, source_name="s", source_url="",
                published_at="2026-09-02", collected_at="2026-09-02",
                status="published", title_hash=title_hash(title))


def test_grade_beats_keywords():
    """우리가 만든 데이터와 우리가 쓴 기사는 소재와 무관하게 그 부문이다."""
    assert topic_of(make("오늘의 환율 — 1 USD", grade="A", section="data")) == "data"
    assert topic_of(make("괌 호텔 실측 기록", grade="C")) == "feature"


def test_flight_section_goes_to_biz():
    assert topic_of(make("아무 제목", section="flight")) == "biz"


@pytest.mark.parametrize("title,expected", [
    ("괌정부관광청, 제주올레와 협약 체결", "policy"),
    ("대한항공 괌 노선 증편", "biz"),
    ("태풍 로웰 하와이 접근", "issue"),
    ("신임 대표 취임 인터뷰", "people"),
])
def test_korean_titles_land_in_the_right_topic(title, expected):
    assert topic_of(make(title)) == expected


@pytest.mark.parametrize("title,expected", [
    ("Airline adds new route to Guam", "biz"),
    ("Tropical Storm Lowell strengthens", "issue"),
    ("Tourism board announces new policy", "policy"),
])
def test_english_titles_land_in_the_right_topic(title, expected):
    assert topic_of(make(title)) == expected


@pytest.mark.parametrize("title", [
    "He sat on a chair all day",          # air ⊄ chair
    "Sea turtles nest along the coast",   # 아무 규칙에도 안 걸린다
])
def test_english_matching_uses_word_boundaries(title):
    """부분일치로 두면 chair 가 여행BIZ 로 간다."""
    assert topic_of(make(title)) == "world"


def test_policy_wins_over_business():
    """관광청 발표는 업계 소식이기도 하지만 정책이 먼저다."""
    assert topic_of(make("관광청, 항공사와 노선 확대 협약")) == "policy"


def test_unmatched_goes_to_world_not_nowhere():
    """어디에도 안 걸린 기사가 사라지면 지면에서 통째로 빠진다.

    우리 기사는 전부 해외발이라 국제로 보낸다.
    """
    assert topic_of(make("World's second best islands named")) == "world"


def test_group_by_topic_keeps_every_item():
    items = [make("대한항공 증편"), make("태풍 접近"), make("무관한 제목"),
             make("데이터", grade="A", section="data")]
    grouped = group_by_topic(items)
    assert sum(len(v) for v in grouped.values()) == len(items)


def test_group_by_topic_has_a_bucket_for_every_topic():
    """부문 하나가 통째로 빠지면 네비 링크가 404 로 간다."""
    grouped = group_by_topic([])
    assert set(grouped) == {tid for tid, _, _ in TOPICS}


def test_every_topic_has_a_name_and_description():
    from src.topics import TOPIC_DESCS, TOPIC_NAMES
    for tid, name, desc in TOPICS:
        assert TOPIC_NAMES[tid] == name and TOPIC_DESCS[tid] == desc and desc


def test_topics_match_the_reference_masthead():
    """여행신문 지면 구성을 따른다. 순서가 곧 네비 순서다."""
    assert [name for _, name, _ in TOPICS] == [
        "여행BIZ", "이슈·동향", "관광정책", "기획·연재", "국제",
        "피플·오피니언", "통계·리포트"]


def test_our_data_article_goes_to_statistics_not_features():
    """자동 생성 데이터 기사는 등급이 C 지만 성격은 통계·리포트다."""
    assert topic_of(make("09월 2일 여행 데이터", grade="C", section="data")) == "data"
    assert topic_of(make("괌 답사 기록", grade="C", section="news")) == "feature"
