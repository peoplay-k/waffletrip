from pathlib import Path

from src.edit import (edit_items, write_drafts, purge_stale_drafts,
                      load_trending)
from src.guards.dup_guard import PublishedIndex
from src.models import Item, title_hash

NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, section="news", summary="한 문장.", related=None):
    return Item(id=item_id, grade="B", region="guam", section=section,
                title=title, summary=summary, source_name="Guam Post",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash=title_hash(title),
                related=list(related or []))


def empty_index():
    return PublishedIndex(set(), [])


def test_clean_items_reach_publish():
    result = edit_items([make("1", "괌 소식 하나")], empty_index(), [])
    assert [i.id for i in result["publish"]] == ["1"]


def test_copyright_violation_is_dropped_not_published():
    bad = make("1", "괌 소식", summary="가" * 300)
    result = edit_items([bad], empty_index(), [])
    assert result["publish"] == []
    assert len(result["dropped"]) == 1


def test_data_section_gets_grade_a():
    item = make("1", "오늘의 환율 — 1 USD", section="data")
    result = edit_items([item], empty_index(), [])
    assert result["publish"][0].grade == "A"


def test_same_story_from_two_outlets_collapses():
    items = [make("1", "괌 신규 취항 노선 확정"),
             make("2", "괌 신규 취항 노선 확정")]
    result = edit_items(items, empty_index(), [])
    assert len(result["publish"]) == 1
    assert result["publish"][0].related == ["2"]


def test_previously_published_item_is_filtered():
    index = empty_index()
    index.add(make("1", "괌 신규 취항 노선 확정"), "2026-08-30")
    result = edit_items([make("1", "괌 신규 취항 노선 확정")], index, [])
    assert result["publish"] == []
    assert len(result["duplicates"]) == 1


def test_c_candidates_are_selected():
    items = [make("1", "괌 호텔 요금 인상", related=[])]
    items[0].related = ["2", "3"]
    result = edit_items(items, empty_index(), [])
    assert len(result["c_candidates"]) == 1


def test_empty_input_produces_empty_result():
    result = edit_items([], empty_index(), [])
    assert result == {"publish": [], "c_candidates": [], "dropped": [],
                      "duplicates": []}


def test_write_drafts_creates_one_markdown_per_candidate(tmp_path):
    candidates = [(make("abc", "괌 호텔 요금 인상"), "3개 매체가 보도")]
    paths = write_drafts(str(tmp_path), candidates, "2026-08-31")
    assert len(paths) == 1
    text = Path(paths[0]).read_text(encoding="utf-8")
    assert "괌 호텔 요금 인상" in text
    assert "3개 매체가 보도" in text
    assert "status: draft" in text


def test_write_drafts_filename_carries_date_and_id(tmp_path):
    candidates = [(make("abc", "제목"), "사유")]
    paths = write_drafts(str(tmp_path), candidates, "2026-08-31")
    assert Path(paths[0]).name == "2026-08-31_abc.md"


def test_purge_removes_drafts_older_than_two_days(tmp_path):
    (tmp_path / "2026-08-25_old.md").write_text("x", encoding="utf-8")
    (tmp_path / "2026-08-30_recent.md").write_text("x", encoding="utf-8")
    removed = purge_stale_drafts(str(tmp_path), "2026-08-31")
    assert [Path(p).name for p in removed] == ["2026-08-25_old.md"]
    assert (tmp_path / "2026-08-30_recent.md").exists()


def test_purge_keeps_draft_exactly_at_the_boundary(tmp_path):
    (tmp_path / "2026-08-29_edge.md").write_text("x", encoding="utf-8")
    assert purge_stale_drafts(str(tmp_path), "2026-08-31") == []


def test_purge_ignores_files_with_unexpected_names(tmp_path):
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    assert purge_stale_drafts(str(tmp_path), "2026-08-31") == []
    assert (tmp_path / "README.md").exists()


def test_purge_on_missing_directory_is_not_an_error(tmp_path):
    assert purge_stale_drafts(str(tmp_path / "nope"), "2026-08-31") == []


# --- 급상승 키워드 이음매 ---

def test_trending_file_missing_yields_empty_list(tmp_path):
    """파일이 없어도 파이프라인은 돌아야 한다. 규칙 ②만 건너뛴다."""
    assert load_trending(str(tmp_path)) == []


def test_trending_file_is_read(tmp_path):
    (tmp_path / "trending.json").write_text(
        '{"keywords": ["마나가하", "괌 환율"]}', encoding="utf-8")
    assert load_trending(str(tmp_path)) == ["마나가하", "괌 환율"]


def test_corrupt_trending_file_does_not_break_the_build(tmp_path):
    """키워드는 있으면 좋은 것이지 없으면 못 도는 것이 아니다."""
    (tmp_path / "trending.json").write_text("{ broken", encoding="utf-8")
    assert load_trending(str(tmp_path)) == []


def test_trending_keyword_produces_a_candidate_end_to_end():
    item = make("1", "사이판 마나가하 입장료 인상")
    result = edit_items([item], empty_index(), ["마나가하"])
    assert len(result["c_candidates"]) == 1
    assert "마나가하" in result["c_candidates"][0][1]
