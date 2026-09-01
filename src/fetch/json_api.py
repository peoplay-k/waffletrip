"""JSON API 를 Item 으로 바꾼다.

API 마다 응답 모양이 다르므로 공통 파서를 만들 수 없다.
소스 id 로 핸들러를 찾는 레지스트리를 두고, 모르는 id 는 조용히 넘기지 않고
예외를 던진다 — sources.yaml 에 소스를 추가하고 핸들러를 잊는 사고를 막는다.
"""
from __future__ import annotations

from src.models import Item, make_id, title_hash
from src.sources import Source

USER_AGENT = "WaffleTripBot/1.0 (+https://waffletrip.com/about/)"
TIMEOUT = 15.0

# 저액면 통화는 1단위 환율이 1원에 못 미쳐 그대로 쓰면 "1 VND = 약 0원"이 된다.
# 실제로 1 VND ≈ 0.053원, 1 LAK ≈ 0.062원이다. 은행 고시 방식대로 100단위로 묶는다.
QUOTE_UNIT = {"USD": 1, "MYR": 1, "VND": 100, "LAK": 100}
# CURRENCY_BY_REGION 에 통화를 추가하고 여기를 잊으면 KeyError 가 난다. 일부러
# .get(currency, 1) 같은 조용한 기본값을 두지 않는다 — 그러면 미래의 저액면 통화가
# 1단위로 표시되어 "1 VND = 약 0원" 오보를 그대로 되풀이한다. 어긋남은 테스트가
# 개발 시점에 잡는다(test_every_currency_has_a_quote_unit).

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

        unit = QUOTE_UNIT[currency]
        krw = unit / rate
        # 100원 밑이면 소수 한 자리까지 보여준다. 반올림해서 0원이 되면 정보가 아니다.
        shown = f"{krw:,.0f}" if krw >= 100 else f"{krw:,.1f}"
        title = f"오늘의 환율 — {unit} {currency}"
        summary = f"{day} 기준 {unit} {currency} = 약 {shown}원"

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


# ── 날씨 ──────────────────────────────────────────────────────────
# Open-Meteo 는 인증키가 필요 없다. 공공데이터포털 키를 기다리느라 A등급이
# 환율 하나로 남아 있던 것을 메운다. 기사가 하루 1~2건인 사이판·코타·라오스
# 페이지가 특히 이걸로 산다.
#
# 응답은 요청한 좌표 순서대로 배열이 온다. 그런데 **순서에 의존하지 않는다** —
# sources.yaml 의 URL 을 누가 고치면 지역이 통째로 뒤바뀌고, 그 오보를 아무도
# 눈치채지 못한다. 응답이 돌려주는 좌표로 지역을 되찾는다.
WEATHER_SITES = (
    ("guam", "하갓냐", 13.4443, 144.7937),
    ("saipan", "사이판", 15.1850, 145.7467),
    ("hawaii", "호놀룰루", 21.3069, -157.8583),
    ("vietnam", "다낭", 16.0544, 108.2022),
    ("kota", "코타키나발루", 5.9804, 116.0735),
    ("laos", "비엔티안", 17.9757, 102.6331),
    ("jeju", "제주", 33.4996, 126.5312),
)

# 좌표는 API 가 격자에 맞춰 반올림해 돌려준다. 0.5도면 이웃 지역과 섞이지 않으면서
# 반올림 오차를 흡수한다 (가장 가까운 두 지점이 8도 이상 떨어져 있다).
_COORD_TOLERANCE = 0.5

# WMO 기상 코드. 없는 코드는 그대로 두지 않고 "기타"로 흘린다 — 날씨 한 칸 때문에
# 그날 데이터 패널 전체가 빠지는 것이 더 나쁘다.
_WMO = {
    0: "맑음", 1: "대체로 맑음", 2: "구름 조금", 3: "흐림",
    45: "안개", 48: "짙은 안개",
    51: "약한 이슬비", 53: "이슬비", 55: "강한 이슬비",
    56: "어는 이슬비", 57: "강한 어는 이슬비",
    61: "약한 비", 63: "비", 65: "강한 비",
    66: "어는 비", 67: "강한 어는 비",
    71: "약한 눈", 73: "눈", 75: "강한 눈", 77: "싸락눈",
    80: "소나기", 81: "강한 소나기", 82: "매우 강한 소나기",
    85: "소낙눈", 86: "강한 소낙눈",
    95: "뇌우", 96: "우박 동반 뇌우", 99: "강한 우박 동반 뇌우",
}


def _site_for(lat: float, lon: float):
    """응답 좌표로 지역을 되찾는다. 배열 순서를 믿지 않는다."""
    for region, city, site_lat, site_lon in WEATHER_SITES:
        if (abs(site_lat - lat) <= _COORD_TOLERANCE
                and abs(site_lon - lon) <= _COORD_TOLERANCE):
            return region, city
    return None


def _parse_weather(source: Source, payload, collected_at: str) -> list[Item]:
    """Open-Meteo 일별 예보를 지역별 A등급 항목으로 바꾼다."""
    entries = payload if isinstance(payload, list) else [payload]
    day = collected_at[:10]
    items: list[Item] = []

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        site = _site_for(entry.get("latitude"), entry.get("longitude"))
        if site is None:
            continue                      # 모르는 좌표는 조용히 버린다
        region, city = site

        daily = entry.get("daily") or {}
        try:
            high = daily["temperature_2m_max"][0]
            low = daily["temperature_2m_min"][0]
        except (KeyError, IndexError, TypeError):
            continue                      # 기온이 없으면 날씨 항목이 아니다
        if high is None or low is None:
            continue

        rain = _first(daily.get("precipitation_probability_max"))
        sky = _WMO.get(_first(daily.get("weather_code")), "기타")

        title = f"오늘의 날씨 — {city}"
        summary = f"{day} {city} {sky}, 최고 {high:.0f}°C · 최저 {low:.0f}°C"
        if rain is not None:
            summary += f" · 강수확률 {rain:.0f}%"

        items.append(Item(
            id=make_id("", f"wx|{region}", day),
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


def _first(seq):
    try:
        return seq[0]
    except (TypeError, IndexError):
        return None


HANDLERS = {
    "exchange_rate": _parse_exchange_rate,
    "weather": _parse_weather,
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
