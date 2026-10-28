"""편집실에서 고친 발행 기사가 지면에 반영된다(2026-10-28)."""
import json

from src.sync_edits import sync


def _setup(tmp_path, title="괌 노선 재개", body="대구공항의 괌 노선이 12월 재개된다고 국토교통부가 밝혔다.\n"):
    data = tmp_path / "data"; (data / "items").mkdir(parents=True)
    review = tmp_path / "review"; review.mkdir()
    rec = {"id": "c-abc12345", "grade": "C", "region": "guam", "section": "news",
           "title": "괌 노선 재개", "summary": "옛 요약", "source_name": "", "source_url": "",
           "published_at": "2026-10-28T09:00:00+09:00", "collected_at": "2026-10-28T09:00:00+09:00",
           "status": "published", "title_hash": "x", "body_md": "옛 본문"}
    (data / "items" / "2026-10-28.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    (review / "a.md").write_text(
        "---\n" f"title: {title}\nchannel: travel\nregion: guam\nsection: news\n"
        "summary: 새 요약\nstatus: published\npublished_id: c-abc12345\n---\n" + body,
        encoding="utf-8")
    return data, review


def _rec(data):
    return json.loads((data / "items" / "2026-10-28.jsonl").read_text(encoding="utf-8"))


def test_edited_body_reaches_the_published_record(tmp_path):
    data, review = _setup(tmp_path)
    assert sync(str(data), str(review)) == 1
    rec = _rec(data)
    assert rec["summary"] == "새 요약" and rec["body_md"].startswith("대구공항의 괌 노선")
    assert sync(str(data), str(review)) == 0          # 두 번 돌려도 같다


def test_new_title_keeps_the_old_url_alive(tmp_path):
    data, review = _setup(tmp_path, title="대구공항, 12월 괌 노선 재개")
    sync(str(data), str(review))
    assert _rec(data)["title"] == "대구공항, 12월 괌 노선 재개"
    moved = json.loads((data / "moved_urls.json").read_text(encoding="utf-8"))
    assert moved == {"/guam/c-abc123-괌-노선-재개/": "c-abc12345"}


def test_edit_never_brings_media_attribution_back(tmp_path):
    """발행 때와 같은 문 — 매체 인용은 걷어내고 싣는다."""
    data, review = _setup(tmp_path, body="연합뉴스 보도에 따르면 괌 노선이 재개된다.\n")
    sync(str(data), str(review))
    assert "보도에 따르면" not in _rec(data)["body_md"]


def test_edit_with_private_data_is_held(tmp_path):
    data, review = _setup(tmp_path, body="예약자 연락처 010-1234-5678 로 문의.\n")
    assert sync(str(data), str(review)) == 0
    assert _rec(data)["body_md"] == "옛 본문"
