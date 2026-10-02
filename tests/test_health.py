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
                   "ours": 0, "failed_sources": []}


def test_update_history_replaces_same_day(tmp_path):
    path = str(tmp_path / "health.json")
    update_history(path, _day("2026-09-02", collected=1))
    history = update_history(path, _day("2026-09-02", collected=99))
    assert len(history) == 1 and history[0]["collected"] == 99


def test_묵은_홈영상을_잡는다(tmp_path):
    """홈 영상이 아흐레 멈춰 있는데 아무 검사도 울지 않았다(2026-09-15 사장님 지적).

    그 사이 화면에 박힌 환율도 9월 3일 값(855원)이었고 그날 실제 값은
    871원이었다. 영상은 한 번 나가면 되돌리기가 어렵다 — 멈추면 울려야 한다.
    """
    import json
    from datetime import datetime, timedelta, timezone

    from src.health import video_age_days
    KST = timezone(timedelta(hours=9))
    meta = tmp_path / "peopleroad-week.json"

    assert video_age_days(str(tmp_path)) is None          # 영상 자체가 없다

    옛날 = (datetime.now(KST) - timedelta(days=9)).isoformat(timespec="seconds")
    meta.write_text(json.dumps({"built_at": 옛날}), encoding="utf-8")
    assert 8.9 < video_age_days(str(tmp_path)) < 9.1

    오늘 = datetime.now(KST).isoformat(timespec="seconds")
    meta.write_text(json.dumps({"built_at": 오늘}), encoding="utf-8")
    assert video_age_days(str(tmp_path)) < 0.1

    # 언제 만든 것인지 안 적혀 있으면 묵은 것으로 본다. 9월 6일에 손으로
    # 올린 파일이 정확히 이 모양이었다 — built_at 이 아예 없었다.
    meta.write_text(json.dumps({"title": "이번 주 여행 뉴스"}), encoding="utf-8")
    assert video_age_days(str(tmp_path)) > 100


# ── 2026-10-02 부터: 지면이 해설에 달렸다 ─────────────────────────
def test_snapshot_counts_our_own_articles(tmp_path):
    import json as _j
    items = tmp_path / "items"
    items.mkdir()
    rows = [{"id": "c-1", "grade": "C"}, {"id": "c-2", "grade": "C"},
            {"id": "ab12", "grade": "B"}, {"id": "cd34", "grade": "A"}]
    (items / "2026-10-03.jsonl").write_text(
        "\n".join(_j.dumps(r) for r in rows), encoding="utf-8")
    snap = snapshot(str(tmp_path), "2026-10-03")
    assert snap["published"] == 4 and snap["ours"] == 2


def test_two_silent_days_raise_the_alarm_but_today_is_not_counted():
    from src.health import own_silence
    hist = [{"date": "2026-10-03", "ours": 0}, {"date": "2026-10-04", "ours": 0},
            {"date": "2026-10-05", "ours": 0}]
    assert own_silence(hist, "2026-10-05")             # 3일·4일이 0편
    hist[1]["ours"] = 6
    assert not own_silence(hist, "2026-10-05")
    # 아침 실행: 오늘(5일)은 에이전트 전이라 0편이어도 세지 않는다
    assert not own_silence([{"date": "2026-10-04", "ours": 7},
                            {"date": "2026-10-05", "ours": 0}], "2026-10-05")


def test_old_records_without_our_count_do_not_raise_the_alarm():
    from src.health import own_silence
    assert not own_silence([{"date": "2026-09-30"}, {"date": "2026-10-01"}], "2026-10-02")
