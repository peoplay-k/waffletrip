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


def test_여행_기사거리가_아닌_제목은_재료에서_뺀다():
    """2026-10-30 종합지 여행면을 붙인 첫 실행에서 재료에 섞여 들어온 것들."""
    from story_material import is_not_travel
    for t in ["[부고] 서호영 씨(대한항공 전무) 모친상",
              "북한, '무인항공기술발전-2026' 전시회 개최",
              "인천공항, '바이오 화물' 잡는다…유럽 콜드체인 동맹 강화",
              "놀에 이어 마이리얼트립까지…여행·숙박 플랫폼 잇단 개인정보 유출",
              "염동열 강원관광재단 대표 후보자 청문회서 '보은 인사' 공방"]:
        assert is_not_travel(t), t
    for t in ["이스타항공 홍콩~부산 신규 취항…첫 입국 관광객 200여명 '환영'",
              "엔저에 일본행 급증…원·엔 환율 900원대",
              "하동군, 섬진강권 관광지 순환버스로 주말여행 편의 높인다",
              "겨울에 눈여겨볼 만한 해외 패키지여행 3"]:
        assert not is_not_travel(t), t
