"""정규화된 항목을 정적 HTML 로 만든다.

이 모듈은 수집 과정을 모른다. 항목 리스트와 출력 경로만 받는다.
디자인 컨셉은 와플 격자 — 7개 지역이 격자 칸에 놓인다.
"""
from __future__ import annotations

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
