"""sources.yaml 을 읽어 검증된 Source 목록으로 만든다.

이 모듈은 네트워크를 모른다. 파일을 읽고 스키마를 검증할 뿐이다.
"""
from dataclasses import dataclass

import yaml

# 지역 목록은 src/models.py 가 정본이다. 두 곳에 적어두면 반드시 어긋난다 —
# 실제로 지역을 늘렸는데 여기가 옛 목록이라 소스 등록이 막혔다.
from src.models import CHANNELS, REGIONS as _MODEL_REGIONS
from src.topics import ENT_ALIASES, ENT_TOPIC_NAMES

REGIONS = _MODEL_REGIONS + ("all", "auto")
SECTIONS = ("flight", "news", "data", "promo")
TYPES = ("rss", "json")
REQUIRED = ("id", "region", "section", "name", "type", "url", "lang", "enabled")


class SourceConfigError(Exception):
    """sources.yaml 이 규칙을 어겼다."""


@dataclass(frozen=True)
class Source:
    id: str
    region: str
    section: str
    name: str
    type: str
    url: str
    lang: str
    enabled: bool
    curated: bool = False
    # 채널. 기본은 여행. 연예 소스(channel: ent)는 지역 판정을 건너뛰고 category 를 싣는다.
    channel: str = "travel"
    category: str = ""
    # region: auto 소스에서 지명이 안 잡힌 기사를 여행업계면으로 받을지.
    # 여행 전문지는 받는다. 종합 보도자료가 섞인 곳(TTL뉴스 — 2026-10-15 실측 37건 중
    # 27건이 금융·교육청·식품 보도자료)은 sources.yaml 에서 industry: false 로 끈다.
    industry: bool = True
    # region: auto 소스에서 여행 기사가 아닌 것 가운데 문화(영화·공연·전시·방송) 발표를 문화 채널로
    # 받을지. 문화뉴스처럼 여행면과 문화면이 한 피드로 오는 매체용(2026-10-30 사장님: "여행 기사 더
    # 만들어 … 여기 기사들 많은데 뭐하는거야? 좀 챙겨서 가지고와서 좀 올려"). 지명·여행 말이 있으면
    # 여행이 먼저다 — 문화는 그다음이다(src/fetch/rss.py).
    culture: bool = False


def load_sources(path: str) -> list[Source]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    entries = raw.get("sources") or []
    seen: set[str] = set()
    result: list[Source] = []

    for i, e in enumerate(entries):
        where = f"sources[{i}]"
        missing = [k for k in REQUIRED if k not in e]
        if missing:
            raise SourceConfigError(f"{where}: 필수 항목 누락 {missing}")

        sid = e["id"]
        if sid in seen:
            raise SourceConfigError(f"{where}: id 중복 '{sid}'")
        seen.add(sid)

        if e["region"] not in REGIONS:
            raise SourceConfigError(
                f"{where}: 알 수 없는 region '{e['region']}' (허용: {REGIONS})")
        if e["section"] not in SECTIONS:
            raise SourceConfigError(
                f"{where}: 알 수 없는 section '{e['section']}' (허용: {SECTIONS})")
        if e["type"] not in TYPES:
            raise SourceConfigError(
                f"{where}: 알 수 없는 type '{e['type']}' (허용: {TYPES})")

        channel = e.get("channel", "travel")
        if channel not in CHANNELS:
            raise SourceConfigError(
                f"{where}: 알 수 없는 channel '{channel}' (허용: {CHANNELS})")
        category = e.get("category", "") or ""
        if channel == "ent" and category and category not in ENT_TOPIC_NAMES and category not in ENT_ALIASES:
            raise SourceConfigError(
                f"{where}: 알 수 없는 연예 부문 '{category}' (허용: {tuple(ENT_TOPIC_NAMES)})")

        culture = bool(e.get("culture", False))
        if culture and (e["region"] != "auto" or channel != "travel"):
            raise SourceConfigError(
                f"{where}: culture 는 region: auto 인 여행 소스에만 둔다 — 기사마다 채널을 가르는 것이라 "
                f"지역이 고정된 소스나 연예 소스에는 뜻이 없다")

        if not e["enabled"]:
            continue

        result.append(Source(
            id=sid, region=e["region"], section=e["section"], name=e["name"],
            type=e["type"], url=e["url"], lang=e["lang"], enabled=True,
            curated=bool(e.get("curated", False)),
            channel=channel, category=category if channel == "ent" else "",
            industry=bool(e.get("industry", True)),
            culture=culture,
        ))

    return result
