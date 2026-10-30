"""사이트 구조 — config/site.json 을 읽는다.

2026-10-30 사장님: "어드민을 완전 새롭게 만들어서 카테고리 등도 내가 실제로 바꾸고 이렇게 해야지.
지금 너가 임의로 하는건 안 돼." 그전에는 지역·부문·기자·홈 배치가 코드에 박혀 있어 사장님이
바꿀 수 없었다. 이제 정본은 config/site.json 이고, 편집실(관리자 화면, admin/)이 그 파일을 고친다.
설계와 칸의 뜻은 docs/ADMIN_DESIGN.md.

각 모듈(models·topics·desks·region_tag·json_api·site)은 예전 이름(REGIONS, TOPICS …)을 그대로
두되 값을 여기서 받는다 — 코드의 나머지는 바뀌지 않는다.

표준 라이브러리만 쓴다. models.py 가 이것을 읽고, models.py 는 무엇에도 기대지 않는 바닥이다.
"""
from __future__ import annotations

import json
import os
import re

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(_ROOT, "config", "site.json")
ID_PATTERN = re.compile(r"^[a-z0-9-]{2,24}$")

# 홈 배치 기본값. 파일에 빠진 칸이 있어도 지면이 깨지지 않게 한다.
HOME_DEFAULTS = {
    "hero_count": 4, "travel_block_size": 11, "culture_grid": 6, "culture_block_size": 5,
    "latest_count": 10, "photo_row": 8, "show_data_strip": True, "show_photo_row": True,
    "show_video": True, "order": ["travel", "culture", "culture_sections", "latest"],
    "pinned_lead": "",
}
HOME_BLOCKS = ("travel", "culture", "culture_sections", "latest")
# 홈 숫자 칸의 허용 범위. 편집실(admin/public/shared/siteconfig.js HOME_NUMBERS)과 같아야 한다 —
# tests/test_site_config.py 가 두 검사기를 같은 입력으로 돌려 어긋남을 잡는다.
HOME_RANGES = (("hero_count", 1, 8), ("travel_block_size", 1, 30), ("culture_grid", 0, 24),
               ("culture_block_size", 1, 20), ("latest_count", 0, 30), ("photo_row", 0, 24))
# 환율을 낼 수 있는 통화. src/fetch/json_api.py QUOTE_UNIT 의 열쇠와 같다(시험이 맞춘다).
# 모르는 통화가 들어오면 수집이 KeyError 로 죽으므로 저장 전에 막는다.
CURRENCIES = ("USD", "MYR", "VND", "LAK", "JPY", "THB", "TWD")


class SiteConfigError(Exception):
    """config/site.json 이 규칙을 어겼다. 지면을 엉뚱하게 내느니 빌드를 멈춘다."""


def load(path: str | None = None) -> dict:
    path = path or os.environ.get("SITE_CONFIG") or DEFAULT_PATH
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    problems = validate(cfg)
    if problems:
        raise SiteConfigError(f"{path}: " + " / ".join(problems))
    return cfg


