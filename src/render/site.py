"""정규화된 항목을 정적 HTML 로 만든다.

이 모듈은 수집 과정을 모른다. 항목 리스트와 출력 경로만 받는다.
디자인 컨셉은 와플 격자 — 7개 지역이 격자 칸에 놓인다.
"""
from __future__ import annotations

import json
import os
import re
import shutil

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from src.desks import DESK_DUTIES, REGION_DESKS, byline_for
from src.photos import (assign as assign_photos, copy_into, load_manifest,
                        load_used, save_used)
from src.render.md import render as md_render
from src.cities import CITY_NAMES, CITY_REGION, cities_of, group_by_city
from src.topics import TOPIC_DESCS, TOPIC_NAMES, TOPICS, group_by_topic, topic_of

from src.models import Item

SITE_NAME = "와플트립"
SITE_TAGLINE = "매일 아침 여행 뉴스"
# 정식 주소. 커스텀 도메인이 붙기 전에는 실제로 열리는 곳을 가리켜야 한다 —
# canonical 이 안 열리는 도메인을 가리키면 검색엔진이 색인을 못 한다.
SITE_URL = os.environ.get("WAFFLE_SITE_URL", "https://waffletrip.com").rstrip("/")

from src.models import REGION_NAMES  # 정본은 models.py

# 지역별 상품 사이트. 확인된 것만 넣는다 — 다른 지역 페이지에 엉뚱한 브랜드를
# 붙이면 브랜드가 섞인다. 빈 값이면 상품 버튼을 그리지 않는다.
# 지역별 자사 상품 사이트.
#
# **소유가 확인된 곳만 넣는다.** 2026-09-01 에 사업자등록번호(220-88-17836)·
# 대표자명·여행업등록번호(제2015-33호)로 대조해 4곳을 확인했다.
#
# 빈 값 3개는 몰라서 비운 게 아니라 **일부러 비운 것이다.**
#   hawaii   — hawaiiplay.com 은 도메인 판매 안내 페이지다 (우리 것이 아니다)
#   vietnam  — vietnamplay.com 은 빈 사이트다
#   jeju     — jejuplay.com 은 제주 유흥 정보 사이트로, 전혀 다른 사업자다.
#              여기에 링크를 걸면 여행 신문이 유흥 사이트를 홍보하는 꼴이 된다.
#
# 나중에 실제 사이트가 생기면 그때 채운다. 확인 없이 채우지 않는다 —
# 예전에 전부 guamplay.com 으로 채워져 하와이 페이지에 괌 여행사가 붙어 있었다.
PRODUCT_LINKS = {
    "guam": "https://guamplay.com",
    "saipan": "https://saipanplay.com",
    "hawaii": "",
    "vietnam": "",
    "kota": "https://kotaplay.com",
    "laos": "https://laosplay.com",
    "jeju": "",
    # 아래 셋은 판매 상품이 없다. 독자를 부르는 지역이고
    # 상품 전환은 괌·사이판·코타·라오스가 맡는다.
    "japan": "",
    "thailand": "",
    "taiwan": "",
}

CONTACT_EMAIL = "peoplay@thepeoplay.com"

# 하위 경로 배포용 접두사. GitHub Pages 는 커스텀 도메인이 없으면
# https://<user>.github.io/<repo>/ 에서 서비스한다. 우리 링크는 전부 "/..." 로
# 시작하므로 브라우저가 그것을 **도메인 루트**에서 찾아 전부 404 가 난다.
# 사진도 기사 링크도 CSS 도 통째로 깨진다 — localhost 는 루트라 멀쩡해 보였다.
# 커스텀 도메인이 붙으면 빈 값으로 두면 된다.
BASE_PATH = os.environ.get("WAFFLE_BASE_PATH", "").rstrip("/")


def load_analytics(path: str = "analytics.yaml") -> dict:
    """방문 분석·검색 노출 설정. 없거나 깨져도 빌드는 돈다."""
    import yaml
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return {}
    return {k: str(v).strip() for k, v in data.items() if v}

# href="/..." src="/..." 만 바꾼다. "//cdn" 같은 프로토콜 상대 URL 은 건드리지 않는다.
_ABS_LINK = re.compile(r'(href|src)="/(?!/)')


