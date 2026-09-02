from pathlib import Path

from src.models import Item
from src.render.site import (slugify, article_url, group_by_region,
                             split_panel, render_site, safe_url,
                             REGION_NAMES)

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
    """확인된 링크가 있는 지역(괌)으로 한정한다. 다른 지역은 빈 값이다."""
    from src.render.site import PRODUCT_LINKS
    render_site([make("1", "괌 소식", region="guam")], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert PRODUCT_LINKS["guam"] in html


def test_regions_without_a_product_site_show_no_button(tmp_path):
    """다른 지역 페이지에 괌 여행사를 붙이면 브랜드가 섞인다."""
    item = make("1", "제주 소식", region="jeju")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "jeju" / "index.html").read_text(encoding="utf-8")
    assert "guamplay.com" not in html
    assert "여행 상품 보러가기" not in html


def test_scraped_titles_are_html_escaped(tmp_path):
    """제목은 남의 사이트에서 긁어온 텍스트다. 그대로 렌더하면 안 된다."""
    item = make("1", "<script>alert(1)</script>")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_javascript_scheme_links_are_dropped(tmp_path):
    """수집한 링크는 남의 사이트가 준 값이다. autoescape 는 스킴을 막지 않는다."""
    item = make("abcdef1234567890", "괌 소식")
    item.source_url = "javascript:alert(1)"
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "abcdef12-괌-소식" /
            "index.html").read_text(encoding="utf-8")
    assert "javascript:" not in html
    assert "Guam Post" in html   # 출처 이름은 링크가 없어도 남는다


def test_outbound_links_are_marked_nofollow(tmp_path):
    """원문 링크는 남의 사이트다. 검색엔진에 우리 신뢰를 넘기지 않는다."""
    item = make("abcdef1234567890", "괌 소식")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "abcdef12-괌-소식" /
            "index.html").read_text(encoding="utf-8")
    assert 'rel="nofollow noopener"' in html


def test_path_traversal_in_id_cannot_escape_the_output_dir(tmp_path):
    """id·region 은 슬러그와 달리 정제되지 않은 채 경로에 들어간다.

    지금은 id 가 sha1 이라 도달할 수 없지만, 방어가 없는 것과 도달 못 하는 것은 다르다.
    """
    item = make("../../../../evil", "제목")
    item.region = "../../etc"
    out = tmp_path / "site"
    render_site([item], str(out), TODAY)
    written = [q for q in tmp_path.rglob('*') if q.is_file()]
    assert all(str(q).startswith(str(out)) for q in written), written


def test_render_site_returns_every_path_it_wrote(tmp_path):
    paths = render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    assert all(Path(p).exists() for p in paths)
    assert any(p.endswith("index.html") for p in paths)


def test_render_site_with_no_items_still_writes_index(tmp_path):
    render_site([], str(tmp_path), TODAY)
    assert (tmp_path / "index.html").exists()


def test_biz_page_collects_airline_news(tmp_path):
    """항공 노선 소식은 여행BIZ 로 간다."""
    item = make("1", "진에어 괌 노선 신규 취항", section="flight")
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "biz" / "index.html").read_text(encoding="utf-8")
    assert "진에어 괌 노선 신규 취항" in html


def test_biz_page_excludes_unrelated_news(tmp_path):
    render_site([make("1", "바다거북 산란지 발견")], str(tmp_path), TODAY)
    html = (tmp_path / "biz" / "index.html").read_text(encoding="utf-8")
    assert "바다거북 산란지 발견" not in html


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


def test_nav_links_to_every_topic(tmp_path):
    """네비의 부문 링크가 실제 페이지와 어긋나면 404 로 간다."""
    from src.topics import TOPICS
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    for tid, _, _ in TOPICS:
        assert f'href="/{tid}/"' in html, tid
        assert (tmp_path / tid / "index.html").exists(), tid


def test_region_names_are_not_in_the_top_nav(tmp_path):
    """지역명을 상단에 늘어놓으면 신문이 아니라 목적지 디렉터리로 보인다."""
    import re
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    nav = re.search(r'<nav class="gnb".*?</nav>', html, re.S)
    assert nav, "네비를 찾지 못했다"
    for name in REGION_NAMES.values():
        assert name not in nav.group(0), name


def test_every_region_key_is_present_in_both_maps():
    from src.render.site import PRODUCT_LINKS
    from src.models import REGIONS
    assert set(REGION_NAMES) == set(REGIONS)
    assert set(PRODUCT_LINKS) == set(REGIONS)


# ── 자사 상품 링크 ────────────────────────────────────────────────
def test_product_links_cover_every_region():
    """지역이 늘었는데 키를 빠뜨리면 KeyError 로 빌드가 죽는다."""
    from src.models import REGIONS
    from src.render.site import PRODUCT_LINKS
    assert set(PRODUCT_LINKS) == set(REGIONS)


def test_product_links_point_at_their_own_region():
    """하와이 페이지에 괌 여행사를 붙이는 브랜드 격리 위반을 막는다.

    실제로 예전에 전부 guamplay.com 으로 채워져 있었다.
    """
    from src.render.site import PRODUCT_LINKS
    expected_host = {"guam": "guamplay.com", "saipan": "saipanplay.com",
                     "kota": "kotaplay.com", "laos": "laosplay.com"}
    for region, host in expected_host.items():
        assert PRODUCT_LINKS[region].endswith(host), region


