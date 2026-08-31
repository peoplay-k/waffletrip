from pathlib import Path

from src.models import Item
from src.render.site import (slugify, article_url, group_by_region,
                             split_panel, render_site, REGION_NAMES)

NOW = "2026-08-31T05:00:00+09:00"
TODAY = "2026-08-31"


def make(item_id, title, region="guam", grade="B", section="news"):
    return Item(id=item_id, grade=grade, region=region, section=section,
                title=title, summary="요약 문장.", source_name="Guam Post",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h")


def test_slugify_keeps_hangul():
    assert slugify("괌 신규 취항") == "괌-신규-취항"


def test_slugify_lowercases_and_strips_punctuation():
    assert slugify("United ADDS a Flight!") == "united-adds-a-flight"


def test_slugify_collapses_repeated_separators():
    assert slugify("괌   ---  취항") == "괌-취항"


def test_slugify_truncates_long_titles():
    assert len(slugify("가" * 100)) <= 40


def test_slugify_on_empty_string_yields_placeholder():
    assert slugify("") == "article"


def test_article_url_has_region_and_id_prefix():
    url = article_url(make("abcdef1234567890", "괌 신규 취항"))
    assert url == "/guam/abcdef12-괌-신규-취항/"


def test_group_by_region_buckets_items():
    grouped = group_by_region([make("1", "a", "guam"), make("2", "b", "jeju")])
    assert set(grouped) == {"guam", "jeju"}


def test_group_by_region_covers_only_regions_present():
    grouped = group_by_region([make("1", "a", "guam")])
    assert "hawaii" not in grouped


def test_split_panel_separates_grade_a():
    data = make("1", "오늘의 환율", grade="A", section="data")
    news = make("2", "괌 소식")
    panel, articles = split_panel([data, news])
    assert [i.id for i in panel] == ["1"]
    assert [i.id for i in articles] == ["2"]


def test_render_site_writes_index(tmp_path):
    render_site([make("1", "괌 신규 취항")], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "와플트립" in html
    assert "매일 아침 여행 뉴스" in html
    assert "괌 신규 취항" in html


def test_render_site_writes_region_page(tmp_path):
    render_site([make("1", "괌 신규 취항")], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert REGION_NAMES["guam"] in html
    assert "괌 신규 취항" in html


def test_render_site_writes_article_page(tmp_path):
    item = make("abcdef1234567890", "괌 신규 취항")
    render_site([item], str(tmp_path), TODAY)
    path = tmp_path / "guam" / "abcdef12-괌-신규-취항" / "index.html"
    assert path.exists()
    assert "Guam Post" in path.read_text(encoding="utf-8")


def test_article_page_links_to_the_original_source(tmp_path):
    item = make("abcdef1234567890", "괌 신규 취항")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "abcdef12-괌-신규-취항" /
            "index.html").read_text(encoding="utf-8")
    assert "https://example.com/abcdef1234567890" in html


def test_region_page_shows_data_panel(tmp_path):
    items = [make("1", "오늘의 환율 — 1 USD", grade="A", section="data"),
             make("2", "괌 신규 취항")]
    render_site(items, str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert "오늘의 환율" in html


def test_region_page_links_to_the_product_site(tmp_path):
    from src.render.site import PRODUCT_LINKS
    render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert PRODUCT_LINKS["guam"] in html


def test_render_site_returns_every_path_it_wrote(tmp_path):
    paths = render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    assert all(Path(p).exists() for p in paths)
    assert any(p.endswith("index.html") for p in paths)


def test_render_site_with_no_items_still_writes_index(tmp_path):
    render_site([], str(tmp_path), TODAY)
    assert (tmp_path / "index.html").exists()


def test_render_site_writes_flight_page(tmp_path):
    item = make("1", "진에어 괌 노선 신규 취항", section="flight")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "flight" / "index.html").read_text(encoding="utf-8")
    assert "진에어 괌 노선 신규 취항" in html


def test_flight_page_excludes_ordinary_news(tmp_path):
    render_site([make("1", "투몬 해변 청소")], str(tmp_path), TODAY)
    html = (tmp_path / "flight" / "index.html").read_text(encoding="utf-8")
    assert "투몬 해변 청소" not in html


def test_render_site_writes_data_page(tmp_path):
    item = make("1", "오늘의 환율 — 1 USD", grade="A", section="data")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "data" / "index.html").read_text(encoding="utf-8")
    assert "오늘의 환율" in html


def test_render_site_writes_about_page(tmp_path):
    """봇의 User-Agent 가 이 주소를 가리킨다. 404 면 거짓 신원이 된다."""
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert "저작권" in html
    assert "robots.txt" in html


def test_nav_links_to_flight_data_and_about(tmp_path):
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    for href in ('href="/flight/"', 'href="/data/"', 'href="/about/"'):
        assert href in html


def test_every_region_key_has_a_korean_name_and_product_link():
    from src.render.site import PRODUCT_LINKS
    from src.models import REGIONS
    assert set(REGION_NAMES) == set(REGIONS)
    assert set(PRODUCT_LINKS) == set(REGIONS)
