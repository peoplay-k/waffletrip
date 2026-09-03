"""서명. 사람 이름을 지어내지 않는 것이 이 모듈의 존재 이유다."""
from __future__ import annotations

from src.desks import BRAND, DATA_DESK, REGION_DESKS, byline_for
from src.models import REGIONS, Item, title_hash


def make(grade="C", region="guam", source_name=""):
    return Item(id="x", grade=grade, region=region, section="news", title="제목",
                summary="", source_name=source_name, source_url="",
                published_at="2026-09-02", collected_at="2026-09-02",
                status="published", title_hash=title_hash("제목"))


def test_curation_keeps_the_original_outlet():
    """남의 기사를 우리가 쓴 것처럼 보이게 만들면 안 된다."""
    assert byline_for(make("B", source_name="제주의소리")) == "제주의소리"


def test_data_goes_to_the_data_desk():
    assert byline_for(make("A")) == DATA_DESK


def test_commentary_goes_to_the_region_desk():
    assert byline_for(make("C", region="hawaii")) == "와플트립 하와이 데스크"


def test_named_writer_is_respected():
    """필자가 정해지면 데스크가 그 이름을 덮지 않는다."""
    assert byline_for(make("C", source_name="신창면")) == "신창면"


def test_every_region_has_a_desk():
    assert set(REGION_DESKS) == set(REGIONS)


def test_no_desk_looks_like_a_personal_name():
    """부서명이어야 한다. 사람 이름으로 읽히면 지어낸 기자가 된다."""
    for name in list(REGION_DESKS.values()) + [DATA_DESK]:
        assert name.startswith(BRAND)
        assert name.endswith(("데스크", "데이터팀", "편집팀"))


def test_every_desk_declares_how_it_makes_articles():
    """자동인지 사람이 쓰는지 밝힌다. 독자가 알 수 있어야 한다."""
    from src.desks import DESK_DUTIES
    from src.models import REGIONS
    # 지역 데스크 + 데이터팀 + 편집팀. 숫자를 박아두면 지역을 늘릴 때마다 깨진다.
    assert len(DESK_DUTIES) == len(REGIONS) + 2
    for name, duty, how in DESK_DUTIES:
        assert how in ("자동", "사람"), (name, how)
        assert duty.strip()


def test_desk_list_covers_every_region():
    from src.desks import DESK_DUTIES, REGION_DESKS
    listed = {n for n, _, _ in DESK_DUTIES}
    for desk in REGION_DESKS.values():
        assert desk in listed, desk
