import pytest
from src.sources import load_sources, SourceConfigError


def write(tmp_path, text):
    p = tmp_path / "sources.yaml"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_loads_valid_source(tmp_path):
    path = write(tmp_path, """
sources:
  - id: guam_post
    region: guam
    section: news
    name: The Guam Daily Post
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    sources = load_sources(path)
    assert len(sources) == 1
    assert sources[0].id == "guam_post"
    assert sources[0].region == "guam"


def test_skips_disabled_source(tmp_path):
    path = write(tmp_path, """
sources:
  - id: dead
    region: guam
    section: news
    name: Dead Feed
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: false
""")
    assert load_sources(path) == []


def test_rejects_unknown_region(tmp_path):
    path = write(tmp_path, """
sources:
  - id: bad
    region: mars
    section: news
    name: Mars Times
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="region"):
        load_sources(path)


def test_rejects_unknown_section(tmp_path):
    path = write(tmp_path, """
sources:
  - id: bad
    region: guam
    section: gossip
    name: Guam Gossip
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="section"):
        load_sources(path)


def test_rejects_unknown_type(tmp_path):
    path = write(tmp_path, """
sources:
  - id: bad
    region: guam
    section: news
    name: Guam Podcast
    type: podcast
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="type"):
        load_sources(path)


def test_rejects_missing_required_field(tmp_path):
    path = write(tmp_path, """
sources:
  - id: bad
    region: guam
    section: news
    name: Guam Missing Type
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="필수 항목 누락"):
        load_sources(path)


def test_rejects_duplicate_id(tmp_path):
    path = write(tmp_path, """
sources:
  - id: same
    region: guam
    section: news
    name: A
    type: rss
    url: https://example.com/a
    lang: en
    enabled: true
  - id: same
    region: jeju
    section: news
    name: B
    type: rss
    url: https://example.com/b
    lang: ko
    enabled: true
""")
    with pytest.raises(SourceConfigError, match="중복"):
        load_sources(path)


def test_real_sources_yaml_is_valid():
    """실제 sources.yaml 이 항상 로드 가능해야 한다."""
    sources = load_sources("sources.yaml")
    assert len(sources) > 0


def test_curated_defaults_to_false(tmp_path):
    """기존 소스를 전부 고치지 않아도 되게 선택 필드로 둔다."""
    path = write(tmp_path, """
sources:
  - id: plain
    region: guam
    section: news
    name: Plain
    type: rss
    url: https://example.com/rss
    lang: en
    enabled: true
""")
    assert load_sources(path)[0].curated is False


def test_curated_can_be_set(tmp_path):
    path = write(tmp_path, """
sources:
  - id: travelmag
    region: auto
    section: news
    name: 여행신문
    type: rss
    url: https://example.com/rss
    lang: ko
    enabled: true
    curated: true
""")
    assert load_sources(path)[0].curated is True


# ── culture: 여행·문화가 섞인 매체(문화뉴스, 2026-10-30) ───────────────────────
def test_culture_defaults_to_false(tmp_path):
    path = write(tmp_path, """
sources:
  - id: travelmag
    region: auto
    section: news
    name: 여행신문
    type: rss
    url: https://example.com/rss
    lang: ko
    enabled: true
""")
    assert load_sources(path)[0].culture is False


def test_culture_can_be_set_on_an_auto_source(tmp_path):
    path = write(tmp_path, """
sources:
  - id: mhns
    region: auto
    section: news
    name: 문화뉴스
    type: rss
    url: https://example.com/rss
    lang: ko
    enabled: true
    industry: false
    culture: true
""")
    src = load_sources(path)[0]
    assert src.culture is True and src.industry is False


def test_culture_is_rejected_outside_auto_sources(tmp_path):
    """지역이 고정된 소스나 연예 소스에는 기사마다 채널을 가를 일이 없다."""
    path = write(tmp_path, """
sources:
  - id: fixed
    region: guam
    section: news
    name: 괌 매체
    type: rss
    url: https://example.com/rss
    lang: ko
    enabled: true
    culture: true
""")
    with pytest.raises(SourceConfigError, match="culture"):
        load_sources(path)


def test_owner_named_sources_are_registered_and_enabled():
    """2026-10-30 사장님이 짚은 세 매체 — TTL뉴스·문화뉴스·ㅍㅍㅅㅅ — 가 전부 켜져 있어야 한다."""
    by_id = {s.id: s for s in load_sources("sources.yaml")}
    for sid in ("kr_ttlnews", "kr_mhns", "kr_ppss"):
        assert sid in by_id, sid
        assert by_id[sid].region == "auto" and by_id[sid].industry is False
    assert by_id["kr_mhns"].culture is True
    assert by_id["kr_ppss"].curated is False     # 여행 전문지가 아니다 — 편집 필터를 태운다


# ── 2026-10-30 소스 확장 — 사장님: "내가 말한 거기는 그냥 그런거고 너가 기사를 다 찾아서 넣어야지
#    왜 3군데만 봐 다른곳도 다 봐" ─────────────────────────────────────────────────────
def _real():
    return {s.id: s for s in load_sources("sources.yaml")}


def test_major_outlets_are_searched_one_feed_each_as_auto_industry_off():
    """종합지·통신사는 site: 검색으로 받고, 지명·여행 말이 없는 기사는 수집 단계가 버리는 설정이어야 한다."""
    by_id = _real()
    for sid in ("gn_yna", "gn_newsis", "gn_news1", "gn_chosun", "gn_joongang", "gn_donga", "gn_mk",
                "gn_hankyung", "gn_khan", "gn_hankookilbo", "gn_herald", "gn_kbs", "gn_ytn"):
        s = by_id[sid]
        assert "news.google.com/rss/search" in s.url and "site%3A" in s.url, sid
        assert s.region == "auto" and s.industry is False and s.curated is False, sid


def test_every_auto_google_search_source_turns_industry_off():
    """region: auto 인 검색 피드는 어떤 매체든 섞여 오므로 industry: false 가 아니면 보도자료가 새어 든다."""
    for s in _real().values():
        if s.region == "auto" and "news.google.com" in s.url:
            assert s.industry is False and s.curated is False, s.id


def test_new_korean_trade_press_is_curated_auto():
    by_id = _real()
    for sid in ("kr_gtn", "kr_ktnbm", "kr_travelpress"):
        assert by_id[sid].region == "auto" and by_id[sid].curated is True, sid
        assert by_id[sid].url.endswith("/rss/allArticle.xml"), sid
    for sid in ("kr_hotelrestaurant", "kr_hotelavia", "kr_kdfnews"):   # 외식·화장품이 섞인다
        assert by_id[sid].industry is False and by_id[sid].curated is False, sid


def test_thin_regions_got_local_and_city_sources():
    by_id = _real()
    expect = {
        "thailand": ("thailand_bangkokpost_travel", "thailand_tatnews", "gn_phuket", "gn_chiangmai", "gn_pattaya"),
        "taiwan": ("taiwan_taipeitimes", "gn_focustaiwan_en", "gn_taipei", "gn_kaohsiung", "gn_tainan"),
        "laos": ("gn_vientianetimes_en", "gn_luangprabang", "gn_vientiane"),
        "saipan": ("gn_saipan_ko2",),
        "kota": ("gn_sabah_press_en", "gn_kota_ko2"),
        "japan": ("japan_japantoday", "gn_kyoto", "gn_hiroshima", "gn_kagoshima"),
        "vietnam": ("gn_vietnamnews_en", "gn_hochiminh", "gn_phuquoc"),
        "hawaii": ("hawaii_civilbeat", "hawaii_magazine"),
    }
    for region, ids in expect.items():
        for sid in ids:
            assert sid in by_id, sid
            assert by_id[sid].region == region, (sid, by_id[sid].region)


def test_english_sources_declare_their_language():
    """영문 제목은 해설 에이전트가 옮긴다(src/title_ko.py). lang 이 맞아야 그 길로 간다."""
    by_id = _real()
    for sid in ("thailand_thaiger", "japan_japantimes", "hawaii_khon2", "gn_sabah_press_en", "gn_japan_en"):
        assert by_id[sid].lang == "en", sid
    # 더스타 여행면(kota_thestar_travel)은 첫 실행에 404 라 꺼 두었다 — 켜면 auto/industry:false 여야 한다
    if "kota_thestar_travel" in by_id:
        assert by_id["kota_thestar_travel"].region == "auto" and by_id["kota_thestar_travel"].industry is False


def test_enabled_sources_do_not_share_a_url():
    urls = [s.url for s in _real().values()]
    assert len(urls) == len(set(urls))
