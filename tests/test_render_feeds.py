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
