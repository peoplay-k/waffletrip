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


def test_auto_source_uses_summary_when_title_has_no_place_name():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>신규 취항 소식</title><link>https://example.com/x</link>
    <description>제주 노선이 늘어난다.</description></item></channel></rss>"""
    assert parse_feed(AUTO_SOURCE, xml, NOW)[0].region == "jeju"


def test_static_region_source_is_not_retagged():
    """region 이 고정된 소스는 기사 내용과 무관하게 그 지역을 쓴다."""
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>Hawaii tourism note</title><link>https://example.com/h</link>
    <description>Body.</description></item></channel></rss>"""
    # SOURCE 는 region="guam" 고정이다
    assert parse_feed(SOURCE, xml, NOW)[0].region == "guam"