def validate(cfg: dict) -> list[str]:
    """틀린 곳 목록. 빈 목록이면 통과. 편집실 서버도 같은 규칙으로 저장 전에 막는다."""
    out: list[str] = []

    def ids(rows, what):
        seen = set()
        for r in rows or []:
            rid = str(r.get("id", ""))
            if not ID_PATTERN.match(rid):
                out.append(f"{what} id '{rid}' 형식이 틀렸다(영문 소문자·숫자·하이픈 2~24자)")
            if rid in seen:
                out.append(f"{what} id '{rid}' 가 두 번 있다")
            seen.add(rid)
            if not str(r.get("name", "")).strip():
                out.append(f"{what} '{rid}' 이름이 비었다")
        return seen

    for ch in ("travel", "ent"):
        if not str(((cfg.get("channels") or {}).get(ch) or {}).get("name", "")).strip():
            out.append(f"채널 {ch} 이름이 비었다")
    travel = ids(cfg.get("travel_sections"), "여행 부문")
    culture = ids(cfg.get("culture_sections"), "문화 부문")
    regions = ids(cfg.get("regions"), "지역")
    if not travel:
        out.append("여행 부문이 하나도 없다")
    if not culture:
        out.append("문화 부문이 하나도 없다")
    if not regions:
        out.append("지역이 하나도 없다")
    # 전부 숨기면 기본 부문·지역 목록이 비어 지면을 못 만든다(topics.TOPICS[0] 등)
    for key, what in (("travel_sections", "여행 부문"), ("culture_sections", "문화 부문"), ("regions", "지역")):
        rows = cfg.get(key) or []
        if rows and not any(r.get("visible", True) for r in rows):
            out.append(f"{what}을 전부 숨길 수는 없다 — 하나는 보여야 한다")
    for r in cfg.get("regions") or []:
        rid = r.get("id", "")
        cur = r.get("currency")
        if cur and cur not in CURRENCIES:
            out.append(f"지역 '{rid}' 의 통화 '{cur}' 는 환율을 낼 수 없다(가능: {', '.join(CURRENCIES)})")
        w = r.get("weather")
        if w is not None:
            ok = (isinstance(w, dict) and str(w.get("city", "")).strip()
                  and isinstance(w.get("lat"), (int, float)) and -90 <= w["lat"] <= 90
                  and isinstance(w.get("lon"), (int, float)) and -180 <= w["lon"] <= 180)
            if not ok:
                out.append(f"지역 '{rid}' 의 날씨 지점(city·lat·lon)이 틀렸다")
    for r in cfg.get("culture_rules") or []:
        if r.get("section") not in culture:
            out.append(f"문화 분류 규칙의 부문 '{r.get('section')}' 이 없다")
    for old, new in (cfg.get("culture_aliases") or {}).items():
        if new not in culture:
            out.append(f"옛 부문 '{old}' 이 가리키는 '{new}' 가 없다")
    beats_ok = regions | {"ent", "data"}
    names = set()
    for rep in cfg.get("reporters") or []:
        name = str(rep.get("name", "")).strip()
        if not name:
            out.append("이름 없는 기자가 있다")
        if name in names:
            out.append(f"기자 '{name}' 가 두 번 있다")
        names.add(name)
        for b in rep.get("beats") or []:
            if b not in beats_ok:
                out.append(f"기자 '{name}' 의 지면 '{b}' 가 없다")
    if cfg.get("general_reporter") and cfg["general_reporter"] not in names:
        out.append(f"기본 기자 '{cfg['general_reporter']}' 가 기자 명단에 없다")
    home = cfg.get("home") or {}
    for key, lo, hi in HOME_RANGES:
        if key in home and not (isinstance(home[key], int) and lo <= home[key] <= hi):
            out.append(f"홈 {key} 는 {lo}~{hi} 사이 숫자여야 한다")
    for b in home.get("order") or []:
        if b not in HOME_BLOCKS:
            out.append(f"홈 순서에 모르는 칸 '{b}'")
    return out


# ── 파생값. 모듈들이 이것으로 예전 상수를 만든다. 시험에서는 dict 를 바꿔 넣어 본다. ──

def channel_names(cfg: dict) -> dict:
    return {k: v["name"] for k, v in cfg["channels"].items()}


def regions(cfg: dict) -> tuple[str, ...]:
    """모든 지역 id(숨긴 것 포함). 옛 기사와 옛 주소가 살아 있어야 한다."""
    return tuple(r["id"] for r in cfg["regions"])


def visible_regions(cfg: dict) -> tuple[str, ...]:
    return tuple(r["id"] for r in cfg["regions"] if r.get("visible", True))


def region_names(cfg: dict) -> dict:
    return {r["id"]: r["name"] for r in cfg["regions"]}


def destinations(cfg: dict) -> tuple[str, ...]:
    return tuple(r["id"] for r in cfg["regions"] if r.get("destination", True))


def region_keywords(cfg: dict) -> dict:
    """숨긴 지역은 새로 수집하지 않는다 — 키워드를 주지 않는다."""
    return {r["id"]: tuple(r["keywords"]) for r in cfg["regions"]
            if r.get("visible", True) and r.get("keywords")}


def travel_word_regions(cfg: dict) -> tuple[str, ...]:
    return tuple(r["id"] for r in cfg["regions"] if r.get("require_travel_word"))


def travel_sections(cfg: dict) -> tuple:
    return tuple((s["id"], s["name"], s.get("desc", "")) for s in cfg["travel_sections"]
                 if s.get("visible", True))


def culture_sections(cfg: dict) -> tuple:
    return tuple((s["id"], s["name"], s.get("desc", "")) for s in cfg["culture_sections"]
                 if s.get("visible", True))


def culture_rules(cfg: dict) -> tuple:
    return tuple((r["section"], tuple(r.get("keywords") or ())) for r in cfg.get("culture_rules") or [])


def reporters(cfg: dict) -> dict:
    return {r["name"]: tuple(r.get("beats") or ()) for r in cfg.get("reporters") or []}


def currencies(cfg: dict) -> dict:
    return {r["id"]: r["currency"] for r in cfg["regions"] if r.get("currency")}


def weather_sites(cfg: dict) -> tuple:
    return tuple((r["id"], r["weather"]["city"], float(r["weather"]["lat"]), float(r["weather"]["lon"]))
                 for r in cfg["regions"] if r.get("weather"))


def desk_duties(cfg: dict) -> dict:
    return {r["id"]: r.get("desk_duty") or f"{r['name']} 지역의 기사를 맡습니다." for r in cfg["regions"]}


def home(cfg: dict) -> dict:
    return {**HOME_DEFAULTS, **(cfg.get("home") or {})}


CONFIG = load()
