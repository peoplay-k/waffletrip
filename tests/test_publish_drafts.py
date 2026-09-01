"""승인 초안 → 발행. 막혀 있던 C등급 경로를 지키는 테스트."""
from __future__ import annotations

import json
import os

import yaml

from src.guards.dup_guard import PublishedIndex
from src.publish_drafts import collect_approved, commentary_id, main

DAY = "2026-09-02"
SOURCE_ID = "1333b01d49834bac5aa53f940e0b132c63f0ef82"


def _draft(tmp_path, status="approved", body="본문입니다.", **over):
    review = tmp_path / "review"
    review.mkdir(exist_ok=True)
    front = {"id": SOURCE_ID, "region": "hawaii", "section": "flight",
             "title": "하와이 직항 재개", "source_name": "Beat of Hawaii",
             "source_url": "https://beatofhawaii.com/a", "status": status}
    front.update(over)
    path = review / f"{DAY}_{SOURCE_ID}.md"
    path.write_text("---\n" + yaml.safe_dump(front, allow_unicode=True,
                                             sort_keys=False) + "---\n" + body,
                    encoding="utf-8")
    return review, path


def test_commentary_id_never_collides_with_source_id():
    """원본 id 는 순수 16진수다. 접두사 'c-' 가 있으면 겹칠 수 없다.

    이게 C등급이 막혀 있던 진짜 이유였다 — 초안 파일명이 원본 id 라
    승인해도 원본이 이미 발행 이력에 있어서 중복으로 걸렸다.
    """
    new_id = commentary_id(SOURCE_ID, DAY)
    assert new_id != SOURCE_ID
    assert new_id.startswith("c-")
    assert commentary_id(SOURCE_ID, DAY) == new_id          # 안정적


def test_only_approved_drafts_are_collected(tmp_path):
    review, _ = _draft(tmp_path, status="draft")
    assert collect_approved(str(review), DAY) == []


def test_approved_draft_becomes_grade_c_item(tmp_path):
    review, _ = _draft(tmp_path)
    got = collect_approved(str(review), DAY)
    assert len(got) == 1
    item = got[0][1]
    assert item.grade == "C"
    assert item.status == "published"
    assert item.body_md == "본문입니다."
    assert item.region == "hawaii"


def test_empty_body_is_not_published(tmp_path):
    """status 만 approved 로 바꾸고 본문을 안 쓴 초안이 빈 기사로 나가면 안 된다."""
    review, _ = _draft(tmp_path, body="<!-- 여기에 해설을 쓴다 -->\n")
    assert collect_approved(str(review), DAY) == []


def test_summary_falls_back_to_first_paragraph(tmp_path):
    review, _ = _draft(tmp_path, body="## 제목\n\n첫 문단이다.\n\n두번째.")
    assert collect_approved(str(review), DAY)[0][1].summary == "첫 문단이다."


def test_explicit_summary_wins(tmp_path):
    review, _ = _draft(tmp_path, summary="직접 쓴 요약", body="첫 문단.")
    assert collect_approved(str(review), DAY)[0][1].summary == "직접 쓴 요약"


def test_main_writes_item_and_marks_draft_published(tmp_path, monkeypatch):
    review, path = _draft(tmp_path)
    data = tmp_path / "data"
    (data / "items").mkdir(parents=True)

    import src.publish_drafts as pd
    monkeypatch.setattr(pd, "datetime", _FixedDatetime)

    assert main(str(data), str(review)) == 0

    lines = (data / "items" / f"{DAY}.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["grade"] == "C"

    front = yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])
    assert front["status"] == "published"          # 다음 실행에 또 안 나간다


def test_main_appends_and_does_not_clobber_edit_output(tmp_path, monkeypatch):
    """edit.py 가 먼저 쓴 같은 파일을 덮어쓰면 그날 기사가 전부 사라진다."""
    review, _ = _draft(tmp_path)
    data = tmp_path / "data"
    (data / "items").mkdir(parents=True)
    (data / "items" / f"{DAY}.jsonl").write_text(
        '{"id":"기존"}\n', encoding="utf-8")

    import src.publish_drafts as pd
    monkeypatch.setattr(pd, "datetime", _FixedDatetime)
    main(str(data), str(review))

    lines = (data / "items" / f"{DAY}.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["id"] == "기존"


def test_already_published_id_is_skipped(tmp_path, monkeypatch):
    review, _ = _draft(tmp_path)
    data = tmp_path / "data"
    (data / "items").mkdir(parents=True)
    index = PublishedIndex(set(), [])
    from src.models import Item
    from src.publish_drafts import commentary_id as cid
    index.ids.add(cid(SOURCE_ID, DAY))
    index.save(str(data / "published_index.json"))

    import src.publish_drafts as pd
    monkeypatch.setattr(pd, "datetime", _FixedDatetime)
    main(str(data), str(review))
    assert not (data / "items" / f"{DAY}.jsonl").exists()


class _FixedDatetime:
    """오늘 날짜를 고정한다. 테스트가 자정을 넘겨 깨지지 않게."""
    @staticmethod
    def now(tz=None):
        import datetime as _dt
        return _dt.datetime(2026, 9, 2, 10, 0, tzinfo=tz)


def test_draft_with_customer_phone_is_blocked(tmp_path):
    """고객 정보가 든 초안은 승인돼 있어도 나가지 않는다."""
    review, _ = _draft(tmp_path, body="고객 연락처는 010-1234-5678 이었다.")
    assert collect_approved(str(review), DAY) == []


def test_draft_with_trade_price_is_blocked(tmp_path):
    review, _ = _draft(tmp_path, body="이번 넷가는 12만원이었다.")
    assert collect_approved(str(review), DAY) == []


def test_clean_draft_still_passes(tmp_path):
    review, _ = _draft(tmp_path, body="실제 결제가는 180,000원이었다.")
    assert len(collect_approved(str(review), DAY)) == 1
