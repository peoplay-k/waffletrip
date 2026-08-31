"""RSS·sitemap·robots·CNAME 을 만든다.

RSS 는 문자열 조립 대신 ElementTree 로 만든다. 제목에 & 나 < 가 들어와도
깨지지 않게 하려면 이스케이프를 직접 하지 않는 편이 안전하다.
"""
from __future__ import annotations

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
