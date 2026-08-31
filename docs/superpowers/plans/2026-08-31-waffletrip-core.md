# 와플트립 코어 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7개 여행지의 뉴스·항공·실용데이터를 매일 자동 수집해 정적 신문 사이트로 발행하는 파이프라인을 만든다.

**Architecture:** `sources.yaml`에 정의된 소스를 `collect.py`가 병렬 수집해 `data/raw/`에 원본 JSON을 남기고, `edit.py`가 저작권·중복 가드를 통과시킨 뒤 등급을 매겨 `data/items/`에 정규화된 항목을 쌓고, `build.py`가 Jinja2로 `public/`에 정적 HTML·RSS·sitemap을 생성한다. GitHub Actions가 매일 05:00 KST에 셋을 순서대로 돌리고 Pages로 배포한다. 데이터베이스는 없고 모든 상태는 저장소 안의 파일이다.

**Tech Stack:** Python 3.11+, feedparser(RSS), httpx(HTTP), PyYAML(설정), Jinja2(템플릿), pytest(테스트), GitHub Actions + Pages(자동화·호스팅)

**Spec:** `docs/superpowers/specs/2026-08-31-play-travel-news-design.md`

## Global Constraints

모든 태스크의 요구사항에 아래가 암묵적으로 포함된다.

- **비용 0원** — 유료 API·유료 호스팅·유료 서비스를 도입하지 않는다. 무료 티어 한도를 넘는 설계를 하지 않는다.
- **Python 3.9 호환** — CI 는 3.11 을 쓰지만 사용자의 로컬 파이썬은 3.9.6 이다. 사용자가 로컬에서 사이트를 미리 보려면 3.9 에서 돌아야 한다. 모든 모듈 맨 위에 `from __future__ import annotations` 를 넣고, `str | None` 같은 3.10+ 표기는 **어노테이션에서만** 쓴다(런타임 평가 자리에 쓰지 않는다). `match` 문을 쓰지 않는다.
- **지역 키 7개 고정** — `guam`, `saipan`, `hawaii`, `vietnam`, `kota`, `laos`, `jeju`. 이 외의 값은 검증에서 거부한다.
- **소스 설정에서만 추가 허용되는 두 값** — `all`(전 지역 공통 데이터, 예: 환율)과 `auto`(기사 내용에서 지역을 추론). 항목(`Item`)의 `region`은 항상 7개 중 하나로 확정된다.
- **등급 3종** — `A`(사실 데이터), `B`(큐레이션), `C`(해설 기사). 이 외의 값은 거부한다.
- **섹션 4종** — `flight`, `news`, `data`, `promo`. 이 외의 값은 거부한다.
- **인용 상한** — B등급 `summary`는 최대 **200자** 그리고 최대 **2문장**. 초과 시 절단하지 않고 **항목을 폐기**한다.
- **출처 필수** — B등급은 `source_name`과 `source_url`이 모두 있어야 한다. 없으면 폐기.
- **원문 이미지 임베드 금지** — 수집한 텍스트에 `<img`, `![](`, 또는 외부 이미지 URL이 있으면 폐기.
- **원문 전문 저장 금지** — 원문 본문 전체를 저장소에 커밋하지 않는다. 제목·요약·링크·메타데이터만 남긴다.
- **가드는 fail-closed** — 중복 인덱스를 읽지 못하면(파일은 있는데 파싱 실패) 발행을 **중단**한다. 읽기 실패를 "중복 없음"으로 해석하지 않는다. 단, 파일이 아예 없는 최초 실행은 빈 인덱스로 정상 진행한다.
- **C등급 하루 5건 상한**, 승인되지 않은 초안은 **48시간 후 자동 폐기**.
- **개별 소스 실패가 전체를 막지 않는다** — 한 소스가 실패해도 나머지로 빌드한다. 실패는 기록한다.
- **빈 결과 방어** — 수집 0건이면 기존 `public/`을 유지하고 경고한다. 빈 사이트를 배포하지 않는다.
- **발행 시각** — 매일 05:00 KST (= 20:00 UTC 전일). cron: `0 20 * * *`.
- **매체명 표기** — `와플트립`, 부제 `매일 아침 여행 뉴스`, 도메인 `waffletrip.com`.
- **과미 제외** — 과미(@guami_travel)는 플레이 계열이 아니다. 이 사이트에 넣지 않는다.

## File Structure

```
~/여행신문/                          (git repo)
├── sources.yaml                     소스 레지스트리 — Task 1 산출물
├── requirements.txt
├── pytest.ini
├── tools/
│   └── check_sources.py             소스 생존 점검 스크립트 (Task 1)
├── src/
│   ├── __init__.py
│   ├── models.py                    Item 데이터클래스 + URL 정규화 + 해시 (Task 2)
│   ├── sources.py                   sources.yaml 로드·스키마 검증 (Task 1)
│   ├── fetch/
│   │   ├── __init__.py
│   │   ├── rss.py                   RSS/Atom 수집 (Task 3)
│   │   └── json_api.py              JSON API 수집 — 환율·여행경보 (Task 4)
│   ├── collect.py                   수집 오케스트레이터 → data/raw/ (Task 5)
│   ├── guards/
│   │   ├── __init__.py
│   │   ├── copyright_guard.py       인용 상한·출처·이미지 규칙 (Task 6)
│   │   └── dup_guard.py             중복·재발행 차단 (Task 7)
│   ├── grade.py                     등급 분류 + C후보 선정 (Task 8)
│   ├── edit.py                      편집 오케스트레이터 → data/items/ (Task 9)
│   ├── render/
│   │   ├── __init__.py
│   │   ├── site.py                  HTML 렌더 (Task 10)
│   │   ├── feeds.py                 RSS·sitemap·robots (Task 11)
│   │   └── templates/               Jinja2 템플릿 (Task 10)
│   └── build.py                     빌드 오케스트레이터 → public/ (Task 12)
├── tests/
│   ├── fixtures/                    저장된 RSS·JSON 샘플 (네트워크 없이 테스트)
│   └── test_*.py
├── data/
│   ├── raw/YYYY-MM-DD/              수집 원본
│   ├── items/YYYY-MM-DD.jsonl       정규화 항목
│   └── published_index.json         발행 이력 (중복 판정)
├── content/review/                  C등급 초안
├── public/                          빌드 산출물 (Pages 배포 대상)
└── .github/workflows/daily.yml      매일 05시 자동 실행 (Task 13)
```

**책임 분리 원칙:** `fetch/*`는 네트워크만 알고 도메인 규칙을 모른다. `guards/*`는 항목만 보고 파일시스템을 모른다(인덱스 경로는 주입받는다). `render/*`는 항목 리스트만 받고 수집 과정을 모른다. 오케스트레이터(`collect`/`edit`/`build`)만 파일시스템과 순서를 안다.

---

## Task 1: 소스 레지스트리 — 실측 조사와 로더

7개 지역 소스 후보를 실제로 두드려보고, 응답하는 것만 `sources.yaml`에 남긴다. 스펙 8절의 목록은 **후보일 뿐 검증되지 않았다.** 죽은 소스를 조용히 빼지 말고 조사 결과에 기록한다.

**Files:**
- Create: `tools/check_sources.py`
- Create: `sources.yaml`
- Create: `src/__init__.py`, `src/sources.py`
- Create: `tests/test_sources.py`
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `src.sources.Source` — 데이터클래스. 필드: `id: str`, `region: str`, `section: str`, `name: str`, `type: str`, `url: str`, `lang: str`, `enabled: bool`
  - `src.sources.load_sources(path: str) -> list[Source]` — 검증 통과한 소스만 반환. 검증 실패 시 `SourceConfigError` 발생
  - `src.sources.SourceConfigError(Exception)`

- [ ] **Step 1: 프로젝트 기본 파일 생성**

`requirements.txt`:
```
feedparser==6.0.11
httpx==0.27.2
PyYAML==6.0.2
Jinja2==3.1.4
pytest==8.3.3
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -q
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
public/
data/raw/
```

`src/__init__.py` — 빈 파일.

- [ ] **Step 2: 가상환경 만들고 의존성 설치**

```bash
cd ~/여행신문
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -c "import feedparser, httpx, yaml, jinja2; print('deps ok')"
```
Expected: `deps ok`

- [ ] **Step 3: 소스 생존 점검 스크립트 작성**

