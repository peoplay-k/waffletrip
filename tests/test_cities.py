"""도시 페이지 규칙."""
from src.cities import (CITIES, CITY_NAMES, CITY_REGION, MIN_ARTICLES,
                        cities_of, group_by_city)
from src.models import REGIONS


class FakeItem:
    def __init__(self, title, summary="", grade="B"):
        self.title, self.summary, self.grade = title, summary, grade


def test_every_city_belongs_to_a_region_we_cover():
    """다루지 않는 지역의 도시 페이지를 만들면 지역면 링크가 깨진다."""
    for slug, _, region, _ in CITIES:
        assert region in REGIONS, f"{slug} 의 지역 {region} 을 다루지 않는다"


def test_slugs_and_names_are_unique():
    slugs = [c[0] for c in CITIES]
    assert len(slugs) == len(set(slugs))
    assert len(CITY_NAMES) == len(CITIES) == len(CITY_REGION)


def test_airport_names_count_as_the_city():
    """'하네다 증편'은 도쿄 기사다. 공항 이름으로만 쓴 기사를 놓치면 안 된다."""
    assert "tokyo" in cities_of(FakeItem("하네다 노선 증편"))
    assert "osaka" in cities_of(FakeItem("간사이공항 이용객 회복"))


def test_one_article_can_belong_to_two_cities():
    got = cities_of(FakeItem("도쿄·오사카 노선 동시 증편"))
    assert "tokyo" in got and "osaka" in got


def test_thin_cities_get_no_page():
    """기사 몇 건짜리 페이지를 찍어내면 사이트 전체 평가가 내려간다."""
    items = [FakeItem("도쿄 여행 기사")] * MIN_ARTICLES
    items += [FakeItem("가오슝 여행 기사")] * (MIN_ARTICLES - 1)
    got = group_by_city(items)
    assert "tokyo" in got
    assert "kaohsiung" not in got


def test_exchange_rate_rows_never_become_city_articles():
    """A등급은 지역 단위 데이터다. 도시 페이지에 넣으면 같은 값이 반복된다."""
    items = [FakeItem("오늘의 환율 — 100 JPY", "도쿄", grade="A")] * 40
    assert group_by_city(items) == {}


def test_every_region_has_a_korean_name():
    """이름표가 빠지면 지면에 "이번 주 japan에서 나온 소식"이 나간다.
    실제로 일본·태국·대만을 열었을 때 그렇게 나갔다."""
    from src.models import REGION_NAMES
    for region in REGIONS:
        assert region in REGION_NAMES, f"{region} 의 한글 이름이 없다"
        assert REGION_NAMES[region] != region


def test_region_names_has_one_definition():
    """모듈마다 따로 적어두면 반드시 어긋난다."""
    from src.autowrite import REGION_NAMES as a
    from src.render.site import REGION_NAMES as b
    from src.models import REGION_NAMES as c
    assert a is c and b is c
