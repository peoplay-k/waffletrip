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

# llms.txt 는 AI 가 한 번에 읽는 안내문이다. 기사를 전부 나열하면 안내가
# 목록에 묻힌다. 전체 주소는 sitemap.xml 이 담당한다.
LLMS_MAX_ITEMS = 30


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
    from src.cities import group_by_city
    from src.topics import TOPICS

    base = SITE_URL + BASE_PATH
    urls = [base + "/"]
    urls += [f"{base}/{key}/" for key in REGION_NAMES]
    urls += [f"{base}/{tid}/" for tid, _, _ in TOPICS]
    # 도시 페이지도 같은 이유로 파생시킨다. 기사가 쌓여 새 도시 페이지가
    # 생기는 날 사이트맵이 저절로 따라와야 한다.
    urls += [f"{base}/city/{slug}/" for slug in group_by_city(items)]
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


def render_llms_txt(items: list[Item], out_dir: str) -> str:
    """AI 검색이 읽는 사이트 안내문.

    챗GPT·퍼플렉시티 같은 도구는 사이트를 통째로 훑는 대신 이 파일 하나로
    "여기가 무슨 매체이고 어디에 뭐가 있는지"를 판단한다. sitemap.xml 은
    주소만 있고 설명이 없어서 그 역할을 못 한다.

    항목을 손으로 적지 않고 REGION_NAMES 와 TOPICS 에서 끌어온다. sitemap 이
    사라진 부문을 계속 가리키던 것과 같은 사고를 되풀이하지 않기 위해서다.
    """
    from src.cities import group_by_city
    from src.topics import TOPICS

    base = SITE_URL + BASE_PATH
    regions = "·".join(REGION_NAMES.values())

    lines = [f"# {SITE_NAME}", "",
             f"> {SITE_TAGLINE}. {regions} 일곱 곳의 여행 뉴스를 매일 "
             f"05:00(KST)에 새로 낸다. 현지 매체와 관광청 발표를 원문 출처와 "
             f"함께 옮기고, 확인되지 않은 사실은 싣지 않는다.", ""]

    lines += ["## 지역면", ""]
    lines += [f"- [{name}]({base}/{key}/): {name} 여행 뉴스"
              for key, name in REGION_NAMES.items()]

    lines += ["", "## 부문", ""]
    lines += [f"- [{name}]({base}/{tid}/): {desc}" for tid, name, desc in TOPICS]

    lines += ["", "## 매체 정보", "",
              f"- [매체 소개]({base}/about/): 발행 주체와 편집 원칙",
              f"- [제보·문의]({base}/contact/)",
              f"- [전체 주소 목록]({base}/sitemap.xml)",
              f"- [RSS]({base}/rss.xml)", ""]

    # A등급(환율·날씨 같은 자동 생성 데이터)은 기사가 아니라 빼둔다.
    # sitemap 과 같은 기준이다.
    articles = [i for i in items if i.grade != "A"]
    if articles:
        lines += ["## 최근 기사", ""]
        lines += [f"- [{_xml_safe(i.title)}]({base}{article_url(i)})"
                  for i in articles[:LLMS_MAX_ITEMS]]
        lines.append("")

    return _write(os.path.join(out_dir, "llms.txt"), "\n".join(lines) + "\n")


def render_cname(out_dir: str, domain: str = "waffletrip.com") -> str:
    """GitHub Pages 커스텀 도메인 설정 파일.

    빌드마다 다시 만든다. public/ 을 통째로 갈아엎어도 도메인이 풀리지 않게
    하기 위해서다.
    """
    return _write(os.path.join(out_dir, "CNAME"), domain + "\n")