`tools/check_sources.py`:
```python
"""소스 후보를 실제로 두드려 살아있는지 확인한다.

사용법: .venv/bin/python tools/check_sources.py candidates.txt
candidates.txt 는 한 줄에 하나씩 "id<TAB>url" 형식.
결과를 표로 출력하고 살아있는 것만 stdout 마지막에 yaml 스니펫으로 낸다.
"""
import sys
import urllib.robotparser
from urllib.parse import urlsplit, urlunsplit

import httpx
import feedparser

UA = "WaffleTripBot/1.0 (+https://waffletrip.com/about/)"
TIMEOUT = 10.0


def robots_allows(url: str) -> tuple[bool, str]:
    """대상 사이트의 robots.txt 가 우리 봇에게 이 경로를 허용하는가.

    스펙 5절 규칙 4. 금지된 경로는 소스로 쓰지 않는다.
    robots.txt 를 못 읽는 경우는 허용으로 본다 — 표준 관행이고,
    없는 robots.txt 를 금지로 해석하면 정상 피드를 전부 버리게 된다.
    """
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    parser = urllib.robotparser.RobotFileParser()
    try:
        r = httpx.get(robots_url, timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": UA})
        if r.status_code >= 400:
            return True, "robots.txt 없음 (허용으로 간주)"
        parser.parse(r.text.splitlines())
    except Exception:
        return True, "robots.txt 조회 실패 (허용으로 간주)"
    allowed = parser.can_fetch(UA, url)
    return allowed, "robots 허용" if allowed else "robots 금지 — 소스로 쓸 수 없다"


def probe(url: str) -> tuple[bool, str]:
    """(살아있는가, 사유). RSS면 항목 수까지 확인한다."""
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": UA})
    except Exception as e:
        return False, f"연결실패: {type(e).__name__}"
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code}"
    body = r.text
    if "<rss" in body[:2000].lower() or "<feed" in body[:2000].lower():
        parsed = feedparser.parse(body)
        n = len(parsed.entries)
        return (n > 0), f"RSS 항목 {n}개"
    if body.lstrip().startswith(("{", "[")):
        return True, "JSON 응답"
    return False, "RSS/JSON 아님 (HTML만 반환)"


def main(path: str) -> None:
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sid, url = line.split("\t", 1)
        allowed, robots_why = robots_allows(url)
        if not allowed:
            rows.append((sid, url, False, robots_why))
            print(f"X   {sid:24s} {robots_why:34s} {url}")
            continue
        ok, why = probe(url)
        rows.append((sid, url, ok, why))
        print(f"{'OK ' if ok else 'X  '} {sid:24s} {why:34s} {url}")
    alive = [r for r in rows if r[2]]
    print(f"\n=== 사용 가능 {len(alive)}/{len(rows)} ===")
    print("robots 금지로 걸린 소스는 sources.yaml 에 넣지 않는다.")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 4: 후보 목록을 만들고 실제로 두드린다**

스펙 8절의 후보를 `candidates.txt`로 옮긴다. 각 매체의 RSS 경로는 추측하지 말고 실제로 확인한다 — 대부분 `/rss`, `/feed`, `/rss.xml`, `/feeds/all.rss` 중 하나다. 확인 방법은 매체 홈페이지 HTML에서 `application/rss+xml` 링크 태그를 찾는 것이다:

```bash
.venv/bin/python -c "
import httpx, re, sys
for host in ['https://www.postguam.com','https://www.mvariety.com','https://www.saipantribune.com','https://www.hawaiinewsnow.com','https://e.vnexpress.net','https://www.theborneopost.com','https://www.vientianetimes.org.la','https://www.kuam.com','https://www.pacificislandtimes.com','https://beatofhawaii.com','https://www.dailyexpress.com.my','https://laotiantimes.com','https://www.jejusori.net','https://www.headlinejeju.co.kr']:
    try:
        r = httpx.get(host, timeout=10, follow_redirects=True, headers={'User-Agent':'WaffleTripBot/1.0'})
        feeds = re.findall(r'<link[^>]+application/(?:rss|atom)\+xml[^>]*>', r.text, re.I)
        hrefs = [re.search(r'href=[\"\\']([^\"\\']+)', f, re.I) for f in feeds]
        print(host, '->', [h.group(1) for h in hrefs if h][:3] or 'RSS 링크 태그 없음')
    except Exception as e:
        print(host, '-> 실패', type(e).__name__)
"
```

찾은 URL을 `candidates.txt`에 넣고 점검 스크립트를 돌린다:
```bash
.venv/bin/python tools/check_sources.py candidates.txt
```

점검 스크립트는 **각 소스의 robots.txt 를 먼저 확인**하고 금지된 경로는 살아있어도 탈락시킨다 (스펙 5절 규칙 4). robots 금지로 걸린 소스는 `sources.yaml`에 넣지 않는다.

**조사 결과를 `docs/source-survey-2026-08-31.md`에 기록한다.** 사용 가능한 소스, 죽은 소스, robots 금지 소스와 각각의 이유를 전부 남긴다. 나중에 소스를 늘릴 때 이미 확인한 것을 다시 두드리지 않기 위해서다.

- [ ] **Step 5: sources.yaml 작성**

살아있는 것만 넣는다. 실용데이터(A등급)는 이번 태스크에서 **환율 하나만** 넣는다 — 인증키 없이 동작하는 무료 공개 API다. 날씨·여행경보는 인증키 발급이 필요해 다음 사이클로 미룬다.

```yaml
# 와플트립 소스 레지스트리
# type: rss | json
# section: flight | news | data | promo
# 죽은 소스는 지우지 말고 enabled: false 로 남긴다 (재조사 방지)

sources:
  - id: exchange_rate
    region: all
    section: data
    name: 환율
    type: json
    url: https://open.er-api.com/v6/latest/KRW
    lang: en
    enabled: true

  # --- 아래는 Step 4 조사에서 살아남은 것만 채운다 ---
  # - id: guam_post
  #   region: guam
  #   section: news
  #   name: The Guam Daily Post
  #   type: rss
  #   url: https://www.postguam.com/search/?f=rss&t=article
  #   lang: en
  #   enabled: true
```

- [ ] **Step 6: 실패하는 테스트 작성**

`tests/test_sources.py`:
```python
import pytest
from src.sources import load_sources, SourceConfigError


def write(tmp_path, text):
    p = tmp_path / "sources.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_loads_valid_source(tmp_path):
    path = write(tmp_path, """
sources:
  - id: guam_post
    region: guam
    section: news
    name: The Guam Daily Post
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    sources = load_sources(path)
    assert len(sources) == 1
    assert sources[0].id == "guam_post"
    assert sources[0].region == "guam"


def test_skips_disabled_source(tmp_path):
    path = write(tmp_path, """
sources:
  - id: dead
    region: guam
    section: news
    name: Dead Feed
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: false
""")
    assert load_sources(path) == []


def test_rejects_unknown_region(tmp_path):
    path = write(tmp_path, """
sources:
  - id: bad
    region: mars
    section: news
    name: Mars Times
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="region"):
        load_sources(path)


def test_rejects_unknown_section(tmp_path):
    path = write(tmp_path, """
sources:
  - id: bad
    region: guam
    section: gossip
    name: Guam Gossip
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="section"):
        load_sources(path)


def test_rejects_duplicate_id(tmp_path):
    path = write(tmp_path, """
sources:
  - id: same
    region: guam
    section: news
    name: A
    type: rss
    url: https://example.com/a
    lang: en
    enabled: true
  - id: same
    region: jeju
    section: news
    name: B
    type: rss
    url: https://example.com/b
    lang: ko
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="중복"):
        load_sources(path)


def test_real_sources_yaml_is_valid():
    """실제 sources.yaml 이 항상 로드 가능해야 한다."""
    sources = load_sources("sources.yaml")
    assert len(sources) > 0
```

- [ ] **Step 7: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_sources.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.sources'`

- [ ] **Step 8: 로더 구현**

`src/sources.py`:
```python
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
        ))

    return result
```

- [ ] **Step 9: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_sources.py -v
```
Expected: PASS (6 passed)

- [ ] **Step 10: 커밋**

```bash
cd ~/여행신문
git add requirements.txt pytest.ini .gitignore src/__init__.py src/sources.py \
        tools/check_sources.py sources.yaml tests/test_sources.py \
        docs/source-survey-2026-08-31.md
git commit -m "feat: 소스 레지스트리와 실측 조사 결과

살아있는 것으로 확인된 소스만 sources.yaml 에 등록하고,
지역/섹션/타입/중복 ID를 로드 시점에 검증한다."
```

---

## Task 2: 데이터 모델 — Item, URL 정규화, 해시

파이프라인 전체가 주고받는 단 하나의 자료형을 정의한다. 이후 모든 태스크가 이 타입에 의존한다.

국내 여행 전문 매체의 피드는 목적지가 섞여 있으므로 **기사에서 지역을 추론하는 태거**도 여기서 만든다. 태거는 모델과 마찬가지로 순수 함수이고 아무것에도 의존하지 않으므로 같은 태스크에 둔다.

**Files:**
- Create: `src/models.py`
- Create: `src/region_tag.py`
- Create: `tests/test_models.py`
- Create: `tests/test_region_tag.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `src.models.Item` — 데이터클래스. 필드: `id: str`, `grade: str`, `region: str`, `section: str`, `title: str`, `summary: str`, `source_name: str`, `source_url: str`, `published_at: str`, `collected_at: str`, `status: str`, `title_hash: str`, `body_md: str | None = None`, `related: list[str] = []`
  - `src.models.normalize_url(url: str) -> str`
  - `src.models.make_id(source_url: str, title: str, published_at: str) -> str`
  - `src.models.title_hash(title: str) -> str`
  - `src.models.title_tokens(title: str) -> set[str]`
  - `src.models.jaccard(a: set[str], b: set[str]) -> float`
  - `src.models.item_to_dict(item: Item) -> dict` / `src.models.item_from_dict(d: dict) -> Item`
  - `src.region_tag.REGION_KEYWORDS: dict[str, tuple[str, ...]]`
  - `src.region_tag.SINGLE_CHAR_ALLOWED: frozenset[str]` — 한 글자 키워드 허용 목록
  - `src.region_tag.REGION_EXCLUSIONS: tuple[str, ...]` — 지역명을 품었지만 그 지역이 아닌 표현
  - `src.region_tag.tag_region(text: str) -> str | None` — 지역 키 또는 `None`(우리가 다루지 않는 목적지)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_models.py`:
```python
from src.models import (Item, normalize_url, make_id, title_hash,
                        title_tokens, jaccard, item_to_dict, item_from_dict)


def test_normalize_url_strips_tracking_params():
    url = "https://Example.com/news/a?utm_source=x&id=7&fbclid=zz#top"
    assert normalize_url(url) == "https://example.com/news/a?id=7"


def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://example.com/news/") == "https://example.com/news"


def test_normalize_url_keeps_root_slash():
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_make_id_is_stable_for_same_url():
    a = make_id("https://example.com/a?utm_source=x", "제목", "2026-08-31")
    b = make_id("https://example.com/a", "다른 제목", "2026-09-01")
    assert a == b, "URL 이 같으면 제목이 달라도 같은 항목이다"


def test_make_id_falls_back_to_title_when_no_url():
    a = make_id("", "괌 신규 취항", "2026-08-31")
    b = make_id("", "괌 신규 취항", "2026-08-31")
    c = make_id("", "괌 신규 취항", "2026-09-01")
    assert a == b
    assert a != c


def test_title_hash_ignores_spacing_and_punctuation():
    assert title_hash("괌, 신규 취항!") == title_hash("괌 신규취항")


def test_title_tokens_drops_one_character_words():
    assert title_tokens("괌 에 신규 취항") == {"신규", "취항"}


def test_jaccard_identical_is_one():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_is_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty_sets_is_zero():
    assert jaccard(set(), set()) == 0.0


def test_item_roundtrips_through_dict():
    item = Item(
        id="abc", grade="B", region="guam", section="news",
        title="괌 신규 취항", summary="요약", source_name="Guam Post",
        source_url="https://example.com/a", published_at="2026-08-31T09:00:00+09:00",
        collected_at="2026-08-31T05:00:00+09:00", status="draft",
        title_hash="hhh",
    )
    assert item_from_dict(item_to_dict(item)) == item


def test_item_roundtrips_with_body_and_related():
    item = Item(
        id="abc", grade="C", region="jeju", section="flight",
        title="t", summary="s", source_name="n", source_url="u",
        published_at="2026-08-31T09:00:00+09:00",
        collected_at="2026-08-31T05:00:00+09:00", status="approved",
        title_hash="h", body_md="# 본문", related=["x", "y"],
    )
    assert item_from_dict(item_to_dict(item)) == item
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: 모델 구현**

`src/models.py`:
```python
"""파이프라인 전체가 주고받는 자료형.

이 모듈은 아무것도 import 하지 않는다(표준 라이브러리 제외).
수집·편집·렌더가 전부 여기에 의존하므로 의존성이 한 방향으로만 흐른다.
"""
import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

GRADES = ("A", "B", "C")
SECTIONS = ("flight", "news", "data", "promo")
REGIONS = ("guam", "saipan", "hawaii", "vietnam", "kota", "laos", "jeju")
STATUSES = ("draft", "approved", "published")

# 추적용 쿼리 파라미터 — 같은 기사인데 URL 만 달라 보이게 만드는 주범
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "igshid", "ref", "ref_src", "spm"}

_PUNCT = re.compile(r"[^\w가-힣]+", re.UNICODE)


@dataclass
class Item:
    id: str
    grade: str
    region: str
    section: str
    title: str
    summary: str
    source_name: str
    source_url: str
    published_at: str
    collected_at: str
    status: str
    title_hash: str
    body_md: str | None = None
    related: list[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    """추적 파라미터와 프래그먼트를 떼고 호스트를 소문자로 만든다.

    같은 기사가 서로 다른 URL 로 두 번 들어오는 것을 막기 위한 것이므로,
    의미 있는 쿼리(id=7 등)는 남긴다.
    """
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_KEYS
        and not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "",
    ))


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def make_id(source_url: str, title: str, published_at: str) -> str:
    """항목의 영구 식별자.

    URL 이 있으면 URL 만으로 정한다 — 같은 기사의 제목이 나중에 수정돼도
    같은 항목으로 인식해야 재발행을 막을 수 있다.
    """
    normalized = normalize_url(source_url)
    if normalized:
        return _sha1(normalized)
    return _sha1(f"{title}|{published_at}")


def title_hash(title: str) -> str:
    """공백·구두점을 무시한 제목 해시. 완전 동일 제목 판정용."""
    return _sha1(_PUNCT.sub("", title).lower())


def title_tokens(title: str) -> set[str]:
    """유사도 비교용 토큰. 조사·한 글자 단어는 잡음이라 버린다."""
    return {t for t in _PUNCT.split(title.lower()) if len(t) > 1}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def item_to_dict(item: Item) -> dict:
    return {
        "id": item.id, "grade": item.grade, "region": item.region,
        "section": item.section, "title": item.title, "summary": item.summary,
        "source_name": item.source_name, "source_url": item.source_url,
        "published_at": item.published_at, "collected_at": item.collected_at,
        "status": item.status, "title_hash": item.title_hash,
        "body_md": item.body_md, "related": list(item.related),
    }


def item_from_dict(d: dict) -> Item:
    return Item(
        id=d["id"], grade=d["grade"], region=d["region"], section=d["section"],
        title=d["title"], summary=d["summary"], source_name=d["source_name"],
        source_url=d["source_url"], published_at=d["published_at"],
        collected_at=d["collected_at"], status=d["status"],
        title_hash=d["title_hash"], body_md=d.get("body_md"),
        related=list(d.get("related") or []),
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_models.py -v
```
Expected: PASS (12 passed)

- [ ] **Step 5: 지역 태거의 실패하는 테스트 작성**

`tests/test_region_tag.py`:
```python
from src.region_tag import tag_region, REGION_KEYWORDS, SINGLE_CHAR_ALLOWED
from src.models import REGIONS


def test_tags_guam_from_korean_title():
    assert tag_region("진에어, 괌 노선 증편 결정") == "guam"


def test_tags_from_english_name():
    assert tag_region("United adds Guam service") == "guam"


def test_is_case_insensitive():
    assert tag_region("HAWAII tourism rebounds") == "hawaii"


def test_tags_vietnam_from_city_name():
    assert tag_region("다낭 신규 리조트 오픈") == "vietnam"
    assert tag_region("나트랑 직항 재개") == "vietnam"


def test_tags_saipan_from_landmark():
    assert tag_region("마나가하 섬 입장료 인상") == "saipan"


def test_tags_kota_only_on_the_full_city_name():
    """'말레이시아'나 '사바'만으로 코타키나발루라고 단정하지 않는다.

    쿠알라룸푸르 기사를 코타키나발루로 태깅하면 우리 신문이 사실을 틀리는 것이다.
    재현율보다 정확도를 택한다."""
    assert tag_region("코타키나발루 신규 취항") == "kota"
    assert tag_region("말레이시아 관광객 증가") is None


def test_tags_laos():
    assert tag_region("루앙프라방 야시장 재개장") == "laos"


def test_tags_jeju():
    assert tag_region("제주 렌터카 요금 인하") == "jeju"


def test_returns_none_for_destinations_we_do_not_cover():
    assert tag_region("오사카 벚꽃 명소 총정리") is None
    assert tag_region("파리 올림픽 관광 특수") is None


def test_returns_none_for_empty_text():
    assert tag_region("") is None


def test_picks_the_region_with_more_hits():
    """여러 지역이 언급되면 더 많이 언급된 쪽으로 정한다."""
    assert tag_region("괌 여행 인기, 괌 호텔 만실 — 하와이도 회복세") == "guam"


def test_ties_break_by_fixed_region_order():
    """동점이면 항상 같은 결과가 나와야 한다. 실행마다 달라지면 안 된다."""
    assert tag_region("괌·사이판 공동 프로모션") == "guam"


def test_every_keyword_bucket_is_a_real_region():
    assert set(REGION_KEYWORDS) == set(REGIONS)


def test_single_character_keywords_come_from_an_explicit_allowlist():
    """한 글자 키워드는 오탐을 부르므로 명시 허용 목록에 있는 것만 쓴다.

    '괌'은 한국어에서 다른 단어의 부분문자열로 거의 나타나지 않아 안전하다.
    새 한 글자 키워드를 넣으려면 허용 목록에 추가하고 근거를 남겨야 한다.
    """
    for region, words in REGION_KEYWORDS.items():
        for w in words:
            assert len(w) > 1 or w in SINGLE_CHAR_ALLOWED, (
                f"{region} 의 한 글자 키워드 '{w}' 가 허용 목록에 없다")


def test_airline_name_containing_a_region_is_not_the_destination():
    """제주항공은 제주가 아니라 전 세계로 날아가는 항공사다.

    실측에서 이 한 단어가 중국 계림·일본 나고야·오사카 기사를 제주로 잘못
    태깅했다. 항공사명은 목적지가 아니다.
    """
    assert tag_region("제주항공, 부산~구이린 노선 취항") is None
    assert tag_region("제주항공, 오사카 노선 증편") is None
    assert tag_region("노랑풍선, 일본 나고야 상품 — 제주항공 나고야 4일") is None


def test_real_jeju_articles_still_tag_after_the_exclusion():
    """제외 규칙이 진짜 제주 기사까지 잡아먹으면 안 된다."""
    assert tag_region("제주 렌터카 요금 인하") == "jeju"
    assert tag_region("모두를 위한 제주, 열린 관광 페스타") == "jeju"
    assert tag_region("에어서울, 제주 노선 탑승률 96.6%") == "jeju"


def test_common_non_target_destinations_are_not_mistagged():
    """길이 규칙보다 이쪽이 진짜 방어선이다. 오탐이 곧 오보다."""
    for text in ("오사카 벚꽃 명소", "파리 올림픽 특수", "도쿄 여행 수요",
                 "방콕 호텔 요금", "세부 리조트 개장", "유류할증료 인상",
                 "여권 발급 수수료 변경", "발리 우기 정보"):
        assert tag_region(text) is None, text
```

- [ ] **Step 6: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_region_tag.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.region_tag'`

- [ ] **Step 7: 지역 태거 구현**

`src/region_tag.py`:
```python
"""기사 텍스트에서 우리가 다루는 7개 지역 중 하나를 추론한다.

국내 여행 전문 매체의 피드는 전 세계 목적지가 섞여 들어온다. 소스에 지역을
고정으로 붙일 수 없으므로 기사마다 판단해야 한다.

원칙은 재현율보다 **정확도**다. '말레이시아' 기사를 코타키나발루로 태깅하면
우리 신문이 사실을 틀리는 것이고, 그건 놓치는 것보다 나쁘다. 그래서 광역
지명이 아니라 도시·섬 이름으로만 매칭한다.
"""
from src.models import REGIONS

# 지역 이름을 품고 있지만 그 지역 기사가 아닌 표현. 세기 전에 먼저 지운다.
# '제주항공'은 제주가 아니라 전 세계로 날아가는 항공사다 — 실측에서
# "제주항공, 부산~구이린 노선 취항"(중국 계림 기사)과 "노랑풍선 일본 나고야 상품"이
# 제주로 잘못 태깅됐다. 항공사명이 목적지를 뜻하지 않는다.
REGION_EXCLUSIONS = ("제주항공",)

# 한 글자 키워드는 오탐을 부르므로 여기 적힌 것만 허용한다.
# '괌'은 한국어에서 다른 단어의 부분문자열로 거의 나타나지 않아 안전하다
# (오사카·파리·도쿄·방콕·세부·유류할증료·여권·발리 에서 오탐 없음을 실측 확인).
SINGLE_CHAR_ALLOWED = frozenset({"괌"})

# 순서가 동점 처리 순서다. REGIONS 와 같은 순서로 유지한다.
REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "guam": ("괌", "guam", "투몬", "tumon", "하갓냐", "데데도"),
    "saipan": ("사이판", "saipan", "티니안", "tinian", "북마리아나",
               "마나가하", "managaha", "마리아나"),
    "hawaii": ("하와이", "hawaii", "호놀룰루", "honolulu", "와이키키",
               "waikiki", "마우이", "maui", "오아후", "oahu", "빅아일랜드"),
    "vietnam": ("베트남", "vietnam", "다낭", "danang", "da nang", "호이안",
                "hoi an", "나트랑", "냐짱", "nha trang", "푸꾸옥", "phu quoc",
                "하노이", "hanoi", "호치민", "ho chi minh", "달랏"),
    "kota": ("코타키나발루", "코타키나바루", "코타 키나발루", "kota kinabalu"),
    "laos": ("라오스", "laos", "비엔티안", "vientiane", "루앙프라방",
             "luang prabang", "방비엥", "vang vieng"),
    "jeju": ("제주", "jeju", "서귀포"),
}


def tag_region(text: str) -> str | None:
    """가장 많이 언급된 지역을 돌려준다. 하나도 없으면 None.

    None 은 오류가 아니라 '우리가 다루지 않는 목적지'라는 정상 판정이다.
    호출자는 그 항목을 버린다.
    """
    if not text:
        return None

    lowered = text.lower()
    for phrase in REGION_EXCLUSIONS:
        lowered = lowered.replace(phrase.lower(), " ")

    best_region: str | None = None
    best_hits = 0

    # REGIONS 순서로 도므로 동점이면 항상 앞선 지역이 이긴다 (결정적).
    for region in REGIONS:
        hits = sum(lowered.count(k.lower()) for k in REGION_KEYWORDS[region])
        if hits > best_hits:
            best_region, best_hits = region, hits

    return best_region
```

- [ ] **Step 8: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_models.py tests/test_region_tag.py -v
```
Expected: PASS (30 passed)

- [ ] **Step 9: 커밋**

```bash
git add src/models.py src/region_tag.py tests/test_models.py tests/test_region_tag.py
git commit -m "feat: Item 자료형과 지역 태거

URL 정규화로 추적 파라미터만 다른 같은 기사를 한 항목으로 묶고,
id 를 URL 기준으로 정해 제목이 수정돼도 재발행되지 않게 한다."
```

---

## Task 3: RSS 수집기

RSS/Atom 피드를 `Item` 목록으로 바꾼다. 네트워크 호출과 파싱을 분리해 파싱을 네트워크 없이 테스트한다.

**요약 추출에 관한 결정 (중요):** 피드의 `description`을 통째로 쓰면 대부분 200자를 넘어 가드에서 전량 폐기된다. 그래서 **수집 시점에 앞 2문장만 뽑는 것을 편집 행위로 명시**한다. 가드는 그 결과를 검증할 뿐 자르지 않는다. 첫 문장 하나가 이미 200자를 넘으면 요약이 불가능하다는 뜻이므로 가드가 폐기한다.

**Files:**
- Create: `src/fetch/__init__.py`, `src/fetch/rss.py`
- Create: `tests/fixtures/sample_feed.xml`
- Create: `tests/test_fetch_rss.py`

국내 여행 전문 매체 피드는 `region: auto` 로 등록되므로, 이 수집기가 **기사마다 지역을 확정**한다. 지역을 못 정한 기사는 우리가 다루지 않는 목적지이므로 버린다.

**Interfaces:**
- Consumes: `src.models.Item`, `src.models.make_id`, `src.models.title_hash`; `src.region_tag.tag_region`; `src.sources.Source`
- Produces:
  - `src.fetch.rss.strip_html(text: str) -> str`
  - `src.fetch.rss.first_sentences(text: str, n: int = 2) -> str`
  - `src.fetch.rss.parse_feed(source: Source, xml_text: str, collected_at: str) -> list[Item]`
  - `src.fetch.rss.fetch(source: Source, client, collected_at: str) -> list[Item]`
  - `src.fetch.rss.USER_AGENT: str`

- [ ] **Step 1: 픽스처 만들기**

`tests/fixtures/sample_feed.xml`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Guam News</title>
    <item>
      <title>United adds third daily Guam-Tokyo flight</title>
      <link>https://example.com/news/united-guam?utm_source=rss</link>
      <description>&lt;p&gt;United Airlines will add a third daily flight. The new service starts in October. Officials expect higher demand from Japan.&lt;/p&gt;</description>
      <pubDate>Sat, 30 Aug 2026 09:00:00 +1000</pubDate>
    </item>
    <item>
      <title>Tumon beach cleanup draws 300 volunteers</title>
      <link>https://example.com/news/cleanup</link>
      <description>Volunteers gathered at dawn.</description>
      <pubDate>Fri, 29 Aug 2026 22:30:00 +1000</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_fetch_rss.py`:
```python
from pathlib import Path

from src.fetch.rss import strip_html, first_sentences, parse_feed
from src.sources import Source

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"
NOW = "2026-08-31T05:00:00+09:00"

SOURCE = Source(id="guam_sample", region="guam", section="news",
                name="Sample Guam News", type="rss",
                url="https://example.com/rss", lang="en", enabled=True)


def test_strip_html_removes_tags_and_entities():
    assert strip_html("<p>Hello &amp; bye</p>") == "Hello & bye"


def test_strip_html_collapses_whitespace():
    assert strip_html("a\n\n  b\t c") == "a b c"


def test_first_sentences_takes_two():
    text = "One. Two. Three. Four."
    assert first_sentences(text, 2) == "One. Two."


def test_first_sentences_returns_all_when_fewer_than_n():
    assert first_sentences("Only one.", 2) == "Only one."


def test_first_sentences_handles_no_terminator():
    assert first_sentences("No terminator here", 2) == "No terminator here"


def test_parse_feed_returns_all_entries():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert len(items) == 2


def test_parse_feed_summary_is_two_sentences():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].summary == (
        "United Airlines will add a third daily flight. "
        "The new service starts in October."
    )


def test_parse_feed_carries_source_metadata():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].source_name == "Sample Guam News"
    assert items[0].region == "guam"
    assert items[0].section == "news"
    assert items[0].collected_at == NOW


def test_parse_feed_normalizes_tracking_params_in_id():
    """utm_source 가 붙은 링크와 안 붙은 링크가 같은 id 여야 한다."""
    from src.models import make_id
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].id == make_id("https://example.com/news/united-guam", "", "")


def test_parse_feed_defaults_to_draft_and_grade_b():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].status == "draft"
    assert items[0].grade == "B"


def test_parse_feed_uses_collected_at_when_no_pubdate():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>No date</title><link>https://example.com/x</link>
    <description>Body.</description></item></channel></rss>"""
    items = parse_feed(SOURCE, xml, NOW)
    assert items[0].published_at == NOW


def test_parse_feed_skips_entry_without_title():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><link>https://example.com/x</link><description>Body.</description></item>
    </channel></rss>"""
    assert parse_feed(SOURCE, xml, NOW) == []


def test_parse_feed_on_garbage_returns_empty():
    assert parse_feed(SOURCE, "not xml at all", NOW) == []


# --- region: auto (국내 여행 전문 매체) ---

AUTO_SOURCE = Source(id="traveltimes", region="auto", section="news",
                     name="여행신문", type="rss",
                     url="https://example.com/rss", lang="ko", enabled=True)

AUTO_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>진에어, 괌 노선 증편 결정</title><link>https://example.com/g</link>
<description>10월부터 주 7회로 늘린다.</description></item>
<item><title>오사카 벚꽃 명소 총정리</title><link>https://example.com/o</link>
<description>봄 시즌 추천 코스.</description></item>
<item><title>다낭 신규 리조트 오픈</title><link>https://example.com/d</link>
<description>5성급이 문을 연다.</description></item>
</channel></rss>"""


def test_auto_source_assigns_region_per_article():
    items = parse_feed(AUTO_SOURCE, AUTO_FEED, NOW)
    assert [(i.title[:2], i.region) for i in items] == [
        ("진에", "guam"), ("다낭", "vietnam")]


def test_auto_source_drops_destinations_we_do_not_cover():
    """오사카 기사는 버린다. 우리가 다루는 7개 지역이 아니다."""
    items = parse_feed(AUTO_SOURCE, AUTO_FEED, NOW)
    assert all("오사카" not in i.title for i in items)


def test_auto_source_ignores_regions_that_appear_only_in_the_summary():
    """요약에 스쳐 지나간 지명으로 지역을 정하지 않는다.

    실측 근거: 요약까지 보고 판정했더니 8건 중 5건이 오탐이었다.
    "티웨이항공 타고 싱가포르 가면…"이 제주로, 여행 기사도 아닌
    "신복위-나주시 금융취약계층 지원"이 제주로 잡혔다.
    """
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>신규 취항 소식</title><link>https://example.com/x</link>
    <description>제주 노선이 늘어난다.</description></item></channel></rss>"""
    assert parse_feed(AUTO_SOURCE, xml, NOW) == []


def test_korean_sentences_split_without_a_space_after_the_period():
    """한국어 기사는 마침표 뒤에 공백이 없는 경우가 흔하다.

    못 자르면 문단 전체가 한 문장이 되어 인용 한도를 넘긴다. 실측에서
    국내 매체 기사의 70%가 200자 초과로 전량 폐기됐다.
    """
    assert first_sentences("개최한다.열린 페스타는 무장애 여행이다.잘 된다.", 2) == (
        "개최한다. 열린 페스타는 무장애 여행이다.")


def test_abbreviation_periods_split_conservatively():
    """'U.S.' 뒤 공백에서도 잘린다. 원래 규칙부터 그랬고 그대로 둔다.

    요약이 의도보다 짧아질 뿐 인용 한도를 넘기지는 않는다. 보수적으로 짧은 쪽으로
    틀리는 것은 저작권 관점에서 안전한 방향이라 잡지 않는다.
    """
    assert first_sentences("The U.S. Navy arrived. Next one.", 2) == (
        "The U.S. Navy arrived.")


def test_static_region_source_is_not_retagged():
    """region 이 고정된 소스는 기사 내용과 무관하게 그 지역을 쓴다."""
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>Hawaii tourism note</title><link>https://example.com/h</link>
    <description>Body.</description></item></channel></rss>"""
    # SOURCE 는 region="guam" 고정이다
    assert parse_feed(SOURCE, xml, NOW)[0].region == "guam"
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_fetch_rss.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.fetch'`

- [ ] **Step 4: 구현**

`src/fetch/__init__.py` — 빈 파일.

`src/fetch/rss.py`:
```python
"""RSS/Atom 피드를 Item 으로 바꾼다.

parse_feed 는 순수 함수다(네트워크를 모른다). fetch 만 네트워크를 안다.
덕분에 파싱 규칙 전체를 저장된 픽스처로 테스트할 수 있다.
"""
import html
import re
from datetime import datetime, timezone

import feedparser

from src.models import Item, make_id, title_hash
from src.region_tag import tag_region
from src.sources import Source

USER_AGENT = "WaffleTripBot/1.0 (+https://waffletrip.com/about/)"
TIMEOUT = 15.0

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
# 한국어 기사 본문은 마침표 뒤에 공백이 없는 경우가 흔하다("개최한다.열린 관광 페스타는").
# 종결부호+공백으로만 자르면 문단 전체가 한 문장이 되어 인용 한도를 넘긴다 — 실측에서
# 국내 매체 기사의 70%가 200자를 넘겨 전량 폐기됐다. 그래서 두 자리에서 자른다.
#   (1) 종결부호 뒤 공백   (2) 한글 바로 뒤에 붙은 종결부호(공백이 없어도)
# (2)는 앞이 한글일 때만 걸리므로 "U.S. Navy" 같은 영문 약어는 잘리지 않는다.
_SENTENCE_END = re.compile(r"(?<=[.!?。？！])\s+|(?<=[가-힣][.!?。？！])")


def strip_html(text: str) -> str:
    """태그와 엔티티를 걷어내고 공백을 하나로 만든다."""
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def first_sentences(text: str, n: int = 2) -> str:
    """앞 n개 문장만 남긴다.

    이것이 우리의 요약 행위다. 원문 전체를 옮기지 않기 위한 것이므로
    가드보다 앞 단계에서 수행한다.
    """
    if not text:
        return ""
    parts = _SENTENCE_END.split(text)
    return " ".join(parts[:n]).strip()


def _published_at(entry, fallback: str) -> str:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return fallback
    return datetime(*parsed[:6], tzinfo=timezone.utc).isoformat()


def parse_feed(source: Source, xml_text: str, collected_at: str) -> list[Item]:
    feed = feedparser.parse(xml_text)
    items: list[Item] = []

    for entry in feed.entries:
        title = strip_html(entry.get("title", ""))
        if not title:
            continue  # 제목 없는 항목은 기사가 아니다

        link = (entry.get("link") or "").strip()
        raw_summary = entry.get("summary") or entry.get("description") or ""
        summary = first_sentences(strip_html(raw_summary), 2)
        published = _published_at(entry, collected_at)

        # 국내 여행 전문 매체는 목적지가 섞여 오므로 기사마다 지역을 정한다.
        region = source.region
        if region == "auto":
            # 제목에서만 판정한다. 요약까지 봤더니 실측에서 요약전용 매칭 8건 중
            # 5건이 오탐이었다 — "티웨이항공 타고 싱가포르"가 제주로, 여행 기사도
            # 아닌 "금융취약계층 생필품 지원"이 제주로 잡혔다. 요약에는 다른 목적지가
            # 스쳐 지나가고, 소스에 따라 아예 다른 기사 본문이 실려 오기도 한다.
            region = tag_region(title)
            if region is None:
                continue  # 우리가 다루지 않는 목적지

        items.append(Item(
            id=make_id(link, title, published),
            grade="B",              # Task 8 에서 재분류된다
            region=region,
            section=source.section,
            title=title,
            summary=summary,
            source_name=source.name,
            source_url=link,
            published_at=published,
            collected_at=collected_at,
            status="draft",
            title_hash=title_hash(title),
        ))

    return items


def fetch(source: Source, client, collected_at: str) -> list[Item]:
    """네트워크에서 피드를 받아 파싱한다. 예외는 호출자가 처리한다."""
    response = client.get(
        source.url, timeout=TIMEOUT, follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    return parse_feed(source, response.text, collected_at)
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_fetch_rss.py -v
```
Expected: PASS (19 passed)

- [ ] **Step 6: 커밋**

```bash
git add src/fetch/__init__.py src/fetch/rss.py tests/fixtures/sample_feed.xml tests/test_fetch_rss.py
git commit -m "feat: RSS 수집기

파싱을 순수 함수로 분리해 네트워크 없이 테스트한다.
요약은 수집 시점에 앞 2문장만 뽑는다 — 원문 전재를 구조적으로 막는다."
```

---

## Task 4: JSON API 수집기 — 환율

A등급(사실 데이터)의 첫 소스를 붙인다. JSON API 는 저마다 응답 모양이 다르므로 소스 id 별 핸들러 레지스트리를 둔다.

**Files:**
- Create: `src/fetch/json_api.py`
- Create: `tests/fixtures/exchange_rate.json`
- Create: `tests/test_fetch_json.py`

**Interfaces:**
- Consumes: `src.models.Item`, `src.models.make_id`, `src.models.title_hash`; `src.sources.Source`
- Produces:
  - `src.fetch.json_api.CURRENCY_BY_REGION: dict[str, str]`
  - `src.fetch.json_api.UnknownJsonSource(Exception)`
  - `src.fetch.json_api.parse_json(source: Source, payload: dict, collected_at: str) -> list[Item]`
  - `src.fetch.json_api.fetch(source: Source, client, collected_at: str) -> list[Item]`

- [ ] **Step 1: 픽스처 만들기**

`tests/fixtures/exchange_rate.json`:
```json
{
  "result": "success",
  "base_code": "KRW",
  "time_last_update_utc": "Sun, 30 Aug 2026 00:00:01 +0000",
  "rates": {
    "KRW": 1,
    "USD": 0.00072,
    "VND": 18.9,
    "MYR": 0.0032,
    "LAK": 15.6
  }
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_fetch_json.py`:
```python
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
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_fetch_json.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.fetch.json_api'`

- [ ] **Step 4: 구현**

`src/fetch/json_api.py`:
```python
"""JSON API 를 Item 으로 바꾼다.

API 마다 응답 모양이 다르므로 공통 파서를 만들 수 없다.
소스 id 로 핸들러를 찾는 레지스트리를 두고, 모르는 id 는 조용히 넘기지 않고
예외를 던진다 — sources.yaml 에 소스를 추가하고 핸들러를 잊는 사고를 막는다.
"""
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
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_fetch_json.py -v
```
Expected: PASS (9 passed)

- [ ] **Step 6: 실제 API 가 픽스처와 같은 모양인지 한 번 확인**

```bash
.venv/bin/python -c "
import httpx, json
r = httpx.get('https://open.er-api.com/v6/latest/KRW', timeout=15)
d = r.json()
print('result:', d.get('result'))
print('base:', d.get('base_code'))
print('USD:', d['rates'].get('USD'), '→ 1USD =', round(1/d['rates']['USD']), '원')
"
```
Expected: `result: success`, `base: KRW`, 그럴듯한 원화 값.
응답 모양이 픽스처와 다르면 **픽스처를 실제 응답으로 갱신하고 테스트를 고친다.**

- [ ] **Step 7: 커밋**

```bash
git add src/fetch/json_api.py tests/fixtures/exchange_rate.json tests/test_fetch_json.py
git commit -m "feat: JSON API 수집기와 환율 핸들러

핸들러 없는 소스는 조용히 넘어가지 않고 예외를 던진다.
환율은 여행자가 쓰는 방향(외화 1단위당 원)으로 뒤집어 저장한다."
```

---

## Task 5: 수집 오케스트레이터

소스를 병렬로 두드리고 결과를 `data/raw/`에 남긴다. **한 소스의 실패가 전체를 막지 않는 것**이 이 태스크의 핵심 요구사항이다.

**Files:**
- Create: `src/collect.py`
- Create: `tests/test_collect.py`

**Interfaces:**
- Consumes: `src.sources.load_sources`, `src.fetch.rss.fetch`, `src.fetch.json_api.fetch`, `src.models.item_to_dict`
- Produces:
  - `src.collect.collect_one(source: Source, client, collected_at: str) -> list[Item]`
  - `src.collect.collect_all(sources: list[Source], client, collected_at: str, max_workers: int = 8) -> tuple[list[Item], list[dict]]` — `(항목들, 오류들)`. 오류 dict 는 `{"source_id", "url", "error"}`
  - `src.collect.write_raw(out_dir: str, items: list[Item], errors: list[dict]) -> None`
  - `src.collect.main(sources_path: str = "sources.yaml", data_dir: str = "data") -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_collect.py`:
```python
import json
from pathlib import Path

from src.collect import collect_all, write_raw
from src.models import Item
from src.sources import Source

NOW = "2026-08-31T05:00:00+09:00"

RSS_SOURCE = Source(id="good_rss", region="guam", section="news", name="Good",
                    type="rss", url="https://example.com/rss", lang="en",
                    enabled=True)
BAD_SOURCE = Source(id="bad_rss", region="jeju", section="news", name="Bad",
                    type="rss", url="https://example.com/bad", lang="ko",
                    enabled=True)

FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Good story</title><link>https://example.com/a</link>
<description>Body sentence.</description></item></channel></rss>"""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeClient:
    """good 은 피드를 주고 bad 는 터진다."""

    def get(self, url, **kwargs):
        if url.endswith("/bad"):
            raise ConnectionError("boom")
        return FakeResponse(FEED)


def test_one_failure_does_not_stop_the_others():
    items, errors = collect_all([RSS_SOURCE, BAD_SOURCE], FakeClient(), NOW)
    assert len(items) == 1
    assert items[0].title == "Good story"
    assert len(errors) == 1
    assert errors[0]["source_id"] == "bad_rss"
    assert "boom" in errors[0]["error"]


def test_all_failing_yields_no_items_but_records_errors():
    items, errors = collect_all([BAD_SOURCE], FakeClient(), NOW)
    assert items == []
    assert len(errors) == 1


def test_empty_source_list_is_not_an_error():
    assert collect_all([], FakeClient(), NOW) == ([], [])


def test_write_raw_groups_items_by_source(tmp_path):
    items = [
        Item(id="1", grade="B", region="guam", section="news", title="t1",
             summary="s", source_name="Good", source_url="https://example.com/a",
             published_at=NOW, collected_at=NOW, status="draft", title_hash="h1"),
    ]
    errors = [{"source_id": "bad_rss", "url": "u", "error": "boom"}]
    write_raw(str(tmp_path), items, errors)

    written = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    assert len(written) == 1
    assert written[0]["title"] == "t1"

    logged = json.loads((tmp_path / "_errors.json").read_text(encoding="utf-8"))
    assert logged[0]["source_id"] == "bad_rss"


def test_write_raw_creates_missing_directory(tmp_path):
    target = tmp_path / "deep" / "2026-08-31"
    write_raw(str(target), [], [])
    assert (target / "items.json").exists()
    assert (target / "_errors.json").exists()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_collect.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.collect'`

- [ ] **Step 3: 구현**

`src/collect.py`:
```python
"""소스를 병렬로 두드려 원본 항목을 data/raw/ 에 남긴다.

설계 원칙: 개별 소스의 실패는 격리된다. 하나가 죽어도 나머지로 신문을 낸다.
실패는 삼키지 않고 _errors.json 에 남겨 3일 연속 실패를 감시할 수 있게 한다.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from src.fetch import json_api, rss
from src.models import Item, item_to_dict
from src.sources import Source, load_sources

KST = timezone(timedelta(hours=9))


def now_kst() -> str:
    return datetime.now(KST).isoformat()


def collect_one(source: Source, client, collected_at: str) -> list[Item]:
    if source.type == "rss":
        return rss.fetch(source, client, collected_at)
    if source.type == "json":
        return json_api.fetch(source, client, collected_at)
    raise ValueError(f"알 수 없는 소스 타입 '{source.type}' (id={source.id})")


def collect_all(sources: list[Source], client, collected_at: str,
                max_workers: int = 8) -> tuple[list[Item], list[dict]]:
    items: list[Item] = []
    errors: list[dict] = []

    if not sources:
        return items, errors

    def run(source: Source):
        try:
            return source, collect_one(source, client, collected_at), None
        except Exception as e:  # 소스 하나의 실패로 전체를 멈추지 않는다
            return source, [], f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for source, fetched, error in pool.map(run, sources):
            if error:
                errors.append({"source_id": source.id, "url": source.url,
                               "error": error})
            else:
                items.extend(fetched)

    return items, errors


def write_raw(out_dir: str, items: list[Item], errors: list[dict]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump([item_to_dict(i) for i in items], f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "_errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def main(sources_path: str = "sources.yaml", data_dir: str = "data") -> int:
    collected_at = now_kst()
    day = collected_at[:10]
    sources = load_sources(sources_path)

    with httpx.Client() as client:
        items, errors = collect_all(sources, client, collected_at)

    out_dir = os.path.join(data_dir, "raw", day)
    write_raw(out_dir, items, errors)

    print(f"수집 완료: 소스 {len(sources)}개, 항목 {len(items)}건, "
          f"실패 {len(errors)}건 → {out_dir}")
    for e in errors:
        print(f"  실패 {e['source_id']}: {e['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_collect.py -v
```
Expected: PASS (5 passed)

- [ ] **Step 5: 실제 소스로 한 번 돌려본다**

```bash
cd ~/여행신문 && .venv/bin/python -m src.collect
```
Expected: `수집 완료: 소스 N개, 항목 M건, 실패 K건 → data/raw/2026-08-31`
`M`이 0이면 sources.yaml 이 비었거나 전부 죽은 것이다 — Task 1로 돌아간다.

- [ ] **Step 6: 커밋**

```bash
git add src/collect.py tests/test_collect.py
git commit -m "feat: 수집 오케스트레이터

소스 실패를 항목 단위로 격리해 하나가 죽어도 신문이 나온다.
실패는 _errors.json 에 남겨 연속 실패를 추적할 수 있게 한다."
```

---

## Task 6: 저작권 가드

수집한 항목이 인용 한도·출처·이미지 규칙을 지키는지 검증한다. **가드는 자르지 않는다. 통과시키거나 폐기한다.** 자르기는 Task 3의 수집 단계에서 이미 편집 행위로 수행했다.

**Files:**
- Create: `src/guards/__init__.py`, `src/guards/copyright_guard.py`
- Create: `tests/test_copyright_guard.py`

**Interfaces:**
- Consumes: `src.models.Item`
- Produces:
  - `src.guards.copyright_guard.MAX_SUMMARY_CHARS: int` (= 200)
  - `src.guards.copyright_guard.MAX_SUMMARY_SENTENCES: int` (= 2)
  - `src.guards.copyright_guard.violations(item: Item) -> list[str]` — 위반 사유 목록. 빈 리스트면 통과
  - `src.guards.copyright_guard.filter_items(items: list[Item]) -> tuple[list[Item], list[tuple[Item, list[str]]]]` — `(통과, [(폐기항목, 사유들)])`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_copyright_guard.py`:
```python
from src.guards.copyright_guard import violations, filter_items
from src.models import Item

NOW = "2026-08-31T05:00:00+09:00"


def make(grade="B", summary="One sentence.", source_name="Guam Post",
         source_url="https://example.com/a", body_md=None):
    return Item(id="x", grade=grade, region="guam", section="news",
                title="제목", summary=summary, source_name=source_name,
                source_url=source_url, published_at=NOW, collected_at=NOW,
                status="draft", title_hash="h", body_md=body_md)


def test_clean_b_item_passes():
    assert violations(make()) == []


def test_b_item_without_source_name_is_rejected():
    assert any("출처" in v for v in violations(make(source_name="")))


def test_b_item_without_source_url_is_rejected():
    assert any("출처" in v for v in violations(make(source_url="")))


def test_b_summary_over_200_chars_is_rejected():
    assert any("200자" in v for v in violations(make(summary="가" * 201)))


def test_b_summary_of_exactly_200_chars_passes():
    assert violations(make(summary="가" * 200)) == []


def test_b_summary_over_two_sentences_is_rejected():
    assert any("문장" in v for v in violations(make(summary="A. B. C.")))


def test_b_summary_of_exactly_two_sentences_passes():
    assert violations(make(summary="A. B.")) == []


def test_empty_summary_is_allowed():
    """제목+링크만 있는 형태가 가장 안전하다. 막을 이유가 없다."""
    assert violations(make(summary="")) == []


def test_html_image_tag_is_rejected():
    assert any("이미지" in v for v in violations(make(summary='<img src="a.jpg">')))


def test_markdown_image_is_rejected():
    assert any("이미지" in v for v in violations(make(summary="![alt](a.png)")))


def test_bare_image_url_is_rejected():
    assert any("이미지" in v
               for v in violations(make(summary="https://x.com/p.jpg")))


def test_image_in_body_is_rejected():
    item = make(grade="C", body_md="본문\n\n![x](https://x.com/a.png)")
    assert any("이미지" in v for v in violations(item))


def test_grade_a_is_exempt_from_length_limits():
    """A등급은 우리가 공공데이터로 만든 문장이라 인용이 아니다."""
    assert violations(make(grade="A", summary="가" * 300)) == []


def test_grade_a_still_needs_attribution():
    assert any("출처" in v for v in violations(make(grade="A", source_url="")))


def test_grade_c_is_exempt_from_length_limits():
    assert violations(make(grade="C", summary="가" * 300, body_md="본문")) == []


def test_grade_c_without_body_is_rejected():
    assert any("본문" in v for v in violations(make(grade="C", body_md="")))


def test_filter_items_splits_kept_and_dropped():
    good, bad = make(), make(summary="가" * 500)
    kept, dropped = filter_items([good, bad])
    assert kept == [good]
    assert len(dropped) == 1
    assert dropped[0][0] is bad
    assert dropped[0][1]


def test_filter_items_on_empty_list():
    assert filter_items([]) == ([], [])
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_copyright_guard.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.guards'`

- [ ] **Step 3: 구현**

`src/guards/__init__.py` — 빈 파일.

`src/guards/copyright_guard.py`:
```python
"""인용 한도·출처·이미지 규칙을 검증한다.

이 가드는 자르지 않는다. 통과시키거나 폐기한다.
요약이 한도를 넘었다는 것은 우리가 요약을 못 했다는 뜻이고,
그 상태로 자르면 남의 글 앞부분을 그대로 싣는 것과 같기 때문이다.

이 모듈은 파일시스템을 모른다. 항목 하나만 보고 판정한다.
"""
import re

from src.models import Item

MAX_SUMMARY_CHARS = 200
MAX_SUMMARY_SENTENCES = 2

_SENTENCE_END = re.compile(r"(?<=[.!?。？！])\s+")
_IMAGE_PATTERNS = (
    re.compile(r"<img\b", re.I),
    re.compile(r"!\[[^\]]*\]\("),
    re.compile(r"https?://\S+\.(?:jpe?g|png|gif|webp|avif|bmp)\b", re.I),
)


def _sentence_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return len([p for p in _SENTENCE_END.split(stripped) if p.strip()])


def _has_image(text: str) -> bool:
    return any(p.search(text or "") for p in _IMAGE_PATTERNS)


def violations(item: Item) -> list[str]:
    """위반 사유 목록. 빈 리스트면 통과."""
    reasons: list[str] = []

    # 출처는 등급을 가리지 않고 필요하다 — A는 공공기관, B는 원매체.
    if item.grade in ("A", "B"):
        if not item.source_name or not item.source_url:
            reasons.append("출처 누락 (source_name·source_url 둘 다 필요)")

    # 인용 한도는 남의 글을 옮기는 B등급에만 적용한다.
    if item.grade == "B":
        if len(item.summary) > MAX_SUMMARY_CHARS:
            reasons.append(
                f"인용 한도 초과: {len(item.summary)}자 > {MAX_SUMMARY_CHARS}자")
        n = _sentence_count(item.summary)
        if n > MAX_SUMMARY_SENTENCES:
            reasons.append(
                f"인용 한도 초과: {n}문장 > {MAX_SUMMARY_SENTENCES}문장")

    # 해설 기사인데 본문이 없으면 기사가 아니다.
    if item.grade == "C" and not (item.body_md or "").strip():
        reasons.append("C등급인데 본문(body_md)이 비었다")

    if _has_image(item.summary) or _has_image(item.body_md or ""):
        reasons.append("원문 이미지 임베드 금지 (자체 실사·공식 배포본만 허용)")

    return reasons


def filter_items(
    items: list[Item],
) -> tuple[list[Item], list[tuple[Item, list[str]]]]:
    kept: list[Item] = []
    dropped: list[tuple[Item, list[str]]] = []
    for item in items:
        reasons = violations(item)
        if reasons:
            dropped.append((item, reasons))
        else:
            kept.append(item)
    return kept, dropped
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_copyright_guard.py -v
```
Expected: PASS (18 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/guards/__init__.py src/guards/copyright_guard.py tests/test_copyright_guard.py
git commit -m "feat: 저작권 가드

한도를 넘은 인용은 자르지 않고 폐기한다 — 자르면 남의 글 앞부분을
그대로 싣는 것과 같다. 이미지 임베드는 등급을 가리지 않고 막는다."
```

---

## Task 7: 중복·재발행 가드

같은 것을 두 번 내지 않는다. 배치 안의 중복은 **묶어서 대표 1건 + 관련 보도**로 만들고, 과거에 이미 낸 것은 **버린다**. 인덱스를 읽지 못하면 발행을 멈춘다.

**Files:**
- Create: `src/guards/dup_guard.py`
- Create: `tests/test_dup_guard.py`

**Interfaces:**
- Consumes: `src.models.Item`, `src.models.title_tokens`, `src.models.jaccard`
- Produces:
  - `src.guards.dup_guard.SIMILARITY_THRESHOLD: float` (= 0.7)
  - `src.guards.dup_guard.RECENT_DAYS: int` (= 30)
  - `src.guards.dup_guard.IndexUnavailable(Exception)`
  - `src.guards.dup_guard.PublishedIndex` — `load(path) -> PublishedIndex` (classmethod), `contains(item) -> bool`, `add(item, day) -> None`, `save(path) -> None`
  - `src.guards.dup_guard.cluster_batch(items: list[Item], threshold: float = 0.7) -> list[Item]` — 대표 항목들. 대표의 `related`에 흡수된 항목 id가 들어간다
  - `src.guards.dup_guard.filter_unpublished(items: list[Item], index: PublishedIndex) -> tuple[list[Item], list[Item]]` — `(신규, 기발행)`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_dup_guard.py`:
```python
import json

import pytest

from src.guards.dup_guard import (PublishedIndex, IndexUnavailable,
                                  cluster_batch, filter_unpublished)
from src.models import Item

NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, source_name="A"):
    from src.models import title_hash
    return Item(id=item_id, grade="B", region="guam", section="news",
                title=title, summary="s", source_name=source_name,
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash=title_hash(title))


# --- 배치 내 클러스터링 ---

def test_identical_titles_collapse_to_one():
    items = [make("1", "괌 신규 취항 확정"), make("2", "괌 신규 취항 확정", "B")]
    result = cluster_batch(items)
    assert len(result) == 1
    assert result[0].related == ["2"]


def test_similar_titles_collapse_and_record_related():
    items = [make("1", "괌 신규 취항 노선 확정 발표"),
             make("2", "괌 신규 취항 노선 확정", "B"),
             make("3", "괌 신규 취항 노선 확정 소식", "C")]
    result = cluster_batch(items)
    assert len(result) == 1
    assert sorted(result[0].related) == ["2", "3"]


def test_different_titles_are_kept_separately():
    items = [make("1", "괌 신규 취항 확정"), make("2", "제주 해수욕장 개장 연기")]
    assert len(cluster_batch(items)) == 2


def test_cluster_keeps_first_as_representative():
    items = [make("1", "괌 신규 취항 확정"), make("2", "괌 신규 취항 확정", "B")]
    assert cluster_batch(items)[0].id == "1"


def test_cluster_on_empty_list():
    assert cluster_batch([]) == []


# --- 발행 이력 대조 ---

def test_missing_index_file_is_treated_as_first_run(tmp_path):
    index = PublishedIndex.load(str(tmp_path / "nope.json"))
    assert index.contains(make("1", "아무거나")) is False


def test_corrupt_index_file_raises_fail_closed(tmp_path):
    path = tmp_path / "published_index.json"
    path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(IndexUnavailable):
        PublishedIndex.load(str(path))


def test_previously_published_id_is_filtered_out(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("1", "괌 신규 취항 확정"), "2026-08-30")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished([make("1", "괌 신규 취항 확정")], reloaded)
    assert fresh == []
    assert len(seen) == 1


def test_same_story_different_url_is_caught_by_title(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("1", "괌 신규 취항 노선 확정 발표"), "2026-08-30")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished(
        [make("999", "괌 신규 취항 노선 확정")], reloaded)
    assert fresh == []
    assert len(seen) == 1


def test_unrelated_new_story_passes(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("1", "괌 신규 취항 확정"), "2026-08-30")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished(
        [make("2", "라오스 비자 규정 변경")], reloaded)
    assert len(fresh) == 1
    assert seen == []


def test_save_prunes_titles_older_than_thirty_days(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("old", "아주 오래된 소식 제목"), "2026-01-01")
    index.add(make("new", "최근 소식 제목"), "2026-08-30")
    index.save(path)

    data = json.loads(open(path, encoding="utf-8").read())
    assert {r["id"] for r in data["recent"]} == {"new"}
    # id 는 영구 보관한다 — 오래된 기사라도 재발행은 막아야 한다
    assert set(data["ids"]) == {"old", "new"}


def test_save_folds_duplicate_ids_in_recent(tmp_path):
    """같은 날 빌드를 두 번 돌려도 recent 가 부풀지 않아야 한다."""
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    item = make("dup", "같은 기사 제목")
    index.add(item, "2026-08-30")
    index.add(item, "2026-08-30")
    index.save(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data["recent"]) == 1


def test_permanently_kept_id_still_blocks_old_story(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("old", "아주 오래된 소식 제목"), "2026-01-01")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished(
        [make("old", "아주 오래된 소식 제목")], reloaded)
    assert fresh == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_dup_guard.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.guards.dup_guard'`

- [ ] **Step 3: 구현**

`src/guards/dup_guard.py`:
```python
"""같은 것을 두 번 내지 않는다.

두 가지 다른 일을 한다.
- cluster_batch: 오늘 들어온 것들 중 같은 사건을 묶는다. 버리지 않고 대표 1건 +
  나머지는 '관련 보도' 링크로 만든다. 여러 매체가 같은 사건을 보도한 것은
  중복이 아니라 그 사건이 중요하다는 신호다.
- filter_unpublished: 과거에 이미 낸 것을 버린다. 이건 진짜 중복이다.

인덱스 파일이 깨져 있으면 예외를 던진다. 읽기 실패를 '중복 없음'으로
해석하면 재발행 사고가 난다.
"""
import json
import os
from datetime import date, timedelta

from src.models import Item, jaccard, title_tokens

SIMILARITY_THRESHOLD = 0.7
RECENT_DAYS = 30


class IndexUnavailable(Exception):
    """발행 이력을 읽을 수 없다. 발행을 중단해야 한다."""


class PublishedIndex:
    """발행 이력. id 는 영구 보관하고 제목은 최근 30일만 유지한다.

    id 를 영구 보관하는 이유: 오래된 기사라도 같은 URL 이 다시 들어오면
    재발행이다. 제목을 30일만 유지하는 이유: 유사도 비교 비용이 무한히
    커지는 것을 막기 위해서다.
    """

    def __init__(self, ids: set[str], recent: list[dict]):
        self.ids = ids
        self.recent = recent
        self._token_cache = [
            (r["id"], title_tokens(r["title"])) for r in recent
        ]

    @classmethod
    def load(cls, path: str) -> "PublishedIndex":
        if not os.path.exists(path):
            return cls(set(), [])  # 최초 실행
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls(set(data.get("ids") or []), list(data.get("recent") or []))
        except Exception as e:
            raise IndexUnavailable(
                f"발행 이력을 읽지 못했다 ({path}): {type(e).__name__}: {e}. "
                f"중복 판정이 불가능하므로 발행을 중단한다.") from e

    def contains(self, item: Item) -> bool:
        if item.id in self.ids:
            return True
        tokens = title_tokens(item.title)
        return any(
            jaccard(tokens, known) >= SIMILARITY_THRESHOLD
            for _, known in self._token_cache
        )

    def add(self, item: Item, day: str) -> None:
        self.ids.add(item.id)
        self.recent.append({"id": item.id, "title": item.title, "date": day})
        self._token_cache.append((item.id, title_tokens(item.title)))

    def save(self, path: str) -> None:
        cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
        # 같은 날 빌드를 두 번 돌리면 같은 id 가 recent 에 두 번 쌓인다. id 로 접는다.
        by_id = {r["id"]: r for r in self.recent if r.get("date", "") >= cutoff}
        pruned = list(by_id.values())
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ids": sorted(self.ids), "recent": pruned}, f,
                      ensure_ascii=False, indent=2)


def cluster_batch(items: list[Item],
                  threshold: float = SIMILARITY_THRESHOLD) -> list[Item]:
    """배치 안의 같은 사건을 묶는다. 먼저 온 항목이 대표가 된다."""
    representatives: list[Item] = []
    rep_tokens: list[set[str]] = []

    for item in items:
        tokens = title_tokens(item.title)
        for rep, known in zip(representatives, rep_tokens):
            if jaccard(tokens, known) >= threshold:
                rep.related.append(item.id)
                break
        else:
            representatives.append(item)
            rep_tokens.append(tokens)

    return representatives


def filter_unpublished(items: list[Item],
                       index: PublishedIndex) -> tuple[list[Item], list[Item]]:
    fresh: list[Item] = []
    seen: list[Item] = []
    for item in items:
        (seen if index.contains(item) else fresh).append(item)
    return fresh, seen
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_dup_guard.py -v
```
Expected: PASS (14 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/guards/dup_guard.py tests/test_dup_guard.py
git commit -m "feat: 중복·재발행 가드

배치 내 같은 사건은 묶어서 대표+관련보도로, 과거 발행분은 폐기.
인덱스를 읽지 못하면 예외를 던져 발행을 멈춘다 (fail-closed)."
```

---

## Task 8: 등급 분류와 C등급 후보 선정

수집된 항목에 등급을 매기고, 오늘 사람이 검수할 해설 기사 후보를 최대 5건 고른다.

**Files:**
- Create: `src/grade.py`
- Create: `tests/test_grade.py`

**Interfaces:**
- Consumes: `src.models.Item`
- Produces:
  - `src.grade.FLIGHT_KEYWORDS: tuple[str, ...]`
  - `src.grade.MAX_C_PER_DAY: int` (= 5)
  - `src.grade.classify(item: Item) -> str` — `"A"` 또는 `"B"`
  - `src.grade.apply_grades(items: list[Item]) -> list[Item]` — 제자리에서 grade 설정 후 같은 리스트 반환
  - `src.grade.is_flight_event(title: str) -> bool`
  - `src.grade.pick_c_candidates(items: list[Item], trending: list[str], max_n: int = 5) -> list[tuple[Item, str]]` — `(항목, 선정사유)` 목록

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_grade.py`:
```python
from src.grade import (classify, apply_grades, is_flight_event,
                       pick_c_candidates, MAX_C_PER_DAY)
from src.models import Item

NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, section="news", related=None):
    return Item(id=item_id, grade="B", region="guam", section=section,
                title=title, summary="s", source_name="A",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h",
                related=list(related or []))


def test_data_section_is_grade_a():
    assert classify(make("1", "오늘의 환율", section="data")) == "A"


def test_news_section_is_grade_b():
    assert classify(make("1", "괌 소식", section="news")) == "B"


def test_flight_section_is_grade_b():
    assert classify(make("1", "괌 항공 소식", section="flight")) == "B"


def test_apply_grades_mutates_in_place():
    items = [make("1", "환율", section="data"), make("2", "뉴스")]
    apply_grades(items)
    assert [i.grade for i in items] == ["A", "B"]


def test_apply_grades_moves_flight_stories_to_the_flight_section():
    items = [make("1", "진에어 괌 노선 신규 취항")]
    apply_grades(items)
    assert items[0].section == "flight"


def test_apply_grades_leaves_ordinary_news_in_news():
    items = [make("1", "투몬 해변 청소 행사")]
    apply_grades(items)
    assert items[0].section == "news"


def test_apply_grades_does_not_move_data_items():
    items = [make("1", "오늘의 환율 — 1 USD 신규 취항", section="data")]
    apply_grades(items)
    assert items[0].section == "data"


def test_is_flight_event_detects_korean_terms():
    assert is_flight_event("진에어 괌 노선 신규 취항")
    assert is_flight_event("대한항공 괌 노선 증편")
    assert is_flight_event("티웨이 괌 노선 감편 결정")


def test_is_flight_event_detects_english_terms():
    assert is_flight_event("United adds new nonstop route to Guam")
    assert is_flight_event("Korean Air to launch Guam service")


def test_is_flight_event_ignores_unrelated_titles():
    assert not is_flight_event("투몬 해변 청소 행사")


# --- 후보 선정 우선순위: ①3개 이상 매체 ②트렌드 ③항공 ---

def test_cluster_of_three_outlets_is_a_candidate():
    items = [make("1", "괌 호텔 요금 인상", related=["2", "3"])]
    picked = pick_c_candidates(items, trending=[])
    assert [i.id for i, _ in picked] == ["1"]
    assert "매체" in picked[0][1]


def test_cluster_of_two_outlets_is_not_enough():
    items = [make("1", "괌 호텔 요금 인상", related=["2"])]
    assert pick_c_candidates(items, trending=[]) == []


def test_trending_keyword_match_is_a_candidate():
    items = [make("1", "사이판 마나가하 섬 입장료 변경")]
    picked = pick_c_candidates(items, trending=["마나가하"])
    assert [i.id for i, _ in picked] == ["1"]
    assert "검색" in picked[0][1]


def test_flight_event_is_a_candidate():
    items = [make("1", "진에어 괌 노선 신규 취항", section="flight")]
    picked = pick_c_candidates(items, trending=[])
    assert [i.id for i, _ in picked] == ["1"]
    assert "항공" in picked[0][1]


def test_priority_order_when_over_the_cap():
    """상한을 넘으면 3매체 > 트렌드 > 항공 순으로 남는다."""
    items = (
        [make(f"f{i}", f"진에어 {i}호 노선 신규 취항", section="flight")
         for i in range(4)]
        + [make(f"t{i}", f"마나가하 소식 {i}") for i in range(4)]
        + [make(f"c{i}", f"클러스터 기사 {i}", related=["x", "y"])
           for i in range(4)]
    )
    picked = pick_c_candidates(items, trending=["마나가하"], max_n=5)
    ids = [i.id for i, _ in picked]
    assert len(ids) == 5
    assert ids[:4] == ["c0", "c1", "c2", "c3"]
    assert ids[4].startswith("t")


def test_never_exceeds_the_daily_cap():
    items = [make(f"c{i}", f"클러스터 {i}", related=["x", "y"])
             for i in range(20)]
    assert len(pick_c_candidates(items, trending=[])) == MAX_C_PER_DAY


def test_item_qualifying_twice_appears_once():
    items = [make("1", "진에어 괌 노선 신규 취항", section="flight",
                  related=["2", "3"])]
    picked = pick_c_candidates(items, trending=["괌"])
    assert len(picked) == 1


def test_grade_a_items_are_never_c_candidates():
    """환율 같은 사실 데이터에 해설을 붙일 이유가 없다."""
    item = make("1", "오늘의 환율 — 1 USD", section="data", related=["2", "3"])
    item.grade = "A"
    assert pick_c_candidates([item], trending=[]) == []


def test_empty_input_yields_no_candidates():
    assert pick_c_candidates([], trending=["괌"]) == []
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_grade.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.grade'`

- [ ] **Step 3: 구현**

`src/grade.py`:
```python
"""등급을 매기고 오늘 검수할 해설 기사 후보를 고른다.

C등급 후보 상한(5건)이 있는 이유: 검수량이 하루 감당 가능한 양을 넘으면
검수 자체가 중단된다. 상한이 없는 검수 큐는 곧 아무도 안 보는 큐가 된다.
"""
from src.models import Item

MAX_C_PER_DAY = 5
MIN_OUTLETS_FOR_CLUSTER = 3  # 대표 1 + related 2 = 3개 매체

FLIGHT_KEYWORDS = (
    "취항", "증편", "감편", "신규 노선", "노선 확대", "운항 중단", "직항",
    "new route", "new service", "nonstop", "adds flight", "launch",
    "increase frequency", "suspend service",
)


def classify(item: Item) -> str:
    """사실 데이터인가 인용인가. 해설(C)은 여기서 정하지 않는다."""
    return "A" if item.section == "data" else "B"


def apply_grades(items: list[Item]) -> list[Item]:
    for item in items:
        item.grade = classify(item)
        # 항공 노선 변동 기사는 항공 섹션으로 옮긴다. 전 지역 항공 페이지의 재료가
        # 되고, 여행객이 예약 결정에 직접 쓰는 정보라 따로 모을 값어치가 있다.
        if item.section == "news" and is_flight_event(item.title):
            item.section = "flight"
    return items


def is_flight_event(title: str) -> bool:
    lowered = title.lower()
    return any(k.lower() in lowered for k in FLIGHT_KEYWORDS)


def pick_c_candidates(items: list[Item], trending: list[str],
                      max_n: int = MAX_C_PER_DAY) -> list[tuple[Item, str]]:
    """해설 기사 후보를 우선순위대로 고른다.

    우선순위: ①3개 이상 매체가 보도 ②검색 급상승 키워드와 겹침 ③항공 노선 변동.
    셋 다 해당해도 한 번만 뽑히고, 가장 앞선 사유가 기록된다.
    """
    lowered_trending = [t.lower() for t in trending if t]

    by_cluster: list[tuple[Item, str]] = []
    by_trend: list[tuple[Item, str]] = []
    by_flight: list[tuple[Item, str]] = []

    for item in items:
        if item.grade == "A":
            continue  # 사실 데이터에 해설을 붙이지 않는다

        outlets = 1 + len(item.related)
        if outlets >= MIN_OUTLETS_FOR_CLUSTER:
            by_cluster.append((item, f"{outlets}개 매체가 보도"))
            continue

        lowered_title = item.title.lower()
        hit = next((t for t in lowered_trending if t in lowered_title), None)
        if hit:
            by_trend.append((item, f"검색 급상승 키워드 '{hit}'"))
            continue

        if is_flight_event(item.title):
            by_flight.append((item, "항공 노선 변동"))

    return (by_cluster + by_trend + by_flight)[:max_n]
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_grade.py -v
```
Expected: PASS (20 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/grade.py tests/test_grade.py
git commit -m "feat: 등급 분류와 C등급 후보 선정

후보에 하루 5건 상한을 둔다 — 상한 없는 검수 큐는 곧 아무도 안 보는 큐가 된다."
```

---

## Task 9: 편집 오케스트레이터

수집 원본을 읽어 가드·등급·클러스터를 통과시키고 발행 대상 항목과 검수 초안을 만든다.

**Files:**
- Create: `src/edit.py`
- Create: `tests/test_edit.py`

**Interfaces:**
- Consumes: `src.models.item_from_dict`/`item_to_dict`, `src.grade.apply_grades`/`pick_c_candidates`, `src.guards.copyright_guard.filter_items`, `src.guards.dup_guard.PublishedIndex`/`cluster_batch`/`filter_unpublished`
- Produces:
  - `src.edit.edit_items(raw_items: list[Item], index: PublishedIndex, trending: list[str]) -> dict` — `{"publish": [Item], "c_candidates": [(Item, str)], "dropped": [(Item, [str])], "duplicates": [Item]}`
  - `src.edit.write_drafts(review_dir: str, candidates: list[tuple[Item, str]], day: str) -> list[str]` — 만든 파일 경로들
  - `src.edit.purge_stale_drafts(review_dir: str, today: str, max_age_days: int = 2) -> list[str]` — 지운 파일 경로들
  - `src.edit.load_trending(data_dir: str) -> list[str]` — `data/trending.json` 에서 급상승 키워드를 읽는다. 파일이 없으면 빈 리스트
  - `src.edit.main(data_dir: str = "data", review_dir: str = "content/review") -> int`

**급상승 키워드 배선에 관한 결정:** C등급 후보 규칙 ②(검색 급상승 키워드)는 네이버 데이터랩 값이 필요한데, 데이터랩은 이 세션의 MCP 도구로만 접근되고 GitHub Actions 러너에는 없다. 그래서 `edit` 은 **`data/trending.json` 이라는 파일 이음매**만 읽는다. 파일이 없으면 규칙 ②는 조용히 건너뛰고 ①③으로만 후보를 고른다 — 파이프라인은 정상 동작한다. 이 파일을 채우는 일은 6단계(검수 워크플로) 소관이다. 배선을 지금 뚫어두는 이유는, 나중에 붙일 때 `edit` 을 고치지 않아도 되게 하기 위해서다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_edit.py`:
```python
from pathlib import Path

from src.edit import (edit_items, write_drafts, purge_stale_drafts,
                      load_trending)
from src.guards.dup_guard import PublishedIndex
from src.models import Item, title_hash

NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, section="news", summary="한 문장.", related=None):
    return Item(id=item_id, grade="B", region="guam", section=section,
                title=title, summary=summary, source_name="Guam Post",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash=title_hash(title),
                related=list(related or []))


def empty_index():
    return PublishedIndex(set(), [])


def test_clean_items_reach_publish():
    result = edit_items([make("1", "괌 소식 하나")], empty_index(), [])
    assert [i.id for i in result["publish"]] == ["1"]


def test_copyright_violation_is_dropped_not_published():
    bad = make("1", "괌 소식", summary="가" * 300)
    result = edit_items([bad], empty_index(), [])
    assert result["publish"] == []
    assert len(result["dropped"]) == 1


def test_data_section_gets_grade_a():
    item = make("1", "오늘의 환율 — 1 USD", section="data")
    result = edit_items([item], empty_index(), [])
    assert result["publish"][0].grade == "A"


def test_same_story_from_two_outlets_collapses():
    items = [make("1", "괌 신규 취항 노선 확정"),
             make("2", "괌 신규 취항 노선 확정")]
    result = edit_items(items, empty_index(), [])
    assert len(result["publish"]) == 1
    assert result["publish"][0].related == ["2"]


def test_previously_published_item_is_filtered():
    index = empty_index()
    index.add(make("1", "괌 신규 취항 노선 확정"), "2026-08-30")
    result = edit_items([make("1", "괌 신규 취항 노선 확정")], index, [])
    assert result["publish"] == []
    assert len(result["duplicates"]) == 1


def test_c_candidates_are_selected():
    items = [make("1", "괌 호텔 요금 인상", related=[])]
    items[0].related = ["2", "3"]
    result = edit_items(items, empty_index(), [])
    assert len(result["c_candidates"]) == 1


def test_empty_input_produces_empty_result():
    result = edit_items([], empty_index(), [])
    assert result == {"publish": [], "c_candidates": [], "dropped": [],
                      "duplicates": []}


def test_write_drafts_creates_one_markdown_per_candidate(tmp_path):
    candidates = [(make("abc", "괌 호텔 요금 인상"), "3개 매체가 보도")]
    paths = write_drafts(str(tmp_path), candidates, "2026-08-31")
    assert len(paths) == 1
    text = Path(paths[0]).read_text(encoding="utf-8")
    assert "괌 호텔 요금 인상" in text
    assert "3개 매체가 보도" in text
    assert "status: draft" in text


def test_write_drafts_filename_carries_date_and_id(tmp_path):
    candidates = [(make("abc", "제목"), "사유")]
    paths = write_drafts(str(tmp_path), candidates, "2026-08-31")
    assert Path(paths[0]).name == "2026-08-31_abc.md"


def test_purge_removes_drafts_older_than_two_days(tmp_path):
    (tmp_path / "2026-08-25_old.md").write_text("x", encoding="utf-8")
    (tmp_path / "2026-08-30_recent.md").write_text("x", encoding="utf-8")
    removed = purge_stale_drafts(str(tmp_path), "2026-08-31")
    assert [Path(p).name for p in removed] == ["2026-08-25_old.md"]
    assert (tmp_path / "2026-08-30_recent.md").exists()


def test_purge_keeps_draft_exactly_at_the_boundary(tmp_path):
    (tmp_path / "2026-08-29_edge.md").write_text("x", encoding="utf-8")
    assert purge_stale_drafts(str(tmp_path), "2026-08-31") == []


def test_purge_ignores_files_with_unexpected_names(tmp_path):
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert purge_stale_drafts(str(tmp_path), "2026-08-31") == []
    assert (tmp_path / "README.md").exists()


def test_purge_on_missing_directory_is_not_an_error(tmp_path):
    assert purge_stale_drafts(str(tmp_path / "nope"), "2026-08-31") == []


# --- 급상승 키워드 이음매 ---

def test_trending_file_missing_yields_empty_list(tmp_path):
    """파일이 없어도 파이프라인은 돌아야 한다. 규칙 ②만 건너뛴다."""
    assert load_trending(str(tmp_path)) == []


def test_trending_file_is_read(tmp_path):
    (tmp_path / "trending.json").write_text(
        '{"keywords": ["마나가하", "괌 환율"]}', encoding="utf-8")
    assert load_trending(str(tmp_path)) == ["마나가하", "괌 환율"]


def test_corrupt_trending_file_does_not_break_the_build(tmp_path):
    """키워드는 있으면 좋은 것이지 없으면 못 도는 것이 아니다."""
    (tmp_path / "trending.json").write_text("{ broken", encoding="utf-8")
    assert load_trending(str(tmp_path)) == []


def test_trending_keyword_produces_a_candidate_end_to_end():
    item = make("1", "사이판 마나가하 입장료 인상")
    result = edit_items([item], empty_index(), ["마나가하"])
    assert len(result["c_candidates"]) == 1
    assert "마나가하" in result["c_candidates"][0][1]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_edit.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.edit'`

- [ ] **Step 3: 구현**

`src/edit.py`:
```python
"""수집 원본을 발행 가능한 항목으로 만든다.

순서가 중요하다.
  등급 → 저작권 가드 → 배치 클러스터 → 발행이력 대조 → C후보 선정
저작권 가드를 클러스터보다 먼저 두는 이유: 위반 항목이 대표가 되면
클러스터 전체가 사라진다.

이 모듈은 발행 이력을 읽기만 하고 쓰지 않는다. 인덱스 갱신은 build 가
실제로 페이지를 만든 뒤에 한다 — 안 나간 것을 발행됨으로 기록하지 않기 위해서다.
"""
import json
import os
import re
import sys
from datetime import date, timedelta

from src.grade import apply_grades, pick_c_candidates
from src.guards.copyright_guard import filter_items
from src.guards.dup_guard import (PublishedIndex, cluster_batch,
                                  filter_unpublished)
from src.models import Item, item_from_dict, item_to_dict

DRAFT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)\.md$")
DRAFT_MAX_AGE_DAYS = 2  # 48시간


def edit_items(raw_items: list[Item], index: PublishedIndex,
               trending: list[str]) -> dict:
    apply_grades(raw_items)
    kept, dropped = filter_items(raw_items)
    clustered = cluster_batch(kept)
    fresh, duplicates = filter_unpublished(clustered, index)
    candidates = pick_c_candidates(fresh, trending)
    return {"publish": fresh, "c_candidates": candidates,
            "dropped": dropped, "duplicates": duplicates}


def write_drafts(review_dir: str, candidates: list[tuple[Item, str]],
                 day: str) -> list[str]:
    """검수 대기 초안을 마크다운으로 남긴다.

    본문은 비워둔다. 사람(또는 클로드 예약작업)이 채우고 status 를 approved
    로 바꿔야 발행된다.
    """
    os.makedirs(review_dir, exist_ok=True)
    paths = []
    for item, reason in candidates:
        path = os.path.join(review_dir, f"{day}_{item.id}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"---\n"
                f"id: {item.id}\n"
                f"region: {item.region}\n"
                f"section: {item.section}\n"
                f"title: {item.title}\n"
                f"source_name: {item.source_name}\n"
                f"source_url: {item.source_url}\n"
                f"reason: {reason}\n"
                f"status: draft\n"
                f"---\n\n"
                f"<!-- 여기에 해설을 쓴 뒤 위 status 를 approved 로 바꾼다. -->\n"
                f"<!-- 48시간 안에 승인하지 않으면 자동 폐기된다. -->\n"
            )
        paths.append(path)
    return paths


def purge_stale_drafts(review_dir: str, today: str,
                       max_age_days: int = DRAFT_MAX_AGE_DAYS) -> list[str]:
    """48시간 지난 미승인 초안을 지운다.

    신선도가 지난 뉴스이기도 하고, 오래된 초안이 쌓이면 검수 자체를 안 하게 된다.
    """
    if not os.path.isdir(review_dir):
        return []

    cutoff = (date.fromisoformat(today) - timedelta(days=max_age_days)).isoformat()
    removed = []
    for name in sorted(os.listdir(review_dir)):
        m = DRAFT_NAME.match(name)
        if not m:
            continue  # 우리가 만든 초안이 아니다
        if m.group(1) < cutoff:
            path = os.path.join(review_dir, name)
            os.remove(path)
            removed.append(path)
    return removed


def load_trending(data_dir: str) -> list[str]:
    """검색 급상승 키워드를 읽는다. 없으면 빈 리스트.

    네이버 데이터랩은 Actions 러너에서 접근할 수 없으므로 파일 이음매로 받는다.
    없거나 깨져도 파이프라인을 멈추지 않는다 — 키워드는 후보 선정의 보조
    신호이지 발행의 전제조건이 아니다.
    """
    path = os.path.join(data_dir, "trending.json")
    try:
        with open(path, encoding="utf-8") as f:
            return list(json.load(f).get("keywords") or [])
    except Exception:
        return []


def main(data_dir: str = "data", review_dir: str = "content/review") -> int:
    today = date.today().isoformat()
    raw_path = os.path.join(data_dir, "raw", today, "items.json")
    if not os.path.exists(raw_path):
        print(f"수집 결과가 없다: {raw_path}. collect 를 먼저 돌려라.",
              file=sys.stderr)
        return 1

    with open(raw_path, encoding="utf-8") as f:
        raw_items = [item_from_dict(d) for d in json.load(f)]

    index = PublishedIndex.load(os.path.join(data_dir, "published_index.json"))
    result = edit_items(raw_items, index, load_trending(data_dir))

    out_dir = os.path.join(data_dir, "items")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{today}.jsonl"), "w",
              encoding="utf-8") as f:
        for item in result["publish"]:
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")

    purged = purge_stale_drafts(review_dir, today)
    drafts = write_drafts(review_dir, result["c_candidates"], today)

    print(f"편집 완료: 발행대상 {len(result['publish'])}건, "
          f"검수초안 {len(drafts)}건, 폐기 {len(result['dropped'])}건, "
          f"중복 {len(result['duplicates'])}건, 만료초안 삭제 {len(purged)}건")
    for item, reasons in result["dropped"]:
        print(f"  폐기 [{item.source_name}] {item.title[:40]} — "
              f"{'; '.join(reasons)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_edit.py -v
```
Expected: PASS (19 passed)

- [ ] **Step 5: 실제 수집 결과로 돌려본다**

```bash
cd ~/여행신문 && .venv/bin/python -m src.edit
```
Expected: `편집 완료: 발행대상 N건, ...`
폐기 건수가 발행대상보다 많으면 Task 3의 요약 추출이 제대로 안 되고 있다는 뜻이다 — stderr 의 폐기 사유를 읽고 고친다.

- [ ] **Step 6: 커밋**

```bash
git add src/edit.py tests/test_edit.py
git commit -m "feat: 편집 오케스트레이터

가드를 클러스터보다 먼저 태워 위반 항목이 대표가 되는 것을 막는다.
발행 이력은 읽기만 한다 — 갱신은 실제로 페이지가 나간 뒤 build 가 한다."
```

---

## Task 10: 사이트 렌더러와 템플릿

정규화된 항목을 정적 HTML 로 만든다. 디자인 컨셉은 **와플 격자** — 7개 지역이 격자 칸에 놓이고, 지역 페이지 최상단에 오늘의 데이터 패널이 고정된다.

**Files:**
- Create: `src/render/__init__.py`, `src/render/site.py`
- Create: `src/render/templates/base.html`, `index.html`, `region.html`, `article.html`, `section.html`, `about.html`
- Create: `tests/test_render_site.py`

**Interfaces:**
- Consumes: `src.models.Item`
- Produces:
  - `src.render.site.SITE_NAME: str` (= "와플트립"), `SITE_TAGLINE: str` (= "매일 아침 여행 뉴스"), `SITE_URL: str` (= "https://waffletrip.com")
  - `src.render.site.REGION_NAMES: dict[str, str]`, `PRODUCT_LINKS: dict[str, str]`
  - `src.render.site.slugify(text: str) -> str`
  - `src.render.site.article_url(item: Item) -> str` — 선행 슬래시로 시작하고 슬래시로 끝나는 경로
  - `src.render.site.group_by_region(items: list[Item]) -> dict[str, list[Item]]`
  - `src.render.site.split_panel(items: list[Item]) -> tuple[list[Item], list[Item]]` — `(A등급 데이터, 나머지 기사)`
  - `src.render.site.render_site(items: list[Item], out_dir: str, today: str) -> list[str]` — 생성한 파일 경로들

스펙 9절이 요구하는 페이지를 전부 만든다: 홈 `/`, 지역 7개 `/<region>/`, 기사 `/<region>/<slug>/`, 항공 모음 `/flight/`, 데이터 대시보드 `/data/`, 매체 소개 `/about/`. **`/about/` 은 선택이 아니다** — 우리 수집 봇의 User-Agent 가 `(+https://waffletrip.com/about/)` 로 자기를 밝히고 있어서, 그 주소가 404 면 우리가 다른 사이트에 거짓 신원을 제시하는 셈이 된다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render_site.py`:
```python
from pathlib import Path

from src.models import Item
from src.render.site import (slugify, article_url, group_by_region,
                             split_panel, render_site, REGION_NAMES)

NOW = "2026-08-31T05:00:00+09:00"
TODAY = "2026-08-31"


def make(item_id, title, region="guam", grade="B", section="news"):
    return Item(id=item_id, grade=grade, region=region, section=section,
                title=title, summary="요약 문장.", source_name="Guam Post",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h")


def test_slugify_keeps_hangul():
    assert slugify("괌 신규 취항") == "괌-신규-취항"


def test_slugify_lowercases_and_strips_punctuation():
    assert slugify("United ADDS a Flight!") == "united-adds-a-flight"


def test_slugify_collapses_repeated_separators():
    assert slugify("괌   ---  취항") == "괌-취항"


def test_slugify_truncates_long_titles():
    assert len(slugify("가" * 100)) <= 40


def test_slugify_on_empty_string_yields_placeholder():
    assert slugify("") == "article"


def test_article_url_has_region_and_id_prefix():
    url = article_url(make("abcdef1234567890", "괌 신규 취항"))
    assert url == "/guam/abcdef12-괌-신규-취항/"


def test_group_by_region_buckets_items():
    grouped = group_by_region([make("1", "a", "guam"), make("2", "b", "jeju")])
    assert set(grouped) == {"guam", "jeju"}


def test_group_by_region_covers_only_regions_present():
    grouped = group_by_region([make("1", "a", "guam")])
    assert "hawaii" not in grouped


def test_split_panel_separates_grade_a():
    data = make("1", "오늘의 환율", grade="A", section="data")
    news = make("2", "괌 소식")
    panel, articles = split_panel([data, news])
    assert [i.id for i in panel] == ["1"]
    assert [i.id for i in articles] == ["2"]


def test_render_site_writes_index(tmp_path):
    render_site([make("1", "괌 신규 취항")], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "와플트립" in html
    assert "매일 아침 여행 뉴스" in html
    assert "괌 신규 취항" in html


def test_render_site_writes_region_page(tmp_path):
    render_site([make("1", "괌 신규 취항")], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert REGION_NAMES["guam"] in html
    assert "괌 신규 취항" in html


def test_render_site_writes_article_page(tmp_path):
    item = make("abcdef1234567890", "괌 신규 취항")
    render_site([item], str(tmp_path), TODAY)
    path = tmp_path / "guam" / "abcdef12-괌-신규-취항" / "index.html"
    assert path.exists()
    assert "Guam Post" in path.read_text(encoding="utf-8")


def test_article_page_links_to_the_original_source(tmp_path):
    item = make("abcdef1234567890", "괌 신규 취항")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "abcdef12-괌-신규-취항" /
            "index.html").read_text(encoding="utf-8")
    assert "https://example.com/abcdef1234567890" in html


def test_region_page_shows_data_panel(tmp_path):
    items = [make("1", "오늘의 환율 — 1 USD", grade="A", section="data"),
             make("2", "괌 신규 취항")]
    render_site(items, str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert "오늘의 환율" in html


def test_region_page_links_to_the_product_site(tmp_path):
    from src.render.site import PRODUCT_LINKS
    render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert PRODUCT_LINKS["guam"] in html


def test_render_site_returns_every_path_it_wrote(tmp_path):
    paths = render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    assert all(Path(p).exists() for p in paths)
    assert any(p.endswith("index.html") for p in paths)


def test_render_site_with_no_items_still_writes_index(tmp_path):
    render_site([], str(tmp_path), TODAY)
    assert (tmp_path / "index.html").exists()


def test_render_site_writes_flight_page(tmp_path):
    item = make("1", "진에어 괌 노선 신규 취항", section="flight")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "flight" / "index.html").read_text(encoding="utf-8")
    assert "진에어 괌 노선 신규 취항" in html


def test_flight_page_excludes_ordinary_news(tmp_path):
    render_site([make("1", "투몬 해변 청소")], str(tmp_path), TODAY)
    html = (tmp_path / "flight" / "index.html").read_text(encoding="utf-8")
    assert "투몬 해변 청소" not in html


def test_render_site_writes_data_page(tmp_path):
    item = make("1", "오늘의 환율 — 1 USD", grade="A", section="data")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "data" / "index.html").read_text(encoding="utf-8")
    assert "오늘의 환율" in html


def test_render_site_writes_about_page(tmp_path):
    """봇의 User-Agent 가 이 주소를 가리킨다. 404 면 거짓 신원이 된다."""
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert "저작권" in html
    assert "robots.txt" in html


def test_nav_links_to_flight_data_and_about(tmp_path):
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    for href in ('href="/flight/"', 'href="/data/"', 'href="/about/"'):
        assert href in html


def test_every_region_key_has_a_korean_name_and_product_link():
    from src.render.site import PRODUCT_LINKS
    from src.models import REGIONS
    assert set(REGION_NAMES) == set(REGIONS)
    assert set(PRODUCT_LINKS) == set(REGIONS)
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_render_site.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.render'`

- [ ] **Step 3: 템플릿 작성**

`src/render/templates/base.html`:
```html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}{{ site_name }}{% endblock %}</title>
<meta name="description" content="{% block description %}{{ site_tagline }} — 괌·사이판·하와이·베트남·코타키나발루·라오스·제주{% endblock %}">
<link rel="alternate" type="application/rss+xml" title="{{ site_name }}" href="/rss.xml">
<style>
  :root{
    --bg:#FDFBF7; --card:#FFFFFF; --ink:#2B2118; --muted:#7A6A57;
    --gold:#C98A2E; --line:#E8DFD0;
  }
  @media (prefers-color-scheme: dark){
    :root{ --bg:#1A1512; --card:#231C17; --ink:#F2EAE0; --muted:#A6957F;
           --gold:#E0A648; --line:#3A2F26; }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",
                   "Malgun Gothic",sans-serif;line-height:1.65}
  .wrap{max-width:960px;margin:0 auto;padding:0 20px}
  header{border-bottom:3px solid var(--gold);padding:28px 0 20px}
  .brand{font-size:30px;font-weight:800;letter-spacing:-.02em;
         text-decoration:none;color:var(--ink)}
  .tagline{color:var(--muted);font-size:14px;margin-top:4px}
  .date{color:var(--gold);font-size:13px;font-weight:600;margin-top:10px}
  nav{margin:18px 0 0;display:flex;flex-wrap:wrap;gap:8px}
  nav a{font-size:14px;padding:5px 12px;border:1px solid var(--line);
        border-radius:999px;text-decoration:none;color:var(--muted)}
  nav a:hover{border-color:var(--gold);color:var(--gold)}
  h1{font-size:24px;margin:32px 0 4px}
  h2{font-size:18px;margin:28px 0 10px}
  /* 와플 격자 */
  .waffle{display:grid;gap:14px;margin:20px 0;
          grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
  .cell{background:var(--card);border:1px solid var(--line);border-radius:10px;
        padding:16px}
  .cell a.cell-title{font-weight:700;text-decoration:none;color:var(--ink)}
  .panel{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0;padding:14px;
         background:var(--card);border:1px solid var(--line);border-radius:10px}
  .panel .fact{font-size:14px}
  .panel .fact b{color:var(--gold)}
  article.row{padding:16px 0;border-bottom:1px solid var(--line)}
  article.row h3{margin:0 0 6px;font-size:17px}
  article.row h3 a{text-decoration:none;color:var(--ink)}
  article.row h3 a:hover{color:var(--gold)}
  .meta{font-size:12px;color:var(--muted)}
  .summary{margin:6px 0 0;color:var(--ink)}
  .cta{display:block;margin:28px 0;padding:16px;border-radius:10px;
       background:var(--gold);color:#fff;text-decoration:none;font-weight:700;
       text-align:center}
  footer{margin:48px 0 32px;padding-top:18px;border-top:1px solid var(--line);
         font-size:13px;color:var(--muted)}
  .src{font-size:13px}
  .src a{color:var(--gold)}
</style>
</head>
<body>
<header><div class="wrap">
  <a class="brand" href="/">{{ site_name }}</a>
  <div class="tagline">{{ site_tagline }}</div>
  <div class="date">{{ today }}</div>
  <nav>
    {% for key, name in region_names.items() %}<a href="/{{ key }}/">{{ name }}</a>{% endfor %}
    <a href="/flight/">항공</a><a href="/data/">데이터</a><a href="/about/">소개</a>
  </nav>
</div></header>
<main class="wrap">{% block content %}{% endblock %}</main>
<footer><div class="wrap">
  {{ site_name }} · {{ site_tagline }}<br>
  기사 요약은 원문 출처를 표기하고 링크로 연결합니다. 저작권은 각 매체에 있습니다.
</div></footer>
</body>
</html>
```

`src/render/templates/index.html`:
```html
{% extends "base.html" %}
{% block content %}
<h1>오늘의 여행 소식</h1>
<div class="waffle">
{% for key, name in region_names.items() %}
  <div class="cell">
    <a class="cell-title" href="/{{ key }}/">{{ name }}</a>
    <div class="meta">{{ counts.get(key, 0) }}건</div>
    {% for item in top_by_region.get(key, []) %}
      <div style="margin-top:8px">
        <a href="{{ article_urls[item.id] }}" style="font-size:14px;text-decoration:none;color:var(--muted)">{{ item.title }}</a>
      </div>
    {% endfor %}
  </div>
{% endfor %}
</div>
{% endblock %}
```

`src/render/templates/region.html`:
```html
{% extends "base.html" %}
{% block title %}{{ region_name }} 여행 소식 — {{ site_name }}{% endblock %}
{% block description %}{{ region_name }} 여행 뉴스·항공·환율·날씨를 매일 정리합니다.{% endblock %}
{% block content %}
<h1>{{ region_name }}</h1>
{% if panel %}
<div class="panel">
  {% for fact in panel %}<div class="fact"><b>{{ fact.title }}</b> · {{ fact.summary }}</div>{% endfor %}
</div>
{% endif %}
{% if articles %}
  {% for item in articles %}
  <article class="row">
    <h3><a href="{{ article_urls[item.id] }}">{{ item.title }}</a></h3>
    <div class="meta">{{ item.source_name }} · {{ item.published_at[:10] }}</div>
    {% if item.summary %}<p class="summary">{{ item.summary }}</p>{% endif %}
  </article>
  {% endfor %}
{% else %}
  <p class="meta">오늘 {{ region_name }} 소식은 아직 없습니다.</p>
{% endif %}
<a class="cta" href="{{ product_link }}">{{ region_name }} 여행 상품 보러가기</a>
{% endblock %}
{# 상품 링크가 이 사이트를 만드는 사업적 이유다. 모든 지역 페이지에 넣는다. #}
```

`src/render/templates/article.html`:
```html
{% extends "base.html" %}
{% block title %}{{ item.title }} — {{ site_name }}{% endblock %}
{% block description %}{{ item.summary or item.title }}{% endblock %}
{% block content %}
<h1>{{ item.title }}</h1>
<div class="meta">{{ region_name }} · {{ item.source_name }} · {{ item.published_at[:10] }}</div>
{% if item.summary %}<p class="summary">{{ item.summary }}</p>{% endif %}
{% if item.body_md %}<div>{{ item.body_md }}</div>{% endif %}
{% if item.source_url %}
<p class="src">원문 보기: <a href="{{ item.source_url }}" rel="nofollow noopener" target="_blank">{{ item.source_name }}</a></p>
{% endif %}
{% if related %}
<h2>관련 보도</h2>
<ul class="src">{% for r in related %}<li><a href="{{ r.source_url }}" rel="nofollow noopener" target="_blank">{{ r.source_name }}</a></li>{% endfor %}</ul>
{% endif %}
<a class="cta" href="{{ product_link }}">{{ region_name }} 여행 상품 보러가기</a>
{% endblock %}
```

`src/render/templates/section.html`:
```html
{% extends "base.html" %}
{% block title %}{{ section_title }} — {{ site_name }}{% endblock %}
{% block description %}{{ section_desc }}{% endblock %}
{% block content %}
<h1>{{ section_title }}</h1>
<p class="meta">{{ section_desc }}</p>
{% if items %}
  {% for item in items %}
  <article class="row">
    <h3>{% if item.grade == 'A' %}{{ item.title }}{% else %}<a href="{{ article_urls[item.id] }}">{{ item.title }}</a>{% endif %}</h3>
    <div class="meta">{{ region_names.get(item.region, item.region) }} · {{ item.source_name }} · {{ item.published_at[:10] }}</div>
    {% if item.summary %}<p class="summary">{{ item.summary }}</p>{% endif %}
  </article>
  {% endfor %}
{% else %}
  <p class="meta">아직 모인 소식이 없습니다.</p>
{% endif %}
{% endblock %}
```

`src/render/templates/about.html`:
```html
{% extends "base.html" %}
{% block title %}매체 소개 — {{ site_name }}{% endblock %}
{% block description %}{{ site_name }} 소개와 저작권·수집 정책{% endblock %}
{% block content %}
<h1>{{ site_name }} 소개</h1>
<p>{{ site_name }}은 괌·사이판·하와이·베트남·코타키나발루·라오스·제주 일곱 곳의 여행 정보를 매일 아침 정리해 전하는 여행 정보 매체입니다.</p>

<h2>기사를 만드는 방식</h2>
<p>세 종류의 글을 싣습니다.</p>
<ul>
  <li><b>사실 데이터</b> — 환율·날씨·여행경보처럼 공공기관과 공식 발표에서 받아 그대로 전하는 값입니다.</li>
  <li><b>큐레이션</b> — 다른 매체가 보도한 소식의 제목과 짧은 요약에 <b>원문 링크</b>를 답니다. 전문은 옮기지 않습니다.</li>
  <li><b>해설</b> — 저희가 직접 쓴 정리와 분석입니다.</li>
</ul>

<h2>저작권</h2>
<p>인용한 기사의 저작권은 각 매체에 있습니다. 저희는 제목과 두 문장 이내의 요약만 인용하고 반드시 출처를 밝혀 원문으로 연결합니다. 원문 이미지는 사용하지 않습니다. 삭제나 수정을 원하시는 매체는 아래로 연락 주시면 확인 후 조치하겠습니다.</p>

<h2>수집 정책</h2>
<p>저희 수집 봇은 <code>WaffleTripBot/1.0</code> 으로 자기를 밝히고, 각 사이트의 <code>robots.txt</code> 를 확인해 금지된 경로는 수집하지 않습니다. 공개된 RSS 피드만 읽습니다.</p>

<h2>연락처</h2>
<p><a href="mailto:peoplay@thepeoplay.com">peoplay@thepeoplay.com</a></p>
{% endblock %}
```

- [ ] **Step 4: 렌더러 구현**

`src/render/__init__.py` — 빈 파일.

`src/render/site.py`:
```python
"""정규화된 항목을 정적 HTML 로 만든다.

이 모듈은 수집 과정을 모른다. 항목 리스트와 출력 경로만 받는다.
디자인 컨셉은 와플 격자 — 7개 지역이 격자 칸에 놓인다.
"""
import os
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.models import Item

SITE_NAME = "와플트립"
SITE_TAGLINE = "매일 아침 여행 뉴스"
SITE_URL = "https://waffletrip.com"

REGION_NAMES = {
    "guam": "괌", "saipan": "사이판", "hawaii": "하와이",
    "vietnam": "베트남", "kota": "코타키나발루", "laos": "라오스",
    "jeju": "제주",
}

PRODUCT_LINKS = {
    "guam": "https://guamplay.com",
    "saipan": "https://guamplay.com",
    "hawaii": "https://guamplay.com",
    "vietnam": "https://guamplay.com",
    "kota": "https://guamplay.com",
    "laos": "https://guamplay.com",
    "jeju": "https://guamplay.com",
}

TOP_PER_REGION = 3
_SLUG_STRIP = re.compile(r"[^\w가-힣]+", re.UNICODE)
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )


def slugify(text: str) -> str:
    slug = _SLUG_STRIP.sub("-", (text or "").lower()).strip("-")
    return slug[:40].strip("-") or "article"


def article_url(item: Item) -> str:
    return f"/{item.region}/{item.id[:8]}-{slugify(item.title)}/"


def group_by_region(items: list[Item]) -> dict[str, list[Item]]:
    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.region, []).append(item)
    return grouped


def split_panel(items: list[Item]) -> tuple[list[Item], list[Item]]:
    """A등급(사실 데이터)은 상단 패널로, 나머지는 기사 목록으로."""
    panel = [i for i in items if i.grade == "A"]
    articles = [i for i in items if i.grade != "A"]
    return panel, articles


def _write(path: str, html: str, written: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    written.append(path)


def render_site(items: list[Item], out_dir: str, today: str) -> list[str]:
    env = _env()
    written: list[str] = []
    urls = {i.id: article_url(i) for i in items}
    by_id = {i.id: i for i in items}
    grouped = group_by_region(items)

    common = {
        "site_name": SITE_NAME, "site_tagline": SITE_TAGLINE,
        "site_url": SITE_URL, "region_names": REGION_NAMES,
        "today": today, "article_urls": urls,
    }

    # 홈 — 와플 격자
    top_by_region = {
        key: [i for i in group if i.grade != "A"][:TOP_PER_REGION]
        for key, group in grouped.items()
    }
    _write(
        os.path.join(out_dir, "index.html"),
        env.get_template("index.html").render(
            counts={k: len(v) for k, v in grouped.items()},
            top_by_region=top_by_region, **common),
        written,
    )

    # 지역 페이지 — 소식이 없는 지역도 만든다. 링크가 깨지면 안 된다.
    for key, name in REGION_NAMES.items():
        panel, articles = split_panel(grouped.get(key, []))
        _write(
            os.path.join(out_dir, key, "index.html"),
            env.get_template("region.html").render(
                region_key=key, region_name=name, panel=panel,
                articles=articles, product_link=PRODUCT_LINKS[key], **common),
            written,
        )

    # 항공 모음 — 지역을 가로지른다. 예약 결정에 직접 쓰는 정보라 따로 모은다.
    _write(
        os.path.join(out_dir, "flight", "index.html"),
        env.get_template("section.html").render(
            section_title="항공 소식",
            section_desc="일곱 개 지역의 신규취항·증편·감편을 한자리에 모았습니다.",
            items=[i for i in items if i.section == "flight"], **common),
        written,
    )

    # 데이터 대시보드 — 매일 값이 바뀌는 사실 데이터만 모은다.
    _write(
        os.path.join(out_dir, "data", "index.html"),
        env.get_template("section.html").render(
            section_title="여행 데이터",
            section_desc="환율을 비롯한 오늘의 여행 실용 데이터입니다.",
            items=[i for i in items if i.grade == "A"], **common),
        written,
    )

    # 매체 소개 — 우리 봇의 User-Agent 가 이 주소를 가리키므로 반드시 존재해야 한다.
    _write(
        os.path.join(out_dir, "about", "index.html"),
        env.get_template("about.html").render(**common),
        written,
    )

    # 기사 페이지 — A등급은 패널에만 나오므로 개별 페이지를 만들지 않는다.
    for item in items:
        if item.grade == "A":
            continue
        related = [by_id[r] for r in item.related if r in by_id]
        _write(
            os.path.join(out_dir, urls[item.id].strip("/"), "index.html"),
            env.get_template("article.html").render(
                item=item, related=related,
                region_name=REGION_NAMES.get(item.region, item.region),
                product_link=PRODUCT_LINKS.get(item.region, SITE_URL),
                **common),
            written,
        )

    return written
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_render_site.py -v
```
Expected: PASS (23 passed)

- [ ] **Step 6: 커밋**

```bash
git add src/render/ tests/test_render_site.py
git commit -m "feat: 사이트 렌더러와 와플 격자 템플릿

소식이 없는 지역도 페이지를 만든다 — 네비게이션 링크가 깨지면 안 된다.
모든 지역·기사 페이지에 상품 링크를 넣는다."
```

---

## Task 11: RSS·sitemap·robots·CNAME

검색엔진과 피드 리더가 사이트를 읽을 수 있게 만든다. 커스텀 도메인 연결에 필요한 `CNAME`도 여기서 만든다.

**Files:**
- Create: `src/render/feeds.py`
- Create: `tests/test_render_feeds.py`

**Interfaces:**
- Consumes: `src.models.Item`, `src.render.site.article_url`/`SITE_NAME`/`SITE_TAGLINE`/`SITE_URL`
- Produces:
  - `src.render.feeds.render_rss(items: list[Item], out_dir: str, built_at: str) -> str` — 쓴 파일 경로
  - `src.render.feeds.render_sitemap(items: list[Item], out_dir: str, today: str) -> str`
  - `src.render.feeds.render_robots(out_dir: str) -> str`
  - `src.render.feeds.render_cname(out_dir: str, domain: str = "waffletrip.com") -> str`
  - `src.render.feeds.RSS_MAX_ITEMS: int` (= 50)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_render_feeds.py`:
```python
import xml.etree.ElementTree as ET
from pathlib import Path

from src.models import Item
from src.render.feeds import (render_rss, render_sitemap, render_robots,
                              render_cname, RSS_MAX_ITEMS)

NOW = "2026-08-31T05:00:00+09:00"
TODAY = "2026-08-31"


def make(item_id, title, region="guam", grade="B"):
    return Item(id=item_id, grade=grade, region=region, section="news",
                title=title, summary="요약 문장.", source_name="Guam Post",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h")


def test_rss_is_wellformed_xml(tmp_path):
    path = render_rss([make("1", "괌 신규 취항")], str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    assert root.tag == "rss"


def test_rss_contains_one_item_per_article(tmp_path):
    items = [make("1", "첫 소식"), make("2", "둘째 소식")]
    path = render_rss(items, str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    assert len(root.findall("./channel/item")) == 2


def test_rss_excludes_grade_a_data(tmp_path):
    items = [make("1", "괌 소식"), make("2", "오늘의 환율", grade="A")]
    path = render_rss(items, str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    titles = [e.text for e in root.findall("./channel/item/title")]
    assert titles == ["괌 소식"]


def test_rss_links_are_absolute(tmp_path):
    path = render_rss([make("abcdef1234", "괌 소식")], str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    link = root.find("./channel/item/link").text
    assert link.startswith("https://waffletrip.com/guam/")


def test_rss_caps_the_item_count(tmp_path):
    items = [make(str(i), f"소식 {i}") for i in range(RSS_MAX_ITEMS + 10)]
    path = render_rss(items, str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    assert len(root.findall("./channel/item")) == RSS_MAX_ITEMS


def test_rss_escapes_special_characters_in_titles(tmp_path):
    path = render_rss([make("1", "A & B <소식>")], str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    assert root.find("./channel/item/title").text == "A & B <소식>"


def test_rss_with_no_items_is_still_valid(tmp_path):
    path = render_rss([], str(tmp_path), NOW)
    assert ET.parse(path).getroot().tag == "rss"


def test_sitemap_is_wellformed_and_lists_home(tmp_path):
    path = render_sitemap([make("1", "괌 소식")], str(tmp_path), TODAY)
    text = Path(path).read_text(encoding="utf-8")
    assert "<urlset" in text
    assert "https://waffletrip.com/" in text


def test_sitemap_lists_every_region(tmp_path):
    path = render_sitemap([], str(tmp_path), TODAY)
    text = Path(path).read_text(encoding="utf-8")
    for region in ("guam", "saipan", "hawaii", "vietnam", "kota", "laos", "jeju"):
        assert f"https://waffletrip.com/{region}/" in text


def test_sitemap_lists_the_standing_pages(tmp_path):
    path = render_sitemap([], str(tmp_path), TODAY)
    text = Path(path).read_text(encoding="utf-8")
    for page in ("flight", "data", "about"):
        assert f"https://waffletrip.com/{page}/" in text


def test_sitemap_lists_article_urls(tmp_path):
    path = render_sitemap([make("abcdef1234", "괌 소식")], str(tmp_path), TODAY)
    assert "/guam/abcdef12-" in Path(path).read_text(encoding="utf-8")


def test_robots_allows_crawling_and_points_at_sitemap(tmp_path):
    text = Path(render_robots(str(tmp_path))).read_text(encoding="utf-8")
    assert "Allow: /" in text
    assert "Sitemap: https://waffletrip.com/sitemap.xml" in text


def test_cname_holds_the_bare_domain(tmp_path):
    text = Path(render_cname(str(tmp_path))).read_text(encoding="utf-8")
    assert text.strip() == "waffletrip.com"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_render_feeds.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.render.feeds'`

- [ ] **Step 3: 구현**

`src/render/feeds.py`:
```python
"""RSS·sitemap·robots·CNAME 을 만든다.

RSS 는 문자열 조립 대신 ElementTree 로 만든다. 제목에 & 나 < 가 들어와도
깨지지 않게 하려면 이스케이프를 직접 하지 않는 편이 안전하다.
"""
import os
import xml.etree.ElementTree as ET
from email.utils import format_datetime
from datetime import datetime

from src.models import Item
from src.render.site import (REGION_NAMES, SITE_NAME, SITE_TAGLINE, SITE_URL,
                             article_url)

RSS_MAX_ITEMS = 50


def _rfc822(iso: str) -> str:
    try:
        return format_datetime(datetime.fromisoformat(iso))
    except ValueError:
        return iso


def _write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def render_rss(items: list[Item], out_dir: str, built_at: str) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = SITE_NAME
    ET.SubElement(channel, "link").text = SITE_URL + "/"
    ET.SubElement(channel, "description").text = SITE_TAGLINE
    ET.SubElement(channel, "language").text = "ko"
    ET.SubElement(channel, "lastBuildDate").text = _rfc822(built_at)

    # A등급(환율·날씨)은 매일 값만 바뀌는 데이터라 피드에 넣으면 소음이 된다.
    articles = [i for i in items if i.grade != "A"][:RSS_MAX_ITEMS]

    for item in articles:
        node = ET.SubElement(channel, "item")
        link = SITE_URL + article_url(item)
        ET.SubElement(node, "title").text = item.title
        ET.SubElement(node, "link").text = link
        ET.SubElement(node, "guid", {"isPermaLink": "true"}).text = link
        ET.SubElement(node, "description").text = item.summary or item.title
        ET.SubElement(node, "pubDate").text = _rfc822(item.published_at)
        ET.SubElement(node, "source").text = item.source_name

    xml = ET.tostring(rss, encoding="unicode")
    return _write(os.path.join(out_dir, "rss.xml"),
                  '<?xml version="1.0" encoding="UTF-8"?>\n' + xml)


def render_sitemap(items: list[Item], out_dir: str, today: str) -> str:
    urls = [SITE_URL + "/"]
    urls += [f"{SITE_URL}/{key}/" for key in REGION_NAMES]
    urls += [f"{SITE_URL}/{page}/" for page in ("flight", "data", "about")]
    urls += [SITE_URL + article_url(i) for i in items if i.grade != "A"]

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        lines.append(f"  <url><loc>{url}</loc><lastmod>{today}</lastmod></url>")
    lines.append("</urlset>")
    return _write(os.path.join(out_dir, "sitemap.xml"), "\n".join(lines) + "\n")


def render_robots(out_dir: str) -> str:
    text = (f"User-agent: *\nAllow: /\n\n"
            f"Sitemap: {SITE_URL}/sitemap.xml\n")
    return _write(os.path.join(out_dir, "robots.txt"), text)


def render_cname(out_dir: str, domain: str = "waffletrip.com") -> str:
    """GitHub Pages 커스텀 도메인 설정 파일.

    빌드마다 다시 만든다. public/ 을 통째로 갈아엎어도 도메인이 풀리지 않게
    하기 위해서다.
    """
    return _write(os.path.join(out_dir, "CNAME"), domain + "\n")
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_render_feeds.py -v
```
Expected: PASS (13 passed)

- [ ] **Step 5: 커밋**

```bash
git add src/render/feeds.py tests/test_render_feeds.py
git commit -m "feat: RSS·sitemap·robots·CNAME

RSS 는 ElementTree 로 만들어 제목의 특수문자에 깨지지 않게 한다.
CNAME 을 빌드마다 다시 써서 public/ 을 갈아엎어도 도메인이 풀리지 않는다."
```

---

## Task 12: 빌드 오케스트레이터

최근 항목을 모아 사이트를 만들고, **성공적으로 만든 뒤에만** 발행 이력을 갱신한다. 수집이 0건인 날에 기존 사이트를 지우지 않는 것이 이 태스크의 핵심 요구사항이다.

**Files:**
- Create: `src/build.py`
- Create: `tests/test_build.py`

**Interfaces:**
- Consumes: `src.models.item_from_dict`, `src.render.site.render_site`, `src.render.feeds.render_rss`/`render_sitemap`/`render_robots`/`render_cname`, `src.guards.dup_guard.PublishedIndex`
- Produces:
  - `src.build.SITE_WINDOW_DAYS: int` (= 14)
  - `src.build.load_recent_items(items_dir: str, today: str, days: int = 14) -> list[Item]` — 최신순 정렬
  - `src.build.site_has_content(out_dir: str) -> bool`
  - `src.build.build(items: list[Item], out_dir: str, today: str, built_at: str) -> list[str]`
  - `src.build.main(data_dir: str = "data", out_dir: str = "public") -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_build.py`:
```python
import json
from pathlib import Path

from src.build import (load_recent_items, site_has_content, build,
                       SITE_WINDOW_DAYS)
from src.models import Item, item_to_dict

TODAY = "2026-08-31"
NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, published="2026-08-31T05:00:00+09:00", grade="B"):
    return Item(id=item_id, grade=grade, region="guam", section="news",
                title=title, summary="요약.", source_name="Guam Post",
                source_url=f"https://example.com/{item_id}",
                published_at=published, collected_at=NOW, status="draft",
                title_hash="h")


def write_day(items_dir: Path, day: str, items):
    items_dir.mkdir(parents=True, exist_ok=True)
    with open(items_dir / f"{day}.jsonl", "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")


def test_loads_todays_items(tmp_path):
    write_day(tmp_path, TODAY, [make("1", "오늘 소식")])
    assert [i.id for i in load_recent_items(str(tmp_path), TODAY)] == ["1"]


def test_loads_items_from_previous_days_in_window(tmp_path):
    write_day(tmp_path, TODAY, [make("1", "오늘")])
    write_day(tmp_path, "2026-08-25", [make("2", "엿새 전",
                                            published="2026-08-25T05:00:00+09:00")])
    assert len(load_recent_items(str(tmp_path), TODAY)) == 2


def test_ignores_items_outside_the_window(tmp_path):
    write_day(tmp_path, "2026-07-01", [make("old", "두 달 전")])
    assert load_recent_items(str(tmp_path), TODAY) == []


def test_sorts_newest_first(tmp_path):
    write_day(tmp_path, TODAY, [
        make("old", "예전", published="2026-08-28T05:00:00+09:00"),
        make("new", "최신", published="2026-08-31T09:00:00+09:00"),
    ])
    assert [i.id for i in load_recent_items(str(tmp_path), TODAY)] == ["new", "old"]


def test_missing_items_dir_is_not_an_error(tmp_path):
    assert load_recent_items(str(tmp_path / "nope"), TODAY) == []


def test_window_constant_is_two_weeks():
    assert SITE_WINDOW_DAYS == 14


def test_site_has_content_is_false_for_missing_dir(tmp_path):
    assert site_has_content(str(tmp_path / "nope")) is False


def test_site_has_content_is_true_when_index_exists(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    assert site_has_content(str(tmp_path)) is True


def test_build_writes_index_rss_sitemap_robots_cname(tmp_path):
    build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    for name in ("index.html", "rss.xml", "sitemap.xml", "robots.txt", "CNAME"):
        assert (tmp_path / name).exists(), name


def test_build_returns_the_paths_it_wrote(tmp_path):
    paths = build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    assert all(Path(p).exists() for p in paths)


def test_build_with_no_items_still_produces_a_site(tmp_path):
    """최초 실행에서 수집이 0건이어도 껍데기는 나와야 한다."""
    build([], str(tmp_path), TODAY, NOW)
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "guam" / "index.html").exists()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest tests/test_build.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.build'`

- [ ] **Step 3: 구현**

`src/build.py`:
```python
"""최근 항목을 모아 정적 사이트를 만든다.

두 가지를 지킨다.
- 수집이 0건인 날에 기존 사이트를 지우지 않는다. 빈 사이트를 배포하면
  어제까지 색인된 페이지가 전부 사라진다.
- 발행 이력은 사이트를 실제로 만든 뒤에 갱신한다. 안 나간 것을
  발행됨으로 기록하면 그 기사는 영영 못 나간다.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from src.guards.dup_guard import PublishedIndex
from src.models import Item, item_from_dict
from src.render.feeds import (render_cname, render_robots, render_rss,
                              render_sitemap)
from src.render.site import render_site

SITE_WINDOW_DAYS = 14
KST = timezone(timedelta(hours=9))


def load_recent_items(items_dir: str, today: str,
                      days: int = SITE_WINDOW_DAYS) -> list[Item]:
    """최근 days 일치 항목을 모아 최신순으로 정렬한다."""
    if not os.path.isdir(items_dir):
        return []

    start = date.fromisoformat(today) - timedelta(days=days)
    items: list[Item] = []

    for name in sorted(os.listdir(items_dir)):
        if not name.endswith(".jsonl"):
            continue
        day = name[:-len(".jsonl")]
        try:
            if date.fromisoformat(day) < start:
                continue
        except ValueError:
            continue  # 우리가 만든 파일이 아니다

        with open(os.path.join(items_dir, name), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(item_from_dict(json.loads(line)))

    items.sort(key=lambda i: i.published_at, reverse=True)
    return items


def site_has_content(out_dir: str) -> bool:
    return os.path.exists(os.path.join(out_dir, "index.html"))


def build(items: list[Item], out_dir: str, today: str,
          built_at: str) -> list[str]:
    written = render_site(items, out_dir, today)
    written.append(render_rss(items, out_dir, built_at))
    written.append(render_sitemap(items, out_dir, today))
    written.append(render_robots(out_dir))
    written.append(render_cname(out_dir))
    return written


def main(data_dir: str = "data", out_dir: str = "public") -> int:
    built_at = datetime.now(KST).isoformat()
    today = built_at[:10]

    items = load_recent_items(os.path.join(data_dir, "items"), today)

    if not items and site_has_content(out_dir):
        print("경고: 최근 항목이 0건이다. 기존 사이트를 그대로 둔다.",
              file=sys.stderr)
        return 0

    written = build(items, out_dir, today, built_at)

    # 사이트가 실제로 나온 뒤에만 발행 이력을 갱신한다.
    index_path = os.path.join(data_dir, "published_index.json")
    index = PublishedIndex.load(index_path)
    todays = [i for i in items if i.collected_at[:10] == today]
    for item in todays:
        index.add(item, today)
    index.save(index_path)

    print(f"빌드 완료: 항목 {len(items)}건 → 파일 {len(written)}개, "
          f"발행이력 +{len(todays)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
.venv/bin/python -m pytest tests/test_build.py -v
```
Expected: PASS (11 passed)

- [ ] **Step 5: 전체 파이프라인을 한 번에 돌려 눈으로 확인**

```bash
cd ~/여행신문
.venv/bin/python -m src.collect && \
.venv/bin/python -m src.edit && \
.venv/bin/python -m src.build && \
.venv/bin/python -m pytest -q
```
Expected: 세 줄의 완료 메시지 + 전체 테스트 통과.

브라우저로 열어 눈으로 본다:
```bash
open ~/여행신문/public/index.html
```
확인할 것: 와플 격자에 7개 지역이 모두 보이는가. 지역 페이지에 환율 패널이 뜨는가. 기사 제목을 누르면 개별 페이지로 가는가. 원문 링크가 실제 매체로 가는가. 상품 링크 버튼이 있는가.

- [ ] **Step 6: 커밋**

```bash
git add src/build.py tests/test_build.py
git commit -m "feat: 빌드 오케스트레이터

수집 0건인 날엔 기존 사이트를 유지한다 — 빈 사이트를 배포하면
색인된 페이지가 전부 사라진다. 발행 이력은 빌드 성공 뒤에만 갱신한다."
```

---

## Task 13: GitHub Actions 자동화와 Pages 배포

매일 05:00 KST 에 파이프라인을 돌리고 결과를 Pages 로 배포한다. 이 태스크가 끝나면 맥 전원과 무관하게 신문이 나온다.

**Files:**
- Create: `.github/workflows/daily.yml`
- Modify: `.gitignore` — `public/` 제외를 유지하되 `data/raw/`만 무시하고 `data/items/`·`data/published_index.json`은 커밋 대상으로 둔다

**Interfaces:**
- Consumes: `src.collect.main`, `src.edit.main`, `src.build.main` (CLI 진입점)
- Produces: 배포된 사이트. 이 태스크는 코드 인터페이스를 만들지 않는다.

- [ ] **Step 1: .gitignore 조정**

발행 이력과 정규화 항목은 **반드시 저장소에 남아야 한다.** Actions 실행마다 러너가 새로 만들어지므로 커밋하지 않으면 매일 첫 실행처럼 굴고 중복 방지가 무너진다.

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
public/
data/raw/
```

확인:
```bash
cd ~/여행신문 && git check-ignore -v data/published_index.json data/items 2>&1 || echo "무시되지 않음 — 정상"
```
Expected: `무시되지 않음 — 정상`

- [ ] **Step 2: 워크플로 작성**

`.github/workflows/daily.yml`:
```yaml
name: 매일 발행

on:
  schedule:
    # 05:00 KST = 20:00 UTC (전일). GitHub 스케줄은 UTC 기준이다.
    - cron: '0 20 * * *'
  workflow_dispatch:        # 수동 실행 버튼

permissions:
  contents: write           # 발행 이력 커밋
  pages: write              # Pages 배포
  id-token: write           # Pages 인증

concurrency:
  group: waffletrip-daily
  cancel-in-progress: false # 발행 중 취소는 이력만 어긋나게 만든다

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip

      - name: 의존성 설치
        run: pip install -r requirements.txt

      - name: 테스트
        run: python -m pytest -q

      - name: 수집
        run: python -m src.collect

      - name: 편집
        run: python -m src.edit

      - name: 빌드
        run: python -m src.build

      - name: 발행 이력 커밋
        run: |
          git config user.name  "waffletrip-bot"
          git config user.email "bot@waffletrip.com"
          git add data/items data/published_index.json content/review || true
          if git diff --cached --quiet; then
            echo "변경 없음 — 커밋 생략"
          else
            git commit -m "chore: $(date -u -d '9 hours' +%Y-%m-%d) 발행 기록"
            git push
          fi

      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: public

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 3: 워크플로 문법 검증**

```bash
cd ~/여행신문
.venv/bin/python -c "
import yaml, sys
d = yaml.safe_load(open('.github/workflows/daily.yml', encoding='utf-8'))
jobs = d['jobs']
assert 'build' in jobs and 'deploy' in jobs
# YAML 에서 on: 은 True 로 파싱된다 (YAML 1.1 불린)
trigger = d.get('on') or d.get(True)
assert trigger['schedule'][0]['cron'] == '0 20 * * *'
print('워크플로 문법 OK')
"
```
Expected: `워크플로 문법 OK`

- [ ] **Step 4: 커밋**

```bash
git add .github/workflows/daily.yml .gitignore
git commit -m "feat: 매일 05시 자동 발행 워크플로

발행 이력을 저장소에 커밋한다 — 러너가 매번 새로 뜨므로
커밋하지 않으면 매일 첫 실행처럼 굴고 중복 방지가 무너진다."
```

- [ ] **Step 5: 【사용자 작업】 GitHub 저장소 생성과 푸시**

저장소 생성과 푸시는 외부로 나가는 작업이므로 사용자가 직접 실행한다. 아래를 그대로 붙여넣으면 된다.

```bash
cd ~/여행신문 && ~/bin/gh repo create peoplay-k/waffletrip --private --source=. --remote=origin --push
```

- [ ] **Step 6: 【사용자 작업】 Pages 활성화**

GitHub 저장소 → **Settings → Pages → Build and deployment → Source** 를 **GitHub Actions** 로 바꾼다. 이걸 안 하면 배포 잡이 실패한다.

- [ ] **Step 7: 워크플로를 수동으로 한 번 돌려 확인**

```bash
cd ~/여행신문
~/bin/gh workflow run "매일 발행"
sleep 20 && ~/bin/gh run list --limit 1
```
그다음 완료될 때까지 지켜본다:
```bash
~/bin/gh run watch
```
Expected: build·deploy 두 잡 모두 성공. 실패하면 `~/bin/gh run view --log-failed` 로 원인을 본다.

배포된 사이트를 실제로 열어 확인한다 (커스텀 도메인 연결 전에는 `https://peoplay-k.github.io/waffletrip/`):
```bash
~/bin/gh run view --json url -q .url
```

- [ ] **Step 8: 【사용자 작업】 카페24 DNS 연결**

`waffletrip.com` 은 카페24 네임서버(`ns1.cafe24.co.kr`)를 쓰고 있고 A 레코드가 없다. 카페24 DNS 관리에서 아래를 넣는다.

| 타입 | 호스트 | 값 |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | peoplay-k.github.io |

DNS 전파 후 GitHub 저장소 **Settings → Pages → Custom domain** 에 `waffletrip.com` 을 넣고 **Enforce HTTPS** 를 켠다. `CNAME` 파일은 빌드가 매번 다시 쓰므로 사이트를 갈아엎어도 도메인이 풀리지 않는다.

전파 확인:
```bash
dig +short waffletrip.com A
```
Expected: 185.199.10x.153 네 줄.

- [ ] **Step 9: 최종 확인 — 전체가 손 안 대고 도는가**

```bash
cd ~/여행신문 && ~/bin/gh run list --limit 5
```
스케줄 실행이 붙기 시작하면 완료다. 아래 셋을 눈으로 확인한다.
1. `https://waffletrip.com` 이 열리고 오늘 날짜가 찍혀 있다.
2. 7개 지역 페이지가 전부 열리고 링크가 깨지지 않는다.
3. 다음 날 다시 열었을 때 **어제와 다른 기사**가 보인다. (같으면 수집이 멈춘 것이다.)

---

## 완료 기준

1~5단계가 끝나면 아래가 참이어야 한다.

- [ ] `python -m pytest` 전체 통과
- [ ] `waffletrip.com` 이 HTTPS 로 열린다
- [ ] 7개 지역 페이지가 전부 존재하고 상품 링크가 있다
- [ ] 매일 05:00 KST 에 맥 전원과 무관하게 갱신된다
- [ ] 같은 기사가 두 번 나오지 않는다
- [ ] 인용 한도를 넘은 항목이 발행되지 않는다
- [ ] 수집이 0건인 날에도 기존 사이트가 살아있다

## 다음 사이클 (이 계획 범위 밖)

6단계 검수 워크플로(클로드 예약작업 연동), 7단계 OSMU 확산(블로그·SNS·뉴스레터),
소스 확장(항공사 보도자료·여행경보·날씨), 네이버 서치어드바이저 등록.
각각 이 계획이 끝난 뒤 별도로 설계한다.
