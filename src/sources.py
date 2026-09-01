"""sources.yaml 을 읽어 검증된 Source 목록으로 만든다.

이 모듈은 네트워크를 모른다. 파일을 읽고 스키마를 검증할 뿐이다.
"""
from dataclasses import dataclass

import yaml

REGIONS = ("guam", "saipan", "hawaii", "vietnam", "kota", "laos", "jeju",
           "all", "auto")
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

        if not e["enabled"]:
            continue

        result.append(Source(
            id=sid, region=e["region"], section=e["section"], name=e["name"],
            type=e["type"], url=e["url"], lang=e["lang"], enabled=True,
            curated=bool(e.get("curated", False)),
        ))

    return result
