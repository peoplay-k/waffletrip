"""RSS/Atom 피드를 Item 으로 바꾼다.

parse_feed 는 순수 함수다(네트워크를 모른다). fetch 만 네트워크를 안다.
덕분에 파싱 규칙 전체를 저장된 픽스처로 테스트할 수 있다.
"""
from __future__ import annotations

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
# 그리고 이 함수는 "정규식 조각 수"를 세지 "실제 문장 수"를 세지 않는다. 종결부호 뒤에
# 공백이 없으면 두 문장이 한 조각으로 붙어, n=2 를 요청해도 실제 문장 3개가 통과한다.
# 원문 전재를 막는 장치가 바로 그 지점에서 새므로 세 규칙 모두 필요하다.
#   (1) 종결부호 뒤 공백
#   (2) 한글에 붙은 종결부호 — 공백이 없어도 자른다
#   (3) 소문자/숫자에 붙은 종결부호 뒤에 대문자가 오면 자른다
# (3)의 앞이 소문자여야 하므로 "U.S." 처럼 대문자 뒤의 마침표는 걸리지 않는다.
_SENTENCE_END = re.compile(
    r"(?<=[.!?。？！])\s+"          # (1) 종결부호 뒤 공백
    r"|(?<=[가-힣][.!?。？！])"      # (2) 한글에 붙은 종결부호(공백 없어도)
    r"|(?<=[a-z0-9][.!?])(?=[A-Z])"  # (3) 소문자/숫자 뒤 종결부호 + 대문자
)


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
