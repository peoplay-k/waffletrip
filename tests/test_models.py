from src.models import (Item, normalize_url, make_id, title_hash,
                        title_tokens, jaccard, item_to_dict, item_from_dict)


def test_normalize_url_strips_tracking_params():
    url = "https://Example.com/news/a?utm_source=x&id=7&fbclid=zz#top"
    assert normalize_url(url) == "https://example.com/news/a?id=7"


def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://example.com/news/") == "https://example.com/news"


def test_normalize_url_keeps_root_slash():
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_make_id_is_stable_for_same_url():
    a = make_id("https://example.com/a?utm_source=x", "제목", "2026-08-31")
    b = make_id("https://example.com/a", "다른 제목", "2026-09-01")
    assert a == b, "URL 이 같으면 제목이 달라도 같은 항목이다"


def test_make_id_falls_back_to_title_when_no_url():
    a = make_id("", "괌 신규 취항", "2026-08-31")
    b = make_id("", "괌 신규 취항", "2026-08-31")
    c = make_id("", "괌 신규 취항", "2026-09-01")
    assert a == b
    assert a != c


def test_title_hash_ignores_spacing_and_punctuation():
    assert title_hash("괌, 신규 취항!") == title_hash("괌 신규취항")


def test_title_tokens_drops_one_character_words():
    assert title_tokens("괌 에 신규 취항") == {"신규", "취항"}


def test_jaccard_identical_is_one():
    assert jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_is_zero():
    assert jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty_sets_is_zero():
    assert jaccard(set(), set()) == 0.0


def test_item_roundtrips_through_dict():
    item = Item(
        id="abc", grade="B", region="guam", section="news",
        title="괌 신규 취항", summary="요약", source_name="Guam Post",
        source_url="https://example.com/a", published_at="2026-08-31T09:00:00+09:00",
        collected_at="2026-08-31T05:00:00+09:00", status="draft",
        title_hash="hhh",
    )
    assert item_from_dict(item_to_dict(item)) == item


def test_item_roundtrips_with_body_and_related():
    item = Item(
        id="abc", grade="C", region="jeju", section="flight",
        title="t", summary="s", source_name="n", source_url="u",
        published_at="2026-08-31T09:00:00+09:00",
        collected_at="2026-08-31T05:00:00+09:00", status="approved",
        title_hash="h", body_md="# 본문", related=["x", "y"],
    )
    assert item_from_dict(item_to_dict(item)) == item
