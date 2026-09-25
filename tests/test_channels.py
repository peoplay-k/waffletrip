"""여행 / 연예 두 채널. 피플로드는 문화 전문 매체이고 그 아래 두 축이 있다.

지켜야 할 것: 연예 기사는 /ent/ 아래에서만 살고 지역면·도시면·환율 패널에 섞이지
않는다. 연예 부문 쪽은 기사가 없어도 존재한다(네비가 가리키는 주소가 404 면 안 된다).
빈 연예 블록을 홈에 그리지 않는다. 기존 jsonl(channel 없음)은 전부 여행으로 읽힌다.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from src.models import Item, item_from_dict, item_to_dict, title_hash
from src.render.site import article_url, render_site, tag_of
from src.topics import (ENT_TOPICS, TOPICS, ent_category_of, group_by_ent_topic,
                        group_by_topic, topic_of)

NOW = "2026-09-25T09:00:00+09:00"
TODAY = "2026-09-25"


def make(item_id, title, region="guam", grade="C", channel="travel", category="",
         summary="요약 문장.", photo=None):
    return Item(id=item_id, grade=grade, region=region, section="news",
                title=title, summary=summary, source_name="", source_url="",
                published_at=NOW, collected_at=NOW, status="published",
                title_hash=title_hash(title), body_md="본문이다.", photo=photo,
                channel=channel, category=category)


def ent(item_id, title, category="movie", **kw):
    return make(item_id, title, region="", channel="ent", category=category, **kw)


# ── 모델 ──────────────────────────────────────────────────────────
def test_old_jsonl_without_channel_reads_as_travel():
    d = item_to_dict(make("1", "괌 소식"))
    d.pop("channel"); d.pop("category")
    got = item_from_dict(d)
    assert got.channel == "travel" and got.category == "" and not got.is_ent


def test_ent_item_roundtrips():
    item = ent("c-1", "영화 개봉", "movie")
    assert item_from_dict(item_to_dict(item)) == item
    assert item.is_ent


# ── 부문 ──────────────────────────────────────────────────────────
def test_ent_category_from_editor_wins_over_keywords():
    assert topic_of(ent("1", "괌 촬영지 여행", "music")) == "music"


def test_ent_category_falls_back_to_keywords_then_star():
    assert ent_category_of(ent("1", "배우 ○○, 사이판 촬영지에서", "")) == "startrip"
    assert ent_category_of(ent("1", "○○ 신작 영화 개봉", "")) == "movie"
    assert ent_category_of(ent("1", "○○ 소속사 이적", "")) == "startrip"   # 인물은 스타의 여행으로 합쳤다
    assert ent_category_of(ent("1", "x", "drama")) == "movie"                 # 옛 id 는 새 부문으로
    assert ent_category_of(ent("1", "x", "star")) == "startrip"


def test_travel_rules_never_apply_to_ent_items():
    """'취항'이 제목에 있어도 연예 기사는 여행BIZ 로 가지 않는다."""
    assert topic_of(ent("1", "○○, 취항 기념 콘서트", "music")) == "music"


def test_group_by_topic_and_ent_topic_do_not_mix():
    items = [make("1", "대한항공 괌 증편", grade="B"), ent("2", "영화 개봉", "movie")]
    travel = group_by_topic(items)
    show = group_by_ent_topic(items)
    assert sum(len(v) for v in travel.values()) == 1
    assert [i.id for i in show["movie"]] == ["2"]
    assert set(show) == {tid for tid, _, _ in ENT_TOPICS}
    assert set(travel) == {tid for tid, _, _ in TOPICS}


def test_ent_topic_ids_do_not_collide_with_travel_topic_ids():
    assert not ({t for t, _, _ in ENT_TOPICS} & {t for t, _, _ in TOPICS})


# ── 주소·꼬리표 ────────────────────────────────────────────────────
def test_ent_article_url_lives_under_ent():
    assert article_url(ent("abcdef1234567890", "영화 개봉")) == "/ent/abcdef12-영화-개봉/"


def test_tag_of_points_ent_at_its_section_and_travel_at_its_region():
    assert tag_of(ent("1", "x", "drama")) == {"href": "/ent/movie/", "label": "연예 · 영화·드라마"}
    assert tag_of(make("1", "x", region="jeju")) == {"href": "/jeju/", "label": "제주"}


# ── 렌더 ──────────────────────────────────────────────────────────
def test_ent_pages_exist_even_with_zero_ent_articles(tmp_path):
    render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    assert (tmp_path / "ent" / "index.html").exists()
    assert (tmp_path / "travel" / "index.html").exists()
    for tid, _, _ in ENT_TOPICS:
        assert (tmp_path / "ent" / tid / "index.html").exists(), tid
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "연예 · 영화" not in home              # 빈 블록은 그리지 않는다
    assert 'href="/ent/"' in home and 'href="/travel/"' in home   # 네비에는 있다


def test_ent_article_renders_under_ent_and_not_in_region_pages(tmp_path):
    items = [make("1", "괌 소식", region="guam"), ent("c-2", "영화 ○○ 개봉", "movie")]
    render_site(items, str(tmp_path), TODAY)
    page = tmp_path / "ent" / "c-2-영화-개봉" / "index.html"
    assert page.exists()
    html = page.read_text(encoding="utf-8")
    assert "연예 · 영화" in html
    assert "피플로드 문화부" in html
    assert "오늘</span>" not in html          # 환율·날씨 띠는 여행 기사에만 붙는다
    assert "여행 상품 보러가기" not in html
    for region_page in ("guam", "jeju"):
        rp = (tmp_path / region_page / "index.html").read_text(encoding="utf-8")
        assert "영화 ○○ 개봉" not in rp
    sec = (tmp_path / "ent" / "movie" / "index.html").read_text(encoding="utf-8")
    assert "영화 ○○ 개봉" in sec
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "영화 ○○ 개봉" in home


def test_ent_article_breadcrumb_goes_through_the_channel(tmp_path):
    render_site([ent("c-2", "영화 ○○ 개봉", "movie")], str(tmp_path), TODAY)
    html = (tmp_path / "ent" / "c-2-영화-개봉" / "index.html").read_text(encoding="utf-8")
    assert '"name": "연예"' in html and '"name": "영화·드라마"' in html
    assert '"articleSection": "영화·드라마"' in html


def test_search_index_tags_ent_articles_with_their_section(tmp_path):
    render_site([ent("c-2", "영화 ○○ 개봉", "movie"), make("1", "괌 소식")],
                str(tmp_path), TODAY)
    rows = json.loads((tmp_path / "search.json").read_text(encoding="utf-8"))
    by = {r["t"]: r for r in rows}
    assert by["영화 ○○ 개봉"]["k"] == "ent/movie" and by["영화 ○○ 개봉"]["r"] == "연예 · 영화·드라마"
    assert by["괌 소식"]["k"] == "guam"


def test_ent_articles_get_no_regional_photo(tmp_path, monkeypatch):
    """괌 해변 사진이 영화 개봉 기사에 붙으면 거짓 그림이다."""
    import src.render.site as site
    calls = []
    monkeypatch.setattr(site, "load_manifest", lambda: {"guam": [{"file": "a.webp"}]})
    monkeypatch.setattr(site, "assign_photos",
                        lambda m, region, seeds, used: calls.append(region) or {})
    monkeypatch.setattr(site, "load_used", lambda: {})
    monkeypatch.setattr(site, "save_used", lambda used: None)
    monkeypatch.setattr(site, "photo_places", lambda m: {})
    monkeypatch.setattr(site, "photo_dims", lambda m, p: {})
    monkeypatch.setattr(site, "render_og_images", lambda *a, **k: 0)
    render_site([make("1", "괌 소식"), ent("c-2", "영화 개봉")], str(tmp_path), TODAY)
    assert "" not in calls and "ent" not in calls


# ── 피드 ──────────────────────────────────────────────────────────
def test_ent_feed_holds_only_ent_and_region_feed_holds_only_travel(tmp_path):
    from src.render.feeds import render_rss
    items = [make("1", "괌 소식"), ent("c-2", "영화 개봉")]
    ent_path = render_rss(items, str(tmp_path), NOW, channel="ent")
    xml = Path(ent_path).read_text(encoding="utf-8")
    assert ent_path.endswith("ent/rss.xml")
    assert "영화 개봉" in xml and "괌 소식" not in xml and "<title>피플로드 연예</title>" in xml
    guam = Path(render_rss(items, str(tmp_path), NOW, region="guam")).read_text(encoding="utf-8")
    assert "괌 소식" in guam and "영화 개봉" not in guam


def test_sitemap_lists_channel_hubs_and_ent_sections(tmp_path):
    from src.render.feeds import render_sitemap
    text = Path(render_sitemap([ent("c-2", "영화 개봉")], str(tmp_path), TODAY)).read_text(encoding="utf-8")
    assert "/travel/</loc>" in text and "/ent/</loc>" in text
    for tid, _, _ in ENT_TOPICS:
        assert f"/ent/{tid}/</loc>" in text
    assert "/ent/c-2-" in text


def test_build_writes_the_ent_feed(tmp_path):
    from src.build import build
    build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    assert (tmp_path / "ent" / "rss.xml").exists()


# ── 발행 경로 ──────────────────────────────────────────────────────
def _draft(tmp_path, **front):
    review = tmp_path / "review"; review.mkdir(exist_ok=True)
    base = {"id": "x", "title": "제목", "status": "approved"}
    base.update(front)
    p = review / "2026-09-25_x.md"
    p.write_text("---\n" + yaml.safe_dump(base, allow_unicode=True, sort_keys=False)
                 + "---\n본문이다.", encoding="utf-8")
    return review


def test_ent_draft_publishes_without_region(tmp_path):
    from src.publish_drafts import collect_approved
    review = _draft(tmp_path, channel="ent", category="drama", region="guam")
    got = collect_approved(str(review), TODAY)
    assert len(got) == 1
    item = got[0][1]
    assert item.channel == "ent" and item.category == "movie" and item.region == ""   # drama → movie


def test_travel_draft_without_region_is_skipped(tmp_path):
    """빈 region 이 조용히 통과해 `//` 주소가 나던 구멍을 막는다."""
    from src.publish_drafts import collect_approved
    review = _draft(tmp_path, region="")
    assert collect_approved(str(review), TODAY) == []


def test_ent_draft_with_unknown_category_is_skipped(tmp_path):
    from src.publish_drafts import collect_approved
    review = _draft(tmp_path, channel="ent", category="gossip")
    assert collect_approved(str(review), TODAY) == []


# ── 피플레이와 함께한 스타 ───────────────────────────────────────
def test_star_trips_file_is_valid_and_ships_empty():
    """명단은 사장님이 채운다. 클로드는 지어내지 않는다."""
    data = yaml.safe_load(open("data/star_trips.yaml", encoding="utf-8"))
    assert data["entries"] == []


def test_star_trips_render_only_with_consent(tmp_path, monkeypatch):
    import src.render.site as site
    rows = {"entries": [
        {"name": "동의한 사람", "region": "guam", "when": "2026-03", "play": "괌플레이",
         "purpose": "화보 촬영", "consent": True},
        {"name": "동의 없는 사람", "region": "guam", "when": "2026-04", "play": "괌플레이",
         "consent": False},
    ]}
    path = tmp_path / "star_trips.yaml"
    path.write_text(yaml.safe_dump(rows, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(site, "STAR_TRIPS", str(path))
    out = tmp_path / "out"
    render_site([], str(out), TODAY)
    html = (out / "ent" / "startrip" / "index.html").read_text(encoding="utf-8")
    assert "피플레이와 함께한 스타" in html
    assert "동의한 사람" in html and "괌플레이" in html
    assert "동의 없는 사람" not in html
    # 다른 연예 부문에는 표가 없다
    assert "피플레이와 함께한 스타" not in (out / "ent" / "movie" / "index.html").read_text(encoding="utf-8")



# ── 연예 소스 수집 경로 ────────────────────────────────────────────
def test_sources_yaml_carries_ent_sources_with_categories():
    from src.sources import load_sources
    ent_sources = [s for s in load_sources("sources.yaml") if s.channel == "ent"]
    assert ent_sources, "연예 소스가 하나도 없다"
    for s in ent_sources:
        # 부문 없는 소스(연예 헤드라인·시상식)는 빈 값 — 제목으로 추정한다. 옛 id 도 허용.
        from src.topics import ENT_ALIASES
        assert s.category in {t for t, _, _ in ENT_TOPICS} | {""} | set(ENT_ALIASES), s.id
        assert s.region == "all"


def test_unknown_channel_or_category_in_sources_is_rejected(tmp_path):
    from src.sources import SourceConfigError, load_sources
    base = ("sources:\n  - id: x\n    region: all\n    section: news\n    name: n\n"
            "    type: rss\n    url: https://e\n    lang: ko\n    enabled: true\n")
    p = tmp_path / "s.yaml"
    p.write_text(base + "    channel: radio\n", encoding="utf-8")
    import pytest
    with pytest.raises(SourceConfigError):
        load_sources(str(p))
    p.write_text(base + "    channel: ent\n    category: gossip\n", encoding="utf-8")
    with pytest.raises(SourceConfigError):
        load_sources(str(p))


def test_google_news_ent_feed_skips_region_check_and_tags_channel():
    from src.fetch.rss import parse_feed
    from src.sources import Source
    src = Source(id="gn_ent_movie", region="all", section="news", name="영화 소식",
                 type="rss", url="https://news.google.com/rss/search?q=x", lang="ko",
                 enabled=True, channel="ent", category="movie")
    xml = """<?xml version="1.0"?><rss><channel>
      <item><title>영화 ○○ 9월 30일 개봉 확정 - 연합뉴스</title><link>https://e/1</link>
        <pubDate>Thu, 25 Sep 2026 01:00:00 GMT</pubDate></item>
      <item><title>배우 ○○ 열애설 부인 - 디스패치</title><link>https://e/2</link>
        <pubDate>Thu, 25 Sep 2026 01:00:00 GMT</pubDate></item>
    </channel></rss>"""
    items = parse_feed(src, xml, "2026-09-25T10:00:00+09:00")
    assert [i.title for i in items] == ["영화 ○○ 9월 30일 개봉 확정"]   # 디스패치는 SKIP_OUTLETS
    item = items[0]
    assert item.channel == "ent" and item.category == "movie" and item.region == ""
    assert item.source_name == "연합뉴스"


def test_edit_keeps_ent_news_but_drops_gossip_and_travel_filter_does_not_apply():
    from src.edit import edit_items
    from src.guards.dup_guard import PublishedIndex
    good = ent("1", "영화 ○○ 제작발표회 개최", "movie", grade="B", summary="배급사가 밝혔다.")
    good.source_name = "연합뉴스"; good.source_url = "https://e/1"
    gossip = ent("2", "배우 ○○ 열애설에 소속사 입장", "star", grade="B", summary="")
    gossip.source_name = "연합뉴스"; gossip.source_url = "https://e/2"
    got = edit_items([good, gossip], PublishedIndex(set(), []), [], set())
    kept = {i.id for i in got["publish"]}
    assert "1" in kept and "2" not in kept
    assert {i.id for i in got["off_topic"]} == {"2"}


def test_ent_exclusion_keywords():
    from src.relevance import is_ent_excluded
    assert is_ent_excluded("○○ 결별설 해명")
    assert is_ent_excluded("○○ 비키니 몸매 공개")
    assert not is_ent_excluded("○○ 월드투어 서울 공연 추가")


def test_ent_items_are_never_commentary_candidates():
    """연예는 편집실이 쓴다. 자동 해설 후보 초안을 만들지 않는다."""
    from src.edit import edit_items
    from src.guards.dup_guard import PublishedIndex
    rows = []
    for n in range(3):
        it = ent(str(n), "영화 ○○ 제작발표회", "movie", grade="B")
        it.source_name = f"매체{n}"; it.source_url = f"https://e/{n}"
        rows.append(it)
    got = edit_items(rows, PublishedIndex(set(), []), ["제작발표회"], set())
    assert got["c_candidates"] == []


def test_ent_exclusion_catches_translated_and_non_entertainment_items():
    from src.relevance import is_ent_excluded
    assert is_ent_excluded("베트남 박스오피스에서 수빈의 영화가 인기를 끄는 이유를 분석해 봅시다")
    assert is_ent_excluded("이번 주 수요일 영화 개봉작에 대한 리뷰를 읽어보세요")
    assert is_ent_excluded("전기의 비너스가 VOD로 시청 가능합니다")
    assert is_ent_excluded("공포 영화 개봉 Silent Hill Townfall 공식 출시 전에 불")
    assert is_ent_excluded("제네시스 GV80 영화 인턴 등장 내달 하이브리드도 출격")
    assert is_ent_excluded("영화 30편 15억달러 투자 약속 파라마운트 워너 인수 눈앞")
    assert is_ent_excluded("아무 제목", source_name="VnExpress International")
    assert not is_ent_excluded("2PM 더 리턴 콘서트 영화로 만난다 10월 21일 개봉", "연합뉴스")
    assert not is_ent_excluded("MBC 새 금토드라마 라이어 대본리딩 현장 공개", "뉴스1")


def test_home_shows_an_entertainment_block_near_the_top(tmp_path):
    """두 축 매체다. 연예가 화면 맨 아래에만 있으면 여행 사이트로 읽힌다."""
    items = [make(str(n), f"괌 소식 {n}", grade="B") for n in range(20)]
    items += [ent(f"e{n}", f"영화 ○○ 개봉 {n}", "movie", grade="B") for n in range(3)]
    render_site(items, str(tmp_path), TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    ent_pos = home.index('class="block-title"><a href="/ent/">')
    first_travel_block = home.index('class="block-title"><a href="/news/">') if '/news/">' in home else len(home)
    assert ent_pos < first_travel_block          # 연예 톱이 여행 부문 블록보다 위
    assert home.count("영화 ○○ 개봉 0") == 1     # 같은 기사가 두 번 걸리지 않는다


def test_ent_skips_broken_outlet_names_and_offtopic_outlets():
    from src.relevance import is_ent_excluded
    assert is_ent_excluded("영화 개봉", source_name="��신문")
    assert is_ent_excluded("영화 개봉", source_name="sortiraparis.com")
    assert is_ent_excluded("영화 개봉", source_name="레디앙")


def test_more_list_excludes_hidden_articles(tmp_path):
    """숨긴(off_topic) 기사는 기사 하단 '더 보기'에도 나오지 않는다."""
    a = ent("c-a", "영화 A 개봉", "movie", grade="B")
    hidden = ent("c-h", "베트남 영화 수익 분석해 봅시다", "movie", grade="B")
    hidden.off_topic = True
    others = [ent(f"c-{n}", f"영화 {n} 개봉", "movie", grade="B") for n in range(3)]
    render_site([a, hidden] + others, str(tmp_path), TODAY)
    import glob as _g
    html = open(_g.glob(str(tmp_path / "ent" / "c-a-*" / "index.html"))[0], encoding="utf-8").read()
    assert "분석해 봅시다" not in html
    assert "영화 0 개봉" in html


def test_generic_ent_feed_requires_an_official_announcement_keyword():
    from src.edit import edit_items
    from src.guards.dup_guard import PublishedIndex
    def row(i, title, cat=""):
        it = ent(str(i), title, cat, grade="B"); it.source_name = f"연합뉴스{i}"; it.source_url = f"https://e/{i}"; return it
    rows = [row(1, "BTS 월드투어 3분기 누적 전 세계 투어 매출 1위"),          # 투어 → 실린다
            row(2, "신현준, 이국적 외모 가족사진 공개"),                      # 가족사진 → 제외
            row(3, "심형래, 179억 빚에 파산까지"),                            # 빚·파산 → 제외
            row(4, "지창욱 얼굴 좋아하죠"),                                    # 발표성 낱말 없음 → 제외
            row(5, "주상욱♥차예련, 9세 딸 첫 공개"),                          # ♥ → 제외
            row(6, "영암서 내달 9일 환경영화제 개막…초등생 제작 영화 상영", "movie")]  # 초등생 → 제외
    got = edit_items(rows, PublishedIndex(set(), []), [], set())
    assert {i.id for i in got["publish"]} == {"1"}


def test_old_section_urls_redirect_to_the_merged_sections(tmp_path):
    render_site([make("1", "괌 소식")], str(tmp_path), TODAY)
    for old, new in (("issue", "news"), ("world", "news"), ("policy", "news"), ("people", "biz")):
        html = (tmp_path / old / "index.html").read_text(encoding="utf-8")
        assert f'url=/{new}/' in html and 'noindex' in html
    for old, new in (("drama", "movie"), ("star", "startrip")):
        html = (tmp_path / "ent" / old / "index.html").read_text(encoding="utf-8")
        assert f'url=/ent/{new}/' in html


def test_home_top_three_mix_both_channels_when_possible(tmp_path):
    """톱·사이드 셋이 한 채널로만 채워지면 한쪽 사이트로 읽힌다."""
    items = [ent(f"c-e{n}", f"영화 {n} 개봉", "movie") for n in range(4)]
    items += [make(f"c-t{n}", f"괌 소식 {n}") for n in range(4)]
    render_site(items, str(tmp_path), TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    top = home.split('class="data-strip"')[0] if 'class="data-strip"' in home else home.split('class="headline-grid"')[0]
    assert "연예 · 영화·드라마" in top and "괌 소식" in top
