"""급상승 키워드 이음매. 실패해도 신문은 나가야 한다."""
from __future__ import annotations

import json

from src.trending import parse_feed, write

FEED = """<?xml version="1.0"?>
<rss><channel>
<title>Daily Search Trends</title>
<item><title>괌 태풍</title>
  <ht:news_item><ht:news_item_title>기사 제목은 키워드가 아니다</ht:news_item_title></ht:news_item>
</item>
<item><title><![CDATA[환율]]></title></item>
<item><title>가</title></item>
<item><title>괌 태풍</title></item>
</channel></rss>"""


def test_channel_title_is_not_a_keyword():
    """'Daily Search Trends' 가 키워드로 새면 모든 제목 매칭이 무의미해진다."""
    assert "Daily Search Trends" not in parse_feed(FEED)


def test_news_item_title_is_not_a_keyword():
    assert "기사 제목은 키워드가 아니다" not in parse_feed(FEED)


def test_cdata_is_unwrapped():
    assert "환율" in parse_feed(FEED)


def test_single_character_keyword_is_dropped():
    """한 글자는 아무 제목에나 걸려 후보 선정을 망친다."""
    assert "가" not in parse_feed(FEED)


def test_duplicates_collapse():
    assert parse_feed(FEED).count("괌 태풍") == 1


def test_empty_or_broken_feed_returns_empty():
    assert parse_feed("") == []
    assert parse_feed("not xml at all") == []
    assert parse_feed(None) == []


def test_write_produces_shape_load_trending_expects(tmp_path):
    """src.edit.load_trending 이 읽는 모양과 어긋나면 조용히 빈 리스트가 된다."""
    from src.edit import load_trending
    write(str(tmp_path), ["괌 태풍", "환율"], "2026-09-02")
    assert load_trending(str(tmp_path)) == ["괌 태풍", "환율"]


def test_written_file_is_readable_json(tmp_path):
    path = write(str(tmp_path), ["가나다"], "2026-09-02")
    data = json.load(open(path, encoding="utf-8"))
    assert data["keywords"] == ["가나다"]
    assert data["source"] == "google_trends_kr"