def test_regions_without_a_verified_site_stay_empty():
    """소유가 확인되지 않은 도메인은 비워 둔다.

    jejuplay.com 은 제주 유흥 정보 사이트이고, hawaiiplay.com 은 도메인 판매
    페이지다. 이름이 비슷하다는 이유로 붙이면 사고가 난다.
    """
    from src.render.site import PRODUCT_LINKS
    assert PRODUCT_LINKS["jeju"] == ""
    assert PRODUCT_LINKS["hawaii"] == ""
    assert PRODUCT_LINKS["vietnam"] == ""


def test_no_product_link_uses_an_unowned_domain():
    from src.render.site import PRODUCT_LINKS
    forbidden = ("jejuplay.com", "hawaiiplay.com", "vietnamplay.com")
    for region, url in PRODUCT_LINKS.items():
        assert not any(bad in url for bad in forbidden), region


# ── 데이터 패널 압축 ──────────────────────────────────────────────
def test_compact_fact_shortens_weather():
    from src.render.site import compact_fact
    got = compact_fact("2026-09-02 하갓냐 뇌우, 최고 31°C · 최저 25°C · 강수확률 100%")
    assert got == "31° / 25°  뇌우  ·  비 100%"


def test_compact_fact_handles_weather_without_rain():
    from src.render.site import compact_fact
    got = compact_fact("2026-09-02 하갓냐 맑음, 최고 31°C · 최저 25°C")
    assert got == "31° / 25°  맑음"


def test_compact_fact_shortens_exchange_rate():
    from src.render.site import compact_fact
    assert compact_fact("2026-09-02 기준 1 USD = 약 1,377원") == "1 USD  1,377원"


def test_compact_fact_keeps_low_denomination_unit():
    """100 단위로 묶은 저액면 통화가 1 단위로 잘못 보이면 안 된다."""
    from src.render.site import compact_fact
    assert compact_fact("2026-09-02 기준 100 VND = 약 5.3원") == "100 VND  5.3원"


def test_compact_fact_falls_back_to_original():
    """줄이려다 정보를 잃는 것보다 길게 나오는 편이 낫다."""
    from src.render.site import compact_fact
    assert compact_fact("모르는 형식입니다") == "모르는 형식입니다"
    assert compact_fact("") == ""
    assert compact_fact(None) == ""


def test_compact_fact_handles_negative_temperature():
    from src.render.site import compact_fact
    assert compact_fact("2026-01-02 제주 눈, 최고 -1°C · 최저 -7°C") == "-1° / -7°  눈"


# ── 하위 경로 배포 ────────────────────────────────────────────────
def test_with_base_prefixes_absolute_links():
    """GitHub Pages 는 커스텀 도메인이 없으면 /<repo>/ 하위에서 서비스한다.

    "/img/..." 를 그대로 두면 브라우저가 도메인 루트에서 찾아 전부 404 가
    난다. 실제로 사진 7장과 모든 기사 링크가 깨진 채 배포됐다.
    """
    from src.render.site import with_base
    html = '<a href="/guam/">괌</a><img src="/img/guam/a.webp">'
    got = with_base(html, "/waffletrip")
    assert 'href="/waffletrip/guam/"' in got
    assert 'src="/waffletrip/img/guam/a.webp"' in got


def test_with_base_leaves_external_and_relative_links_alone():
    from src.render.site import with_base
    html = ('<a href="https://guamplay.com">상품</a>'
            '<a href="//cdn.example.com/x">프로토콜상대</a>'
            '<a href="rss.xml">상대</a>')
    got = with_base(html, "/waffletrip")
    assert got == html


def test_with_base_is_a_noop_when_empty():
    """커스텀 도메인이 붙으면 접두사가 없어야 한다."""
    from src.render.site import with_base
    html = '<a href="/guam/">괌</a>'
    assert with_base(html, "") == html


def test_rendered_pages_get_the_prefix(tmp_path, monkeypatch):
    import src.render.site as site
    monkeypatch.setattr(site, "BASE_PATH", "/waffletrip")
    site.render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'href="/waffletrip/' in html
    assert 'href="//' not in html.replace('href="//waffletrip', '')


def test_search_page_uses_a_relative_index_path(tmp_path):
    """검색 색인을 절대경로로 부르면 하위 경로 배포에서 404 가 난다.

    with_base 는 href/src 속성만 고치고 JS 문자열은 손대지 않는다.
    실제로 배포된 사이트에서 검색이 통째로 죽어 있었다.
    """
    render_site([], str(tmp_path), TODAY)
    html = (tmp_path / "search" / "index.html").read_text(encoding="utf-8")
    assert "'../search.json'" in html
    assert "'/search.json'" not in html


def test_our_own_article_has_no_source_link(tmp_path):
    """우리가 쓴 기사에 '원문 보기: 와플트립 괌 데스크' 가 붙으면 안 된다."""
    item = make("1", "괌 데이터 정리", grade="C")
    item.source_url = ""
    render_site([item], str(tmp_path), TODAY)
    html = (tmp_path / "guam" / "1-괌-데이터-정리" / "index.html").read_text(
        encoding="utf-8") if (tmp_path / "guam").exists() else ""
    import glob as _g
    for p in _g.glob(str(tmp_path / "guam" / "*" / "index.html")):
        html = open(p, encoding="utf-8").read()
        break
    assert "원문 보기" not in html


def test_curated_article_keeps_its_source(tmp_path):
    """남의 기사는 출처를 반드시 밝힌다."""
    item = make("1", "제주 소식", grade="B")
    item.source_name = "제주의소리"
    item.source_url = "https://example.com/a"
    render_site([item], str(tmp_path), TODAY)
    import glob as _g
    html = ""
    for p in _g.glob(str(tmp_path / "guam" / "*" / "index.html")):
        html = open(p, encoding="utf-8").read()
    assert "제주의소리" in html