def with_base(html: str, base: str = None) -> str:
    base = BASE_PATH if base is None else base.rstrip("/")
    if not base:
        return html
    return _ABS_LINK.sub(rf'\1="{base}/', html)

TOP_PER_REGION = 3

_HANGUL = re.compile(r"[가-힣]")


def front_order(articles: list) -> list:
    """첫 화면 순서. 한글 제목을 앞으로 당긴다.

    우리 독자는 한국어로 읽는다. 현지 매체(Beat of Hawaii, VnExpress 등)를
    인용하면 제목이 영문 그대로 들어오는데, 최신순으로만 세우면 이것들이
    톱기사와 헤드라인 띠를 차지한다. 한국어 신문 1면에 "Hurricane Lowell
    remains a powerful category 4 system" 이 톱으로 걸리는 꼴이었다.

    버리지는 않는다 — 현지발 소식은 국제면의 재료다. 앞자리만 양보시킨다.
    같은 묶음 안에서는 원래대로 최신순을 지킨다(정렬이 안정적이므로).
    """
    # 데이터 기사(환율·날씨)는 1면 톱이 아니다. 매일 나오는 표이지 그날의
    # 뉴스가 아니다. 사진 우선 규칙 때문에 톱으로 올라온 적이 있다.
    data = [a for a in articles if getattr(a, "section", "") == "data"]
    news = [a for a in articles if getattr(a, "section", "") != "data"]
    korean = [a for a in news if _HANGUL.search(a.title or "")]
    rest = [a for a in news if not _HANGUL.search(a.title or "")] + data
    # 한글 기사 안에서는 사진 있는 것을 앞으로. 신문 1면에는 사진 기사가 온다.
    # 사진이 붙는 기사가 전체의 일부뿐이라(자사 촬영본만 쓰므로) 최신순으로만
    # 세우면 1면이 글자만으로 채워지는 날이 생긴다.
    return ([a for a in korean if a.photo] + [a for a in korean if not a.photo]
            + rest)

# 데이터 패널을 짧게 줄인다. 요약문은 우리가 만든 것이라 형식을 안다
# (src/fetch/json_api.py). 형식이 안 맞으면 원문을 그대로 쓴다 —
# 줄이려다 정보를 잃는 것보다 길게 나오는 편이 낫다.
_WEATHER_RE = re.compile(
    r"\S+\s+(?P<city>\S+)\s+(?P<sky>[^,]+),\s*최고\s*(?P<hi>-?\d+)°C"
    r"\s*·\s*최저\s*(?P<lo>-?\d+)°C(?:\s*·\s*강수확률\s*(?P<rain>\d+)%)?")
_FX_RE = re.compile(r"기준\s+(?P<unit>[\d,]+)\s+(?P<cur>[A-Z]{3})\s*=\s*약\s*(?P<krw>[\d,.]+)원")


def compact_fact(summary: str) -> str:
    """긴 사실 문장을 패널 한 줄로 줄인다."""
    m = _WEATHER_RE.search(summary or "")
    if m:
        out = f"{m['hi']}° / {m['lo']}°  {m['sky'].strip()}"
        if m["rain"]:
            out += f"  ·  비 {m['rain']}%"
        return out
    m = _FX_RE.search(summary or "")
    if m:
        return f"{m['unit']} {m['cur']}  {m['krw']}원"
    return summary or ""
