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
