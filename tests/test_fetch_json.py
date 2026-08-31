import json
from pathlib import Path

import pytest

from src.fetch.json_api import parse_json, UnknownJsonSource, CURRENCY_BY_REGION
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


def test_currency_map_covers_every_non_krw_region():
    assert set(CURRENCY_BY_REGION) == {
        "guam", "saipan", "hawaii", "vietnam", "kota", "laos"}