_SLUG_STRIP = re.compile(r"[^\w가-힣]+", re.UNICODE)
# 경로 조각에 쓸 수 있는 문자. id·region 이 오염돼도 out_dir 밖으로 못 나가게 한다.
_SAFE_SEGMENT = re.compile(r"[^A-Za-z0-9_-]")
# href 에 넣어도 되는 스킴. 남의 사이트에서 긁어온 URL 을 그대로 쓰면
# javascript: 링크가 만들어진다.
_ALLOWED_SCHEMES = ("http://", "https://")
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def safe_url(url: str) -> str:
    """href 에 넣어도 되는 URL 만 통과시킨다. 아니면 빈 문자열.

    수집한 링크는 남의 사이트가 준 값이다. Jinja 의 autoescape 는 HTML 특수문자만
    막고 URI 스킴은 거르지 않아서, javascript: 링크가 그대로 클릭 가능해진다.
    """
    stripped = (url or "").strip()
    if stripped.lower().startswith(_ALLOWED_SCHEMES):
        return stripped
    return ""


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["safe_url"] = safe_url
    # 해설 기사 본문. md.render 가 이스케이프를 먼저 하므로 안전하다.
    env.filters["md"] = lambda text: Markup(md_render(text))
    # 지역면 패널에서도 같은 압축을 쓴다. 항목명은 템플릿이 따로 보여준다.
    env.filters["compact"] = compact_fact
    # JSON-LD 는 이스케이프하면 &#34; 가 되어 파싱이 통째로 깨진다.
    # json.dumps 가 이미 안전한 문자열을 만든다.
    env.filters["ld"] = lambda t: Markup(t)
    # 샘플 표시는 제목에서 떼어 배지로 보낸다. 헤드라인마다 "[샘플]" 이 붙어
    # 있으면 지면이 통째로 미완성으로 보인다. 표시 자체는 없애지 않는다 —
    # 사이트가 공개돼 있어 실제 취재로 오인되면 안 된다.
    env.filters["clean_title"] = lambda t: (t or "").replace("[샘플] ", "", 1)
    env.tests["sample"] = lambda t: (t or "").startswith("[샘플]")
    return env


def slugify(text: str) -> str:
    slug = _SLUG_STRIP.sub("-", (text or "").lower()).strip("-")
    return slug[:40].strip("-") or "article"


def article_url(item: Item) -> str:
    """기사 경로. id·region 도 정제한다.

    제목은 slugify 가 이미 정제하지만 id·region 은 그대로 경로에 들어간다.
    둘 중 하나에 "../" 가 섞이면 출력 디렉터리 밖에 파일이 써진다. 지금은
    id 가 sha1 이고 region 이 검증된 값이라 도달할 수 없지만, 방어가 없는 것과
    도달 못 하는 것은 다르다.
    """
    region = _SAFE_SEGMENT.sub("", item.region) or "etc"
    ident = _SAFE_SEGMENT.sub("", item.id)[:8] or "0"
    return f"/{region}/{ident}-{slugify(item.title)}/"


def group_by_region(items: list[Item]) -> dict[str, list[Item]]:
    grouped: dict[str, list[Item]] = {}
    for item in items:
        grouped.setdefault(item.region, []).append(item)
    return grouped


def split_panel(items: list[Item]) -> tuple[list[Item], list[Item]]:
    """A등급(사실 데이터)은 상단 패널로, 나머지는 기사 목록으로."""
    panel = [i for i in items if i.grade == "A"]
    by_topic = group_by_topic(items)
    articles = [i for i in items if i.grade != "A"]
    return panel, articles


_OUT_DIR = ""      # render_site 가 설정한다. _write 한 곳에서만 쓴다.
ANALYTICS: dict = {}


def _page_url(path: str) -> str:
    """출력 파일 경로 → 정식 주소."""
    rel = os.path.relpath(path, _OUT_DIR) if _OUT_DIR else os.path.basename(path)
    rel = rel.replace(os.sep, "/")
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return f"{SITE_URL}{BASE_PATH}/{rel}"


