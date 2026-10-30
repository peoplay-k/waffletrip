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


# ── 편집실 검사기와 같은 답을 내야 한다 ─────────────────────────────────────
# 편집실(admin/public/shared/siteconfig.js validateSite)이 통과시킨 구조를 빌드(validate)가
# 막으면 사장님이 저장한 순간 지면이 멈춘다. 반대로 편집실이 막는데 빌드가 받는 것은 불편할 뿐
# 사고는 아니다. 그래서 '편집실 통과 ⇒ 빌드 통과' 를 여러 입력으로 확인한다.

_JS = os.path.join(sc._ROOT, "admin", "public", "shared", "siteconfig.js")


def _js_validate(cfgs):
    import shutil
    import subprocess
    if not shutil.which("node"):
        import pytest
        pytest.skip("node 가 없다")
    script = (
        "const { validateSite } = await import(process.env.SITECONFIG_JS);"
        "let s=''; process.stdin.on('data', d => s += d).on('end', () => {"
        "  const out = JSON.parse(s).map(c => validateSite(c, null, {}).map(e => e.msg));"
        "  process.stdout.write(JSON.stringify(out)); });"
    )
    r = subprocess.run(["node", "--input-type=module", "-e", script],
                       env={**os.environ, "SITECONFIG_JS": "file://" + _JS},
                       input=json.dumps(cfgs), capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def _cases():
    base = json.load(open(sc.DEFAULT_PATH, encoding="utf-8"))
    out = [("그대로", base)]

    def mutate(label, fn):
        c = copy.deepcopy(base)
        fn(c)
        out.append((label, c))

    for key, lo, hi in sc.HOME_RANGES:
        mutate(f"{key} 최소", lambda c, k=key, v=lo: c["home"].__setitem__(k, v))
        mutate(f"{key} 최대", lambda c, k=key, v=hi: c["home"].__setitem__(k, v))
        mutate(f"{key} 최대+1", lambda c, k=key, v=hi + 1: c["home"].__setitem__(k, v))
        mutate(f"{key} 최소-1", lambda c, k=key, v=lo - 1: c["home"].__setitem__(k, v))
    for cur in list(sc.CURRENCIES) + ["EUR", "usd", "KRW"]:
        mutate(f"통화 {cur}", lambda c, v=cur: c["regions"][0].__setitem__("currency", v))
    mutate("통화 없음", lambda c: c["regions"][0].pop("currency", None))
    mutate("여행 부문 전부 숨김", lambda c: [s.__setitem__("visible", False) for s in c["travel_sections"]])
    mutate("문화 부문 전부 숨김", lambda c: [s.__setitem__("visible", False) for s in c["culture_sections"]])
    mutate("지역 전부 숨김", lambda c: [r.__setitem__("visible", False) for r in c["regions"]])
    mutate("지역 하나만 보임", lambda c: [r.__setitem__("visible", i == 0) for i, r in enumerate(c["regions"])])
    mutate("날씨 위도 틀림", lambda c: c["regions"][0].__setitem__("weather", {"city": "x", "lat": 95, "lon": 0}))
    mutate("날씨 도시 비움", lambda c: c["regions"][0].__setitem__("weather", {"city": "", "lat": 1, "lon": 1}))
    mutate("날씨 정상", lambda c: c["regions"][0].__setitem__("weather", {"city": "Agana", "lat": 13.5, "lon": 144.8}))
    mutate("id 대문자", lambda c: c["travel_sections"][0].__setitem__("id", "News"))
    mutate("id 겹침", lambda c: c["regions"][1].__setitem__("id", c["regions"][0]["id"]))
    mutate("이름 비움", lambda c: c["culture_sections"][0].__setitem__("name", " "))
    mutate("규칙이 없는 부문", lambda c: c["culture_rules"][0].__setitem__("section", "nope"))
    mutate("옛 이름표가 없는 부문", lambda c: c["culture_aliases"].__setitem__("x", "nope"))
    mutate("기자 담당이 없는 지면", lambda c: c["reporters"][0]["beats"].append("mars"))
    mutate("기본 기자가 명단 밖", lambda c: c.__setitem__("general_reporter", "아무개"))
    mutate("기자 이름 겹침", lambda c: c["reporters"].append(dict(c["reporters"][0])))
    mutate("홈 순서에 모르는 칸", lambda c: c["home"]["order"].append("ads"))
    mutate("채널 이름 비움", lambda c: c["channels"]["ent"].__setitem__("name", ""))
    mutate("채널 소개 바꿈", lambda c: c["channels"]["travel"].__setitem__("desc", "열 곳의 여행 소식"))
    mutate("새 지역 추가", lambda c: c["regions"].append({"id": "philippines", "name": "필리핀", "keywords": ["필리핀", "세부"], "visible": True}))
    mutate("새 여행 부문 추가", lambda c: c["travel_sections"].append({"id": "cruise", "name": "크루즈", "desc": "", "visible": True}))
    return out


def test_편집실이_통과시킨_구조는_빌드도_받는다():
    cases = _cases()
    js = _js_validate([c for _, c in cases])
    disagreements = []
    for (label, cfg), js_errs in zip(cases, js):
        py_errs = sc.validate(cfg)
        if js_errs and not py_errs:
            continue  # 편집실이 더 깐깐한 것은 괜찮다
        if bool(py_errs) != bool(js_errs):
            disagreements.append((label, py_errs, js_errs))
    assert not disagreements, disagreements


def test_통화_목록은_환율_고시_단위와_같다():
    from src.fetch.json_api import QUOTE_UNIT
    assert set(sc.CURRENCIES) == set(QUOTE_UNIT)
