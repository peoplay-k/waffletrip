"""JSON API 를 Item 으로 바꾼다.

API 마다 응답 모양이 다르므로 공통 파서를 만들 수 없다.
소스 id 로 핸들러를 찾는 레지스트리를 두고, 모르는 id 는 조용히 넘기지 않고
예외를 던진다 — sources.yaml 에 소스를 추가하고 핸들러를 잊는 사고를 막는다.
"""
from __future__ import annotations

from src.models import Item, make_id, title_hash
from src.region_tag import tag_region
from src.sources import Source

USER_AGENT = "WaffleTripBot/1.0 (+https://waffletrip.com/about/)"
TIMEOUT = 15.0

# 제주는 원화권이라 환율 항목이 없다.
CURRENCY_BY_REGION = {
    "guam": "USD",
    "saipan": "USD",
    "hawaii": "USD",
    "vietnam": "VND",
    "kota": "MYR",
    "laos": "LAK",
}


class UnknownJsonSource(Exception):
    """sources.yaml 에는 있는데 핸들러가 없는 JSON 소스."""


def _parse_exchange_rate(source: Source, payload: dict,
                         collected_at: str) -> list[Item]:
    """open.er-api.com 응답을 지역별 환율 항목으로 바꾼다.

    응답의 rates 는 '1 KRW 당 외화'이므로 역수를 취해 '외화 1단위당 원'으로 만든다.
    여행자가 실제로 쓰는 방향이 그쪽이다.
    """
    rates = payload.get("rates") or {}
    day = collected_at[:10]
    items: list[Item] = []

    for region, currency in CURRENCY_BY_REGION.items():
        rate = rates.get(currency)
        if not rate:  # 없거나 0 — 0 이면 나눌 수 없다
            continue

        krw = 1 / rate
        title = f"오늘의 환율 — 1 {currency}"
        summary = f"{day} 기준 1 {currency} = 약 {krw:,.0f}원"

        items.append(Item(
            id=make_id("", f"fx|{region}|{currency}", day),
            grade="A",
            region=region,
            section="data",
            title=title,
            summary=summary,
            source_name=source.name,
            source_url=source.url,
            published_at=collected_at,
            collected_at=collected_at,
            status="draft",
            title_hash=title_hash(f"{title}|{region}|{day}"),
        ))

    return items


HANDLERS = {
    "exchange_rate": _parse_exchange_rate,
}


def parse_json(source: Source, payload: dict, collected_at: str) -> list[Item]:
    handler = HANDLERS.get(source.id)
    if handler is None:
        raise UnknownJsonSource(
            f"JSON 소스 '{source.id}' 의 핸들러가 없다. "
            f"src/fetch/json_api.py 의 HANDLERS 에 추가하라.")
    return handler(source, payload, collected_at)


def fetch(source: Source, client, collected_at: str) -> list[Item]:
    response = client.get(
        source.url, timeout=TIMEOUT, follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return parse_json(source, response.json(), collected_at)
