import json

import pytest

from src.guards.dup_guard import (PublishedIndex, IndexUnavailable,
                                  cluster_batch, filter_unpublished)
from src.models import Item

NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, source_name="A"):
    from src.models import title_hash
    return Item(id=item_id, grade="B", region="guam", section="news",
                title=title, summary="s", source_name=source_name,
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash=title_hash(title))


# --- 배치 내 클러스터링 ---

def test_identical_titles_collapse_to_one():
    items = [make("1", "괌 신규 취항 확정"), make("2", "괌 신규 취항 확정", "B")]
    result = cluster_batch(items)
    assert len(result) == 1
    assert result[0].related == ["2"]


def test_similar_titles_collapse_and_record_related():
    items = [make("1", "괌 신규 취항 노선 확정 발표"),
             make("2", "괌 신규 취항 노선 확정", "B"),
             make("3", "괌 신규 취항 노선 확정 소식", "C")]
    result = cluster_batch(items)
    assert len(result) == 1
    assert sorted(result[0].related) == ["2", "3"]


def test_grade_a_items_with_identical_titles_are_not_merged():
    """지역별 환율은 제목이 같아도 서로 다른 항목이다.

    실측에서 이걸 묶는 바람에 사이판·하와이의 환율 패널이 통째로 사라졌다.
    A등급은 우리가 만든 사실 데이터이지 남의 보도가 아니다.
    """
    fx = []
    for n, region in enumerate(("guam", "saipan", "hawaii"), start=1):
        item = make(str(n), "오늘의 환율 — 1 USD")
        item.grade, item.region, item.section = "A", region, "data"
        fx.append(item)
    result = cluster_batch(fx)
    assert [i.region for i in result] == ["guam", "saipan", "hawaii"]


def test_same_title_in_different_regions_is_not_merged():
    """다른 곳 이야기는 제목이 같아도 같은 사건일 수 없다."""
    a = make("1", "신규 취항 노선 확정 발표")
    b = make("2", "신규 취항 노선 확정 발표")
    b.region = "jeju"
    assert len(cluster_batch([a, b])) == 2


def test_same_region_still_clusters_after_the_guard():
    """지역·등급 제한이 진짜 중복까지 막으면 안 된다."""
    a = make("1", "괌 신규 취항 노선 확정 발표")
    b = make("2", "괌 신규 취항 노선 확정")
    result = cluster_batch([a, b])
    assert len(result) == 1
    assert result[0].related == ["2"]


def test_different_titles_are_kept_separately():
    items = [make("1", "괌 신규 취항 확정"), make("2", "제주 해수욕장 개장 연기")]
    assert len(cluster_batch(items)) == 2


def test_cluster_keeps_first_as_representative():
    items = [make("1", "괌 신규 취항 확정"), make("2", "괌 신규 취항 확정", "B")]
    assert cluster_batch(items)[0].id == "1"


def test_cluster_on_empty_list():
    assert cluster_batch([]) == []


# --- 발행 이력 대조 ---

def test_missing_index_file_is_treated_as_first_run(tmp_path):
    index = PublishedIndex.load(str(tmp_path / "nope.json"))
    assert index.contains(make("1", "아무거나")) is False


def test_corrupt_index_file_raises_fail_closed(tmp_path):
    path = tmp_path / "published_index.json"
    path.write_text("{ this is not json", encoding="utf-8")
    with pytest.raises(IndexUnavailable):
        PublishedIndex.load(str(path))


def test_previously_published_id_is_filtered_out(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("1", "괌 신규 취항 확정"), "2026-08-30")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished([make("1", "괌 신규 취항 확정")], reloaded)
    assert fresh == []
    assert len(seen) == 1


def test_same_story_different_url_is_caught_by_title(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("1", "괌 신규 취항 노선 확정 발표"), "2026-08-30")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished(
        [make("999", "괌 신규 취항 노선 확정")], reloaded)
    assert fresh == []
    assert len(seen) == 1


def test_unrelated_new_story_passes(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("1", "괌 신규 취항 확정"), "2026-08-30")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished(
        [make("2", "라오스 비자 규정 변경")], reloaded)
    assert len(fresh) == 1
    assert seen == []


def test_save_prunes_titles_older_than_thirty_days(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("old", "아주 오래된 소식 제목"), "2026-01-01")
    index.add(make("new", "최근 소식 제목"), "2026-08-30")
    index.save(path)

    data = json.loads(open(path, encoding="utf-8").read())
    assert {r["id"] for r in data["recent"]} == {"new"}
    # id 는 영구 보관한다 — 오래된 기사라도 재발행은 막아야 한다
    assert set(data["ids"]) == {"old", "new"}


def test_save_folds_duplicate_ids_in_recent(tmp_path):
    """같은 날 빌드를 두 번 돌려도 recent 가 부풀지 않아야 한다."""
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    item = make("dup", "같은 기사 제목")
    index.add(item, "2026-08-30")
    index.add(item, "2026-08-30")
    index.save(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert len(data["recent"]) == 1


def test_permanently_kept_id_still_blocks_old_story(tmp_path):
    path = str(tmp_path / "idx.json")
    index = PublishedIndex.load(path)
    index.add(make("old", "아주 오래된 소식 제목"), "2026-01-01")
    index.save(path)

    reloaded = PublishedIndex.load(path)
    fresh, seen = filter_unpublished(
        [make("old", "아주 오래된 소식 제목")], reloaded)
    assert fresh == []
