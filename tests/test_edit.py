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
    result = edit_items([make("1", "괌 여행 소식 하나")], empty_index(), [], set())
    assert [i.id for i in result["publish"]] == ["1"]


def test_copyright_violation_is_dropped_not_published():
    bad = make("1", "괌 여행 소식", summary="가" * 300)
    result = edit_items([bad], empty_index(), [], set())
    assert result["publish"] == []
    assert len(result["dropped"]) == 1


def test_data_section_gets_grade_a():
    item = make("1", "오늘의 환율 — 1 USD", section="data")
    result = edit_items([item], empty_index(), [], set())
    assert result["publish"][0].grade == "A"


def test_same_story_from_two_outlets_collapses():
    items = [make("1", "괌 신규 취항 노선 확정"),
             make("2", "괌 신규 취항 노선 확정")]
    result = edit_items(items, empty_index(), [], set())
    assert len(result["publish"]) == 1
    assert result["publish"][0].related == ["2"]


def test_previously_published_item_is_filtered():
    index = empty_index()
    index.add(make("1", "괌 신규 취항 노선 확정"), "2026-08-30")
    result = edit_items([make("1", "괌 신규 취항 노선 확정")], index, [], set())
    assert result["publish"] == []
    assert len(result["duplicates"]) == 1


def test_c_candidates_are_selected():
    items = [make("1", "괌 호텔 요금 인상", related=[])]
    items[0].related = ["2", "3"]
    result = edit_items(items, empty_index(), [], set())
    assert len(result["c_candidates"]) == 1


def test_empty_input_produces_empty_result():
    result = edit_items([], empty_index(), [], set())
    assert result == {"publish": [], "c_candidates": [], "dropped": [],
                      "duplicates": [], "off_topic": []}


def test_write_drafts_creates_one_markdown_per_candidate(tmp_path):
    candidates = [(make("abc", "괌 호텔 요금 인상"), "3개 매체가 보도")]
    paths = write_drafts(str(tmp_path), candidates, "2026-08-31")
    assert len(paths) == 1
    text = Path(paths[0]).read_text(encoding="utf-8")
    assert "괌 호텔 요금 인상" in text
    assert "3개 매체가 보도" in text
    assert "status: draft" in text


def test_draft_front_matter_survives_a_colon_in_the_title(tmp_path):
    """제목의 콜론이 프런트매터를 깨뜨리면 검수 워크플로가 파일을 못 읽는다.

    실측 351건 중 37건이 콜론을 담은 제목이었다.
    """
    import yaml
    title = "DPS: 76-year-old man died of natural causes"
    candidates = [(make("abc", title), "3개 매체가 보도")]
    path = write_drafts(str(tmp_path), candidates, "2026-08-31")[0]
    front = Path(path).read_text(encoding="utf-8").split("---")[1]
    parsed = yaml.safe_load(front)
    assert parsed["title"] == title
    assert parsed["status"] == "draft"
    assert parsed["reason"] == "3개 매체가 보도"


def test_draft_front_matter_keeps_korean_readable(tmp_path):
    """한글이 \\uXXXX 로 깨지면 사람이 검수할 수 없다."""
    candidates = [(make("abc", "괌 신규 취항 확정"), "항공 노선 변동")]
    path = write_drafts(str(tmp_path), candidates, "2026-08-31")[0]
    text = Path(path).read_text(encoding="utf-8")
    assert "괌 신규 취항 확정" in text
    assert "\\u" not in text


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


def test_purge_keeps_approved_drafts(tmp_path):
    """승인해둔 초안이 48시간 뒤 사라지면 검수한 일이 헛수고가 된다."""
    old = tmp_path / "2026-08-25_approved.md"
    old.write_text("---\nid: x\nstatus: approved\n---\n\n본문", encoding="utf-8")
    assert purge_stale_drafts(str(tmp_path), "2026-08-31") == []
    assert old.exists()


def test_purge_still_removes_stale_unapproved_drafts(tmp_path):
    old = tmp_path / "2026-08-25_draft.md"
    old.write_text("---\nid: x\nstatus: draft\n---\n\n", encoding="utf-8")
    assert len(purge_stale_drafts(str(tmp_path), "2026-08-31")) == 1
    assert not old.exists()


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
    item = make("1", "사이판 마나가하 관광 입장료 인상")
    result = edit_items([item], empty_index(), ["마나가하"], set())
    assert len(result["c_candidates"]) == 1
    assert "마나가하" in result["c_candidates"][0][1]


# --- 여행 관련성 필터 ---

def test_off_topic_articles_are_dropped():
    """여행 신문 1면에 살인 사건이 실리던 것을 막는다."""
    item = make("1", "Teen shot and killed by her ex-boyfriend, police say")
    result = edit_items([item], empty_index(), [], set())
    assert result["publish"] == []
    assert len(result["off_topic"]) == 1


def test_curated_sources_skip_the_relevance_filter():
    """여행 전용 매체는 그대로 통과시킨다. 필터를 걸면 멀쩡한 기사를 잃는다."""
    item = make("1", "노랑풍선 신상품 3종 출시")
    item.source_name = "여행신문"
    result = edit_items([item], empty_index(), [], {"여행신문"})
    assert len(result["publish"]) == 1


def test_grade_a_data_always_passes():
    """환율은 여행 키워드가 없어도 실려야 한다."""
    item = make("1", "오늘의 환율 — 1 USD", section="data")
    result = edit_items([item], empty_index(), [], set())
    assert len(result["publish"]) == 1


# --- 타임존 ---

def test_main_uses_kst_not_runner_timezone(tmp_path, monkeypatch):
    """러너는 UTC 로 돈다. UTC 날짜를 쓰면 collect 가 만든 디렉터리를 못 찾는다.

    실측: cron 20:00 UTC 는 05:00 KST(익일)이라 두 날짜가 항상 하루 어긋났고,
    예약 실행이 100% 편집 단계에서 죽었다.
    """
    import src.edit as edit_mod
    from datetime import datetime, timezone, timedelta
    kst_today = datetime.now(edit_mod.KST).date().isoformat()
    utc_today = datetime.now(timezone.utc).date().isoformat()
    raw = tmp_path / "raw" / kst_today
    raw.mkdir(parents=True)
    (raw / "items.json").write_text("[]", encoding="utf-8")
    assert edit_mod.main(str(tmp_path), str(tmp_path / "review")) == 0, (
        f"KST={kst_today} UTC={utc_today} — KST 디렉터리를 찾아야 한다")


def test_purge_keeps_published_drafts(tmp_path):
    """발행된 기사의 원고가 48시간 뒤 사라지면 안 된다."""
    import os
    import yaml
    from src.edit import purge_stale_drafts
    review = tmp_path / "review"
    review.mkdir()
    for status in ("draft", "approved", "published"):
        p = review / f"2026-08-01_{status}aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md"
        p.write_text("---\n" + yaml.safe_dump({"status": status}) + "---\n본문",
                     encoding="utf-8")

    removed = purge_stale_drafts(str(review), "2026-09-02")
    names = {os.path.basename(p) for p in removed}
    assert any("draft" in n for n in names)
    assert not any("approved" in n for n in names)
    assert not any("published" in n for n in names)
