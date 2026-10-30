"""사이트 구조 파일(config/site.json) — 편집실이 고치는 정본(2026-10-30)."""
import copy
import json
import os

from src import site_config as sc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE = os.path.join(ROOT, "config", "site.json")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "site.json")


def _live():
    with open(LIVE, encoding="utf-8") as f:
        return json.load(f)


def test_live_config_is_valid():
    """사장님이 편집실에서 고친 진짜 파일. 값은 묻지 않고 규칙만 본다 — 형식·중복·참조."""
    assert sc.validate(_live()) == []


def test_tests_run_on_the_frozen_copy():
    """시험은 얼린 사본으로 돈다(conftest). 진짜 파일을 바꿔도 시험이 깨지지 않는다."""
    assert os.path.samefile(os.environ["SITE_CONFIG"], FIXTURE)


def test_validate_catches_broken_structure():
    cfg = json.load(open(FIXTURE, encoding="utf-8"))
    assert sc.validate(cfg) == []
    bad = copy.deepcopy(cfg)
    bad["culture_sections"].append(dict(bad["culture_sections"][0]))        # 같은 id 두 번
    bad["regions"][0]["id"] = "Guam!"                                       # 형식
    bad["reporters"][0]["beats"].append("nowhere")                          # 없는 지면
    bad["culture_rules"][0]["section"] = "gone"                             # 없는 부문
    bad["home"]["hero_count"] = 99
    bad["home"]["order"] = ["travel", "ads"]
    problems = " ".join(sc.validate(bad))
    for word in ("두 번", "형식", "nowhere", "gone", "hero_count", "ads"):
        assert word in problems, word


def test_derived_values_follow_the_file():
    """편집실에서 바꾼 것이 그대로 지면 상수가 된다 — 이름·순서·숨김·새 지역."""
    cfg = json.load(open(FIXTURE, encoding="utf-8"))
    cfg["culture_sections"][0]["name"] = "시네마"
    cfg["travel_sections"].reverse()
    cfg["travel_sections"][0]["visible"] = False
    cfg["regions"].append({"id": "philippines", "name": "필리핀", "keywords": ["필리핀", "세부"],
                           "visible": True})
    cfg["regions"][0]["visible"] = False
    assert sc.culture_sections(cfg)[0][1] == "시네마"
    assert [t[0] for t in sc.travel_sections(cfg)] == [s["id"] for s in cfg["travel_sections"][1:]]
    assert "philippines" in sc.regions(cfg) and sc.region_names(cfg)["philippines"] == "필리핀"
    assert "guam" in sc.regions(cfg) and "guam" not in sc.visible_regions(cfg)   # 숨겨도 옛 주소는 산다
    assert "guam" not in sc.region_keywords(cfg)                                 # 새로 수집하지 않는다
    assert sc.region_keywords(cfg)["philippines"] == ("필리핀", "세부")
    assert "philippines" not in sc.currencies(cfg)                               # 통화 없는 지역도 된다
