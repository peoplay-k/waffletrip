import xml.etree.ElementTree as ET
from pathlib import Path

from src.models import Item
from src.render.feeds import (render_rss, render_sitemap, render_robots,
                              render_cname, render_llms_txt,
                              RSS_MAX_ITEMS, LLMS_MAX_ITEMS)
from src.render.site import SITE_URL, safe_url

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


def test_control_characters_do_not_break_the_feed(tmp_path):
    """XML 1.0 이 못 받는 제어문자 하나가 피드 전체를 재파싱 불가로 만든다."""
    path = render_rss([make("1", "Bad\x00Title\x07Here")], str(tmp_path), NOW)
    root = ET.parse(path).getroot()
    assert root.find("./channel/item/title").text == "BadTitleHere"


def test_non_string_published_at_does_not_kill_the_feed(tmp_path):
    """None 이면 fromisoformat 이 TypeError 를 던져 피드 전체가 죽었다."""
    item = make("1", "괌 소식")
    item.published_at = None
    path = render_rss([item], str(tmp_path), NOW)
    assert ET.parse(path).getroot().tag == "rss"


def test_safe_url_only_allows_http_schemes():
    """링크 스킴 화이트리스트. 이게 뚫리면 javascript: 링크가 클릭된다."""
    assert safe_url("https://example.com/a") == "https://example.com/a"
    assert safe_url("http://x.kr") == "http://x.kr"
    assert safe_url("  https://ok.com  ") == "https://ok.com"
    assert safe_url("javascript:alert(1)") == ""
    assert safe_url("JavaScript:alert(1)") == ""
    assert safe_url("data:text/html,<script>") == ""
    assert safe_url("") == ""


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
    """부문이 flight/data 에서 일곱 개로 바뀌었다. 사이트맵도 따라가야 한다."""
    path = render_sitemap([], str(tmp_path), TODAY)
    text = Path(path).read_text(encoding="utf-8")
    for page in ("data", "about", "biz", "issue", "feature"):
        assert f"/{page}/</loc>" in text, page
    assert "/flight/</loc>" not in text


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


# ── 사이트맵이 실제 페이지와 어긋나지 않는지 ───────────────────────
def test_sitemap_lists_every_topic_page(tmp_path):
    """부문을 손으로 적어두면 바뀔 때마다 어긋난다.

    실제로 사라진 /flight/ 를 계속 가리키고 새 부문 일곱 개가 빠져 있었다.
    """
    from src.render.feeds import render_sitemap
    from src.topics import TOPICS
    render_sitemap([], str(tmp_path), "2026-09-02")
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    for tid, _, _ in TOPICS:
        assert f"/{tid}/</loc>" in xml, tid


def test_sitemap_lists_policy_pages(tmp_path):
    from src.render.feeds import render_sitemap
    render_sitemap([], str(tmp_path), "2026-09-02")
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    for page in ("about", "contact", "privacy", "youth", "search"):
        assert f"/{page}/</loc>" in xml, page


def test_sitemap_urls_carry_the_base_path(tmp_path, monkeypatch):
    """하위 경로 배포에서 사이트맵이 없는 주소를 가리키면 색인이 안 된다."""
    import src.render.feeds as feeds
    monkeypatch.setattr(feeds, "BASE_PATH", "/waffletrip")
    feeds.render_sitemap([], str(tmp_path), "2026-09-02")
    xml = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    for loc in [l for l in xml.splitlines() if "<loc>" in l]:
        assert "/waffletrip/" in loc, loc


# ── llms.txt (AI 검색이 읽는 안내문) ────────────────────────────────
def test_llms_txt_opens_with_the_site_name_and_summary(tmp_path):
    text = Path(render_llms_txt([], str(tmp_path))).read_text(encoding="utf-8")
    assert text.startswith("# 와플트립")
    assert "> 매일 아침 여행 뉴스" in text


def test_llms_txt_lists_every_region_and_topic(tmp_path):
    """지역·부문을 손으로 적으면 바뀔 때마다 어긋난다 — 사이트맵과 같은 사고."""
    from src.render.site import REGION_NAMES
    from src.topics import TOPICS
    text = Path(render_llms_txt([], str(tmp_path))).read_text(encoding="utf-8")
    for key, name in REGION_NAMES.items():
        assert f"({SITE_URL}/{key}/)" in text, key
        assert name in text, name
    for tid, name, _ in TOPICS:
        assert f"({SITE_URL}/{tid}/)" in text, tid


def test_llms_txt_excludes_grade_a_data(tmp_path):
    items = [make("abcdef1234", "괌 소식"), make("2", "오늘의 환율", grade="A")]
    text = Path(render_llms_txt(items, str(tmp_path))).read_text(encoding="utf-8")
    assert "괌 소식" in text
    assert "오늘의 환율" not in text


def test_llms_txt_caps_the_article_count(tmp_path):
    """전부 나열하면 안내가 목록에 묻힌다. 전체 주소는 sitemap 이 담당한다."""
    items = [make(f"{i:010d}", f"소식 {i}") for i in range(LLMS_MAX_ITEMS + 10)]
    text = Path(render_llms_txt(items, str(tmp_path))).read_text(encoding="utf-8")
    assert text.count("- [소식 ") == LLMS_MAX_ITEMS


def test_llms_txt_urls_carry_the_base_path(tmp_path, monkeypatch):
    import src.render.feeds as feeds
    monkeypatch.setattr(feeds, "BASE_PATH", "/waffletrip")
    feeds.render_llms_txt([], str(tmp_path))
    text = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    for line in [l for l in text.splitlines() if l.startswith("- [")]:
        assert "/waffletrip/" in line, line
