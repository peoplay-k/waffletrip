import json
from pathlib import Path

import pytest

from src.fetch.json_api import (parse_json, UnknownJsonSource,
                                CURRENCY_BY_REGION, QUOTE_UNIT)
from src.sources import Source

FIXTURE = Path(__file__).parent / "fixtures" / "exchange_rate.json"
NOW = "2026-08-31T05:00:00+09:00"

FX = Source(id="exchange_rate", region="all", section="data", name="환율",
            type="json", url="https://example.com/fx", lang="en", enabled=True)


def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_produces_one_item_per_foreign_currency_region():
    items = parse_json(FX, payload(), NOW)
    # 제주는 원화권이라 환율 항목이 없다
    assert {i.region for i in items} == {
        "guam", "saipan", "hawaii", "vietnam", "kota", "laos"}


def test_all_items_are_grade_a_data():
    items = parse_json(FX, payload(), NOW)
    assert all(i.grade == "A" for i in items)
    assert all(i.section == "data" for i in items)


def test_converts_to_krw_per_unit_of_foreign_currency():
    items = parse_json(FX, payload(), NOW)
    guam = next(i for i in items if i.region == "guam")
    # 1 KRW = 0.00072 USD  →  1 USD = 1388.89 KRW
    assert "1,389원" in guam.summary


def test_title_names_the_currency_pair():
    items = parse_json(FX, payload(), NOW)
    guam = next(i for i in items if i.region == "guam")
    assert guam.title == "오늘의 환율 — 1 USD"


def test_low_value_currencies_are_quoted_per_hundred_units():
    """1 VND 는 0.05원이라 1단위로 쓰면 반올림해서 '0원'이 된다.

    0원은 정보가 아니라 오보다. 은행 고시처럼 100단위로 묶어 보여준다.
    """
    items = parse_json(FX, payload(), NOW)
    vietnam = next(i for i in items if i.region == "vietnam")
    assert vietnam.title == "오늘의 환율 — 100 VND"
    assert "0원" != vietnam.summary.split("약 ")[1]
    assert "5.3원" in vietnam.summary   # 100 / 18.9


def test_low_value_currency_shows_one_decimal():
    """100원 밑에서는 소수 한 자리를 보여준다. 6원과 6.2원은 다르다."""
    items = parse_json(FX, payload(), NOW)
    laos = next(i for i in items if i.region == "laos")
    assert "6.4원" in laos.summary   # 100 / 15.6


def test_normal_currencies_keep_the_single_unit_quote():
    """달러·링깃은 1단위 그대로다. 100단위로 바꾸면 오히려 읽기 어렵다."""
    items = parse_json(FX, payload(), NOW)
    guam = next(i for i in items if i.region == "guam")
    kota = next(i for i in items if i.region == "kota")
    assert guam.title == "오늘의 환율 — 1 USD"
    assert kota.title == "오늘의 환율 — 1 MYR"
    # 환산 숫자까지 본다. 제목만 보면 계산이 틀려도 통과한다 — 이번 태스크의
    # "1 VND = 0원" 버그가 정확히 그렇게 살아남았다.
    assert "312원" in kota.summary   # 1 / 0.0032 = 312.5, 픽스처 기준



def test_ids_are_unique_per_region_and_day():
    items = parse_json(FX, payload(), NOW)
    assert len({i.id for i in items}) == len(items)


def test_skips_currency_missing_from_payload():
    data = payload()
    del data["rates"]["LAK"]
    items = parse_json(FX, data, NOW)
    assert "laos" not in {i.region for i in items}


def test_skips_zero_rate_without_dividing_by_zero():
    data = payload()
    data["rates"]["MYR"] = 0
    items = parse_json(FX, data, NOW)
    assert "kota" not in {i.region for i in items}


def test_unknown_source_id_raises():
    unknown = Source(id="mystery", region="all", section="data", name="?",
                     type="json", url="https://example.com", lang="en",
                     enabled=True)
    with pytest.raises(UnknownJsonSource, match="mystery"):
        parse_json(unknown, {}, NOW)


def test_every_currency_has_a_quote_unit():
    """새 지역을 넣으며 고시 단위를 잊으면 그 소스의 수집이 통째로 죽는다.

    조용한 기본값으로 때우지 않기로 했으므로(주석 참고) 이 어긋남을 잡는 것은
    이 테스트뿐이다. 개발 시점에 잡히는 것이 운영에서 환율 패널이 사라지는 것보다 낫다.
    """
    assert set(CURRENCY_BY_REGION.values()) <= set(QUOTE_UNIT)


def test_currency_map_covers_every_non_krw_region():
    assert set(CURRENCY_BY_REGION) == {
        "guam", "saipan", "hawaii", "vietnam", "kota", "laos"}
