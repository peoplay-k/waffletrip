"""RSS·sitemap·robots·CNAME 을 만든다.

RSS 는 문자열 조립 대신 ElementTree 로 만든다. 제목에 & 나 < 가 들어와도
깨지지 않게 하려면 이스케이프를 직접 하지 않는 편이 안전하다.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from email.utils import format_datetime
from datetime import datetime

from src.models import Item
from src.render.site import (BASE_PATH, REGION_NAMES, SITE_NAME, SITE_TAGLINE, SITE_URL,
                             article_url)

RSS_MAX_ITEMS = 50


# XML 1.0 이 허용하지 않는 제어문자. 남기면 ElementTree 가 그대로 직렬화해
# rss.xml 전체가 재파싱 불가능해진다 — 한 항목이 피드 전부를 죽인다.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _xml_safe(text: str) -> str:
    return _CONTROL.sub("", text or "")


def _rfc822(iso: str) -> str:
    """날짜를 RFC822 로. 못 읽으면 원문 그대로 둔다.

    TypeError 도 잡는 이유: published_at 이 None 이면 fromisoformat 이
    ValueError 가 아니라 TypeError 를 던져서 피드 전체가 죽는다.
    """
    try:
        return format_datetime(datetime.fromisoformat(iso))
    except (ValueError, TypeError):
        return str(iso)


def _write(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def render_rss(items: list[Item], out_dir: str, built_at: str) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = SITE_NAME
    ET.SubElement(channel, "link").text = SITE_URL + BASE_PATH + "/"
    ET.SubElement(channel, "description").text = SITE_TAGLINE
    ET.SubElement(channel, "language").text = "ko"
    ET.SubElement(channel, "lastBuildDate").text = _rfc822(built_at)

    # A등급(환율·날씨)은 매일 값만 바뀌는 데이터라 피드에 넣으면 소음이 된다.
    articles = [i for i in items if i.grade != "A"][:RSS_MAX_ITEMS]

    for item in articles:
        node = ET.SubElement(channel, "item")
        link = SITE_URL + BASE_PATH + article_url(item)
        ET.SubElement(node, "title").text = _xml_safe(item.title)
        ET.SubElement(node, "link").text = link
        ET.SubElement(node, "guid", {"isPermaLink": "true"}).text = link
        ET.SubElement(node, "description").text = _xml_safe(
            item.summary or item.title)
        ET.SubElement(node, "pubDate").text = _rfc822(item.published_at)
        ET.SubElement(node, "source").text = _xml_safe(item.source_name)

    xml = ET.tostring(rss, encoding="unicode")
    return _write(os.path.join(out_dir, "rss.xml"),
                  '<?xml version="1.0" encoding="UTF-8"?>\n' + xml)


def render_sitemap(items: list[Item], out_dir: str, today: str) -> str:
    # 부문은 src/topics.py 가 정본이다. 여기에 손으로 적어두면 부문이
    # 바뀔 때마다 어긋난다 — 실제로 사라진 /flight/ 를 계속 가리키고
    # 새 부문 일곱 개가 통째로 빠져 있었다.
    from src.topics import TOPICS

    base = SITE_URL + BASE_PATH
    urls = [base + "/"]
    urls += [f"{base}/{key}/" for key in REGION_NAMES]
    urls += [f"{base}/{tid}/" for tid, _, _ in TOPICS]
    urls += [f"{base}/{page}/" for page in
             ("about", "contact", "privacy", "youth", "search")]
    urls += [base + article_url(i) for i in items if i.grade != "A"]

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        lines.append(f"  <url><loc>{url}</loc><lastmod>{today}</lastmod></url>")
    lines.append("</urlset>")
    return _write(os.path.join(out_dir, "sitemap.xml"), "\n".join(lines) + "\n")


def render_robots(out_dir: str) -> str:
    # 편집실은 색인하지 않는다. 검색 결과에 나올 이유가 없다.
    text = (f"User-agent: *\nAllow: /\nDisallow: /admin/\n\n"
            f"Sitemap: {SITE_URL}{BASE_PATH}/sitemap.xml\n")
    return _write(os.path.join(out_dir, "robots.txt"), text)


def render_cname(out_dir: str, domain: str = "waffletrip.com") -> str:
    """GitHub Pages 커스텀 도메인 설정 파일.

    빌드마다 다시 만든다. public/ 을 통째로 갈아엎어도 도메인이 풀리지 않게
    하기 위해서다.
    """
    return _write(os.path.join(out_dir, "CNAME"), domain + "\n")
