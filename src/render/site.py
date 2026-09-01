"""정규화된 항목을 정적 HTML 로 만든다.

이 모듈은 수집 과정을 모른다. 항목 리스트와 출력 경로만 받는다.
디자인 컨셉은 와플 격자 — 7개 지역이 격자 칸에 놓인다.
"""
from __future__ import annotations

import os
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from src.photos import copy_into, load_manifest, pick as pick_photo
from src.render.md import render as md_render

from src.models import Item

SITE_NAME = "와플트립"
SITE_TAGLINE = "매일 아침 여행 뉴스"
SITE_URL = "https://waffletrip.com"

REGION_NAMES = {
    "guam": "괌", "saipan": "사이판", "hawaii": "하와이",
    "vietnam": "베트남", "kota": "코타키나발루", "laos": "라오스",
    "jeju": "제주",
}

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
}

TOP_PER_REGION = 3
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
    articles = [i for i in items if i.grade != "A"]
    return panel, articles


def _write(path: str, html: str, written: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    written.append(path)


def render_site(items: list[Item], out_dir: str, today: str) -> list[str]:
    # 승인된 사진만 붙는다. 매니페스트가 없으면 조용히 사진 없이 간다.
    manifest = load_manifest()
    if manifest:
        for item in items:
            if not item.photo and item.grade != "A":
                item.photo = pick_photo(manifest, item.region, item.id) or None
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

    copied = copy_into(out_dir)
    if copied:
        print(f"  사진 {copied}장 복사 → {out_dir}/img/")

    return written
