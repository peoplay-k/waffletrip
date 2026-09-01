"""편집 부문 분류. 빈 메뉴를 만들지 않는 것이 이 모듈의 존재 이유다."""
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
    assert topic_of(make("오늘의 날씨 — 하갓냐", grade="A", section="data")) == "data"
    assert topic_of(make("괌 호텔 실측 기록", grade="C")) == "feature"


@pytest.mark.parametrize("title,expected", [
    ("대한항공 괌 노선 증편", "flight"),
    ("태풍 로웰 하와이 접근", "weather"),
    ("웨스틴 리조트 객실 리뉴얼", "stay"),
    ("괌 롱혼스테이크 맛집", "eat"),
    ("돌고래 투어 재개", "play"),
    ("괌 정부 인사 발표", "news"),
])
def test_korean_titles_land_in_the_right_topic(title, expected):
    assert topic_of(make(title)) == expected


@pytest.mark.parametrize("title,expected", [
    ("Airline adds new route to Guam", "flight"),
    ("Tropical Storm Lowell strengthens", "weather"),
    ("New resort opens in Saipan", "stay"),
    ("This Maui restaurant lands award", "eat"),
    ("Beach reservations required soon", "play"),
])
def test_english_titles_land_in_the_right_topic(title, expected):
    assert topic_of(make(title)) == expected


@pytest.mark.parametrize("title", [
    "He sat on a chair all day",        # air ⊄ chair
    "It was a great meeting",           # eat ⊄ great
    "Parking lot expansion approved",   # park ⊄ parking
])
def test_english_matching_uses_word_boundaries(title):
    """영문을 부분일치로 두면 chair 가 항공으로, great 가 먹거리로 간다."""
    assert topic_of(make(title)) == "news"


def test_safety_wins_over_activity():
    """해변에 난 태풍 기사는 즐길거리가 아니라 안전이다."""
    assert topic_of(make("태풍으로 해변 전면 통제")) == "weather"


def test_unmatched_goes_to_news_not_nowhere():
    """어디에도 안 걸린 기사가 사라지면 지면에서 통째로 빠진다."""
    assert topic_of(make("World's second best islands named")) == "news"


def test_group_by_topic_keeps_every_item():
    items = [make("대한항공 증편"), make("태풍 접근"), make("무관한 제목")]
    grouped = group_by_topic(items)
    assert sum(len(v) for v in grouped.values()) == len(items)


def test_every_topic_has_a_name_and_description():
    from src.topics import TOPIC_DESCS, TOPIC_NAMES
    for tid, name, desc in TOPICS:
        assert TOPIC_NAMES[tid] == name and TOPIC_DESCS[tid] == desc and desc
