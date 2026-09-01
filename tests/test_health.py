"""조용한 실패를 잡는 감시. 이게 없으면 05시에 아무 일도 안 일어나도 모른다."""
from __future__ import annotations

import json

from src.health import diagnose, snapshot, update_history


def _day(date, collected=10, published=5, failed=()):
    return {"date": date, "collected": collected, "published": published,
            "failed_sources": list(failed)}


def test_zero_collection_is_fatal():
    fatal, _ = diagnose([_day("2026-09-02", collected=0)])
    assert fatal and "수집이 0건" in fatal[0]


def test_three_empty_publish_days_is_fatal():
    history = [_day(f"2026-09-0{i}", published=0) for i in (1, 2, 3)]
    fatal, _ = diagnose(history)
    assert any("연속 발행 0건" in f for f in fatal)


def test_two_empty_days_is_not_yet_fatal():
    history = [_day(f"2026-09-0{i}", published=0) for i in (1, 2)]
    fatal, _ = diagnose(history)
    assert not any("연속 발행 0건" in f for f in fatal)


def test_healthy_history_has_no_fatal():
    history = [_day(f"2026-09-0{i}") for i in (1, 2, 3)]
    fatal, warn = diagnose(history)
    assert fatal == [] and warn == []


def test_source_failing_three_days_warns_but_does_not_kill():
    """소스 하나가 죽어도 신문은 나가야 한다."""
    history = [_day(f"2026-09-0{i}", failed=["guam_post"]) for i in (1, 2, 3)]
    fatal, warn = diagnose(history)
    assert fatal == []
    assert any("guam_post" in w for w in warn)


def test_source_failing_intermittently_does_not_warn():
    history = [_day("2026-09-01", failed=["a"]), _day("2026-09-02"),
               _day("2026-09-03", failed=["a"])]
    _, warn = diagnose(history)
    assert warn == []


def test_snapshot_counts_files(tmp_path):
    raw = tmp_path / "raw" / "2026-09-02"
    raw.mkdir(parents=True)
    (raw / "items.json").write_text(json.dumps([{}, {}, {}]), encoding="utf-8")
    (raw / "_errors.json").write_text(
        json.dumps([{"source_id": "x", "error": "boom"}]), encoding="utf-8")
    items = tmp_path / "items"
    items.mkdir()
    (items / "2026-09-02.jsonl").write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")

    got = snapshot(str(tmp_path), "2026-09-02")
    assert got["collected"] == 3
    assert got["published"] == 2
    assert got["failed_sources"] == ["x"]


def test_snapshot_survives_missing_files(tmp_path):
    got = snapshot(str(tmp_path), "2026-09-02")
    assert got == {"date": "2026-09-02", "collected": 0, "published": 0,
                   "failed_sources": []}


def test_update_history_replaces_same_day(tmp_path):
    path = str(tmp_path / "health.json")
    update_history(path, _day("2026-09-02", collected=1))
    history = update_history(path, _day("2026-09-02", collected=99))
    assert len(history) == 1 and history[0]["collected"] == 99
