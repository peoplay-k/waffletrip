from src.guards.copyright_guard import violations, filter_items
from src.models import Item

NOW = "2026-08-31T05:00:00+09:00"


def make(grade="B", summary="One sentence.", source_name="Guam Post",
         source_url="https://example.com/a", body_md=None):
    return Item(id="x", grade=grade, region="guam", section="news",
                title="제목", summary=summary, source_name=source_name,
                source_url=source_url, published_at=NOW, collected_at=NOW,
                status="draft", title_hash="h", body_md=body_md)


def test_clean_b_item_passes():
    assert violations(make()) == []


def test_b_item_without_source_name_is_rejected():
    assert any("출처" in v for v in violations(make(source_name="")))


def test_b_item_without_source_url_is_rejected():
    assert any("출처" in v for v in violations(make(source_url="")))


def test_b_summary_over_200_chars_is_rejected():
    assert any("200자" in v for v in violations(make(summary="가" * 201)))


def test_b_summary_of_exactly_200_chars_passes():
    assert violations(make(summary="가" * 200)) == []


def test_b_summary_over_two_sentences_is_rejected():
    assert any("문장" in v for v in violations(make(summary="A. B. C.")))


def test_b_summary_of_exactly_two_sentences_passes():
    assert violations(make(summary="A. B.")) == []


def test_empty_summary_is_allowed():
    """제목+링크만 있는 형태가 가장 안전하다. 막을 이유가 없다."""
    assert violations(make(summary="")) == []


def test_html_image_tag_is_rejected():
    assert any("이미지" in v for v in violations(make(summary='<img src="a.jpg">')))


def test_markdown_image_is_rejected():
    assert any("이미지" in v for v in violations(make(summary="![alt](a.png)")))


def test_bare_image_url_is_rejected():
    assert any("이미지" in v
               for v in violations(make(summary="https://x.com/p.jpg")))


def test_image_in_body_is_rejected():
    item = make(grade="C", body_md="본문\n\n![x](https://x.com/a.png)")
    assert any("이미지" in v for v in violations(item))


def test_grade_a_is_exempt_from_length_limits():
    """A등급은 우리가 공공데이터로 만든 문장이라 인용이 아니다."""
    assert violations(make(grade="A", summary="가" * 300)) == []


def test_grade_a_still_needs_attribution():
    assert any("출처" in v for v in violations(make(grade="A", source_url="")))


def test_grade_c_is_exempt_from_length_limits():
    assert violations(make(grade="C", summary="가" * 300, body_md="본문")) == []


def test_grade_c_without_body_is_rejected():
    assert any("본문" in v for v in violations(make(grade="C", body_md="")))


def test_filter_items_splits_kept_and_dropped():
    good, bad = make(), make(summary="가" * 500)
    kept, dropped = filter_items([good, bad])
    assert kept == [good]
    assert len(dropped) == 1
    assert dropped[0][0] is bad
    assert dropped[0][1]


def test_filter_items_on_empty_list():
    assert filter_items([]) == ([], [])
