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