def _write(path: str, html: str, written: list[str]) -> None:
    """한 곳에서만 접두사를 붙인다.

    템플릿마다 필터를 걸면 새 링크를 추가할 때마다 빠뜨리게 된다.
    실제로 사진·기사·CSS 링크가 통째로 깨진 채 배포됐다.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".html"):
        html = with_base(html)
        # canonical 과 og:url 은 페이지마다 달라야 한다. 템플릿은 홈 주소를
        # 기본값으로 넣고, 실제 주소는 여기서 한 번에 바로잡는다.
        url = _page_url(path)
        home = f"{SITE_URL}{BASE_PATH}/"
        if url != home:
            html = html.replace(f'rel="canonical" href="{home}"',
                                f'rel="canonical" href="{url}"')
            html = html.replace(f'property="og:url" content="{home}"',
                                f'property="og:url" content="{url}"')
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    written.append(path)


def _crumb_ld(item, urls: dict) -> str:
    """검색 결과에 경로를 보여준다 — 와플트립 › 일본 › 기사.

    지역면이 기사보다 위라는 사실을 기계에게도 알린다. 지역면이 색인에서
    기사와 나란히 놓이는 대신 상위 페이지로 이해된다.
    """
    base = SITE_URL + BASE_PATH
    region = REGION_NAMES.get(item.region, item.region)
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE_NAME,
             "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": region,
             "item": f"{base}/{item.region}/"},
            {"@type": "ListItem", "position": 3,
             "name": item.title, "item": base + urls[item.id]},
        ],
    }, ensure_ascii=False)


def _article_ld(item, urls: dict) -> str:
    """기사 구조화 데이터. 검색엔진과 AI 가 읽는다."""
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": (item.title or "").replace("[샘플] ", ""),
        "datePublished": item.published_at,
        "dateModified": item.published_at,
        "inLanguage": "ko",
        "url": f"{SITE_URL}{BASE_PATH}{urls.get(item.id, '/')}",
        "publisher": {"@type": "NewsMediaOrganization", "name": SITE_NAME},
        "author": {"@type": "Organization", "name": item.source_name or SITE_NAME},
    }
    if item.summary:
        data["description"] = item.summary
    if item.photo:
        data["image"] = f"{SITE_URL}{BASE_PATH}{item.photo}"
    return json.dumps(data, ensure_ascii=False)


def render_site(items: list[Item], out_dir: str, today: str) -> list[str]:
    global _OUT_DIR, ANALYTICS
    ANALYTICS = load_analytics()
    _OUT_DIR = out_dir
    # 승인된 사진만 붙는다. 매니페스트가 없으면 조용히 사진 없이 간다.
    # 도시별 묶음. 푸터 링크가 모든 페이지에 들어가므로 common 보다 먼저 만든다.
    by_city = group_by_city(items)

    # 서명. 사람 이름을 지어내지 않고 부서로 나눈다.
    for item in items:
        item.source_name = byline_for(item)

    manifest = load_manifest()
    if manifest:
        # 지역면 단위로 배정한다. 한 화면에 같은 사진이 두 번 걸리지 않게.
        by_region: dict[str, list] = {}
        for item in items:
            if not item.photo and item.grade != "A":
                by_region.setdefault(item.region, []).append(item)
        # 사용 이력을 이어받는다. 한 번 쓴 사진은 다시 배정되지 않는다.
        used = load_used()
        for region, group in by_region.items():
            mapping = assign_photos(manifest, region, [i.id for i in group], used)
            for item in group:
                item.photo = mapping.get(item.id) or None
        save_used(used)
    env = _env()
    written: list[str] = []
    urls = {i.id: article_url(i) for i in items}
    by_id = {i.id: i for i in items}
    grouped = group_by_region(items)

    common = {
        "site_name": SITE_NAME, "site_tagline": SITE_TAGLINE,
        "site_url": SITE_URL, "region_names": REGION_NAMES,
        "today": today, "article_urls": urls,
        # 푸터 도시 링크. 기사가 쌓인 도시만 들어온다.
        "city_links": [(slug, CITY_NAMES[slug]) for slug in by_city],
        "topics": TOPICS, "topic_names": TOPIC_NAMES,
        "contact_email": CONTACT_EMAIL, "desk_duties": DESK_DUTIES,
        "analytics": ANALYTICS,
        "canonical": SITE_URL + BASE_PATH + "/",
        "site_base": SITE_URL + BASE_PATH,
        "site_ld": json.dumps({
            "@context": "https://schema.org",
            "@type": "NewsMediaOrganization",
            "name": SITE_NAME,
            "url": SITE_URL + BASE_PATH + "/",
            "logo": SITE_URL + BASE_PATH + "/og-default.jpg",
            "description": SITE_TAGLINE,
            # 자동 생성 기사가 있다는 사실을 기계도 읽을 수 있게 밝힌다.
            "publishingPrinciples": SITE_URL + BASE_PATH + "/about/",
            "email": CONTACT_EMAIL,
        }, ensure_ascii=False),
    }

    # 홈 — 국내 여행 전문지 지면 구성을 따른다.
    # 톱기사 / 오늘의 데이터 / 최신 헤드라인 띠 / 주요뉴스 / 지역면 블록
    top_by_region = {
        key: [i for i in group if i.grade != "A"][:TOP_PER_REGION]
        for key, group in grouped.items()
    }
    by_topic = group_by_topic(items)
    articles = front_order([i for i in items if i.grade != "A"])
    lead = articles[0] if articles else None
    sub_leads = articles[1:5]
    main_news = articles[5:17]

    # "많이 본 뉴스" 자리에는 조회수를 쓰지 않는다 — 우리는 그 숫자가 없고,
    # 없는 숫자로 순위를 만들면 그건 지어낸 것이다. 대신 우리가 실제로 가진
    # 사실 데이터(환율·날씨)를 놓는다.
    data_panel = []
    for key, name in REGION_NAMES.items():
        # 지면은 14일치를 담으므로 A등급(환율·날씨)도 날짜별로 쌓인다.
        # 그대로 늘어놓으면 한 줄에 "1 USD 1,361원 … 1 USD 1,377원" 처럼
        # 이틀치 환율이 나란히 걸린다. 가장 최근 날짜 것만 쓴다.
        rows = [i for i in grouped.get(key, []) if i.grade == "A"]
        if rows:
            latest = max(i.published_at[:10] for i in rows)
            rows = [i for i in rows if i.published_at[:10] == latest]
        facts = []
        for row in rows:
            fact = compact_fact(row.summary)
            if fact and fact not in facts:
                facts.append(fact)
        if facts:
            data_panel.append({"region": key, "name": name, "facts": facts})

    _write(
        os.path.join(out_dir, "index.html"),
        env.get_template("index.html").render(
            counts={k: len(v) for k, v in grouped.items()},
            top_by_region=top_by_region, lead=lead, sub_leads=sub_leads,
            main_news=main_news, data_panel=data_panel, by_topic=by_topic,
            lead_topic=topic_of(lead) if lead else '',
            headlines=articles[2:14], **common),
        written,
    )

    # 지역 페이지 — 소식이 없는 지역도 만든다. 링크가 깨지면 안 된다.
    for key, name in REGION_NAMES.items():
        panel, articles = split_panel(grouped.get(key, []))
        _write(
            os.path.join(out_dir, key, "index.html"),
            env.get_template("region.html").render(
                region_key=key, region_name=name, panel=panel,
                articles=articles, product_link=PRODUCT_LINKS[key],
                desk=REGION_DESKS.get(key, ""), **common),
            written,
        )

    # 항공 모음 — 지역을 가로지른다. 예약 결정에 직접 쓰는 정보라 따로 모은다.
    # 부문 페이지. 지역면만으로 나누면 목적지 디렉터리로 보인다 —
    # 국내 여행 전문지는 전부 편집 축으로 나눈다.
    for topic_id, topic_name, topic_desc in TOPICS:
        _write(
            os.path.join(out_dir, topic_id, "index.html"),
            env.get_template("section.html").render(
                section_title=topic_name, section_desc=topic_desc,
                items=by_topic[topic_id], **common),
            written,
        )

    # 도시 페이지 — /city/tokyo/ 같은 주소.
    # 지역면(일본)만으로는 "오사카 항공권" 검색을 받지 못한다. 사람들은
    # 나라가 아니라 도시로 검색한다. 기사가 MIN_ARTICLES 미만인 도시는
    # cities.group_by_city 가 아예 돌려주지 않는다 — 얇은 페이지를 안 만든다.
    for slug, city_items in by_city.items():
        name = CITY_NAMES[slug]
        region = CITY_REGION[slug]
        _write(
            os.path.join(out_dir, "city", slug, "index.html"),
            env.get_template("section.html").render(
                section_title=f"{name} 여행뉴스",
                section_desc=(
                    f"{name} 항공 노선·호텔·현지 소식을 모았습니다. "
                    f"{REGION_NAMES.get(region, region)} 지역면에서 "
                    f"{name} 관련 기사만 추렸습니다."),
                items=city_items, **common),
            written,
        )

    # 매체 소개 — 우리 봇의 User-Agent 가 이 주소를 가리키므로 반드시 존재해야 한다.
    _write(
        os.path.join(out_dir, "about", "index.html"),
        env.get_template("about.html").render(**common),
        written,
    )

    # 국내 여행 전문지 8곳을 전수 조사한 결과, 아래 넷은 8곳 중 7~8곳이
    # 갖춘 사실상의 규범이었다. 매체로 보이려면 있어야 한다.
    for slug, template in (("contact", "contact.html"),
                           ("privacy", "privacy.html"),
                           ("youth", "youth.html"),
                           ("search", "search.html")):
        _write(
            os.path.join(out_dir, slug, "index.html"),
            env.get_template(template).render(**common),
            written,
        )

    # 검색은 8/8 이 갖추고 있다. 정적 사이트라 서버가 없으므로 색인을 내려
    # 브라우저에서 찾는다. 색인에는 제목·지역·부문만 넣는다 — 본문을 넣으면
    # 남의 기사 요약을 통째로 배포하는 셈이 된다.
    index = [{"t": i.title, "u": urls[i.id], "k": i.region,
              "r": REGION_NAMES.get(i.region, i.region),
              "g": i.grade, "d": i.published_at[:10]}
             for i in items if i.grade != "A"]
    _write(os.path.join(out_dir, "search.json"),
           json.dumps(index, ensure_ascii=False, separators=(",", ":")), written)

    # 기사 페이지 — A등급은 패널에만 나오므로 개별 페이지를 만들지 않는다.
    #
    # 우리 기사끼리 잇는 링크를 함께 낸다. 지금까지 기사 페이지에서 다른
    # 기사로 가는 길이 네비와 푸터뿐이었다. 읽던 사람은 여기서 나가고,
    # 크롤러는 개별 기사를 사이트맵으로만 만난다. 둘 다 손해다.
    for item in items:
        if item.grade == "A":
            continue
        related = [by_id[r] for r in item.related if r in by_id]

        # 같은 도시 → 없으면 같은 지역. 도시가 더 가까운 맥락이다.
        mine = cities_of(item)
        pool = [i for i in items
                if i.id != item.id and i.grade != "A"
                and i.id not in {r.id for r in related}]
        more = [i for i in pool if mine and set(cities_of(i)) & set(mine)]
        more_label = (CITY_NAMES[mine[0]] if mine and mine[0] in CITY_NAMES
                      else REGION_NAMES.get(item.region, item.region))
        more_link = (f"/city/{mine[0]}/" if mine and mine[0] in by_city
                     else f"/{item.region}/")
        if len(more) < 4:
            seen_ids = {i.id for i in more}
            more += [i for i in pool
                     if i.region == item.region and i.id not in seen_ids]
            more_label = REGION_NAMES.get(item.region, item.region)
            more_link = f"/{item.region}/"
        more = more[:5]

        # 그 지역의 오늘 값. 우리가 만든 사실이라 기사에 붙여도 남의 것이 아니고,
        # 여행 기사를 읽는 사람에게 실제로 쓸모가 있다.
        facts = next((row["facts"] for row in data_panel
                      if row["region"] == item.region), [])

        _write(
            os.path.join(out_dir, urls[item.id].strip("/"), "index.html"),
            env.get_template("article.html").render(
                item=item, related=related, more=more,
                more_label=more_label, more_link=more_link, facts=facts,
                article_ld=_article_ld(item, urls),
                crumb_ld=_crumb_ld(item, urls),
                region_name=REGION_NAMES.get(item.region, item.region),
                product_link=PRODUCT_LINKS.get(item.region, SITE_URL),
                **common),
            written,
        )

    _write(
        os.path.join(out_dir, "404.html"),
        env.get_template("404.html").render(**common),
        written,
    )

    # 파비콘·기본 OG 이미지
    for name in ("favicon.svg", "og-default.jpg"):
        src = os.path.join("static", name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(out_dir, name))

    # 편집실(CMS). 색인은 막는다 — 검색 결과에 나올 이유가 없다.
    admin_src = os.path.join("static", "admin")
    if os.path.isdir(admin_src):
        admin_dst = os.path.join(out_dir, "admin")
        shutil.rmtree(admin_dst, ignore_errors=True)
        shutil.copytree(admin_src, admin_dst)
        written.append(admin_dst)

    copied = copy_into(out_dir)
    if copied:
        print(f"  사진 {copied}장 복사 → {out_dir}/img/")

    return written
