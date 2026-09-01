"""사진 승인 게이트. 검출기는 표식일 뿐이고 진짜 안전장치는 사람 승인이다."""
from __future__ import annotations

import pytest

cv2 = pytest.importorskip(
    "cv2", reason="photo_prepare 는 로컬 운영 도구다. CI 의존성에 넣지 않는다.")

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
from photo_prepare import parse_approve, propagate_blocks  # noqa: E402


def test_parse_approve_handles_ranges_and_lists():
    assert parse_approve("1,4,7-9", 10) == [1, 4, 7, 8, 9]


def test_parse_approve_drops_out_of_range_and_garbage():
    assert parse_approve("0,3,99,abc,,-", 5) == [3]


def test_parse_approve_empty_means_nothing_approved():
    """빈 승인은 '전부'가 아니라 '아무것도'여야 한다."""
    assert parse_approve("", 10) == []


def _v(src, ok, reason=""):
    return {"src": src, "ok": ok, "reason": reason, "faces": 0, "person": 0.0}


def test_block_spreads_across_the_same_scene():
    """실측에서 나온 실패 — 같은 로비 사진 둘 중 하나만 걸리고 하나는 통과했다.

    통과한 쪽에도 사람이 서 있었다. 한 번이라도 걸린 장면은 전부 막는다.
    """
    results = [_v("/x/e20_2.jpg", True), _v("/x/e20_2_hi.jpg", False, "얼굴 2건 검출")]
    assert propagate_blocks(results) == 1
    assert all(not v["ok"] for v in results)
    assert "같은 장면" in results[0]["reason"]


def test_clean_scene_group_is_left_alone():
    results = [_v("/x/a.jpg", True), _v("/x/a_hi.jpg", True)]
    assert propagate_blocks(results) == 0
    assert all(v["ok"] for v in results)


def test_unrelated_photos_do_not_affect_each_other():
    results = [_v("/x/a.jpg", True), _v("/x/b.jpg", False, "얼굴 1건 검출")]
    assert propagate_blocks(results) == 0
    assert results[0]["ok"] is True
