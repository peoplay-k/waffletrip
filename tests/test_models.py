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


def test_title_tokens_keeps_single_digits():
    """한 자리 숫자를 버리면 "Update 1" 과 "Update 5" 가 같은 글이 된다.

    실측에서 태풍 속보 5·4·3·1호가 하나로 병합됐다. 두 자리인 11·12호는
    분리되던 것과 비일관이라 더 나빴다.
    """
    assert title_tokens("Storm Update 5") == {"storm", "update", "5"}
    assert title_tokens("Storm Update 5") != title_tokens("Storm Update 1")


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


# ── 회사명 꼬리 정규화 ──────────────────────────────────────────────
# 2026-09-08 실측: 청주~타이베이 취항 3주년 기사가 "에어로케이" 와
# "에어로케이항공" 으로 갈려 자카드 0.667 로 임계값을 못 넘고 지면에 두 번 실렸다.

def test_회사명_꼬리를_떼면_같은_사건으로_묶인다():
    from src.models import jaccard, title_tokens
    a = title_tokens("에어로케이, 청주~타이베이 취항 3주년…39만 명 수송")
    b = title_tokens("에어로케이항공, 청주-타이베이 취항 3주년... 3년간 39만 명 수송")
    assert jaccard(a, b) >= 0.7


def test_몸통이_두_글자면_꼬리를_떼지_않는다():
    """제주항공→제주 로 줄이면 제주 지역 기사를 전부 삼킨다."""
    from src.models import title_tokens
    for name in ("제주항공", "대한항공", "일본항공", "한진그룹"):
        assert title_tokens(name) == {name}


def test_몸통이_세_글자_이상이면_꼬리를_뗀다():
    from src.models import title_tokens
    assert title_tokens("아시아나항공") == {"아시아나"}
    assert title_tokens("이스타항공") == {"이스타"}


def test_제주항공은_제주_기사와_섞이지_않는다():
    """정규화가 지역명까지 건드리면 안 된다는 회귀 검사."""
    from src.models import jaccard, title_tokens
    a = title_tokens("제주항공, 부산~오사카 노선 증편한다")
    b = title_tokens("제주 관광객 올해 첫 감소…내국인 발길 줄어")
    assert jaccard(a, b) < 0.7
