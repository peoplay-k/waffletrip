"""기사거리 묶음. 남의 단독 기사는 재료로 쓰지 않는다(2026-10-01 편집국장)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
from story_material import is_exclusive  # noqa: E402


def test_exclusive_stories_are_not_material():
    for title in ("[단독] 대한항공, 괌 노선 증편", "(단독)제주항공 신규 취항",
                  "단독: 아시아나 사이판 재개", "【단독】 하와이 호텔 매각",
                  "EXCLUSIVE: Guam resort sold"):
        assert is_exclusive(title), title


def test_ordinary_words_are_not_mistaken_for_exclusives():
    for title in ("괌 단독 여행 늘어", "단독주택 화재 없이 지나가", "사이판 단독 패키지 출시"):
        assert not is_exclusive(title), title
