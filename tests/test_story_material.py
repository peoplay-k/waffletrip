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


def test_여행신문_최근_50건을_따로_늘어놓고_쓴_것에_표시한다(tmp_path, monkeypatch):
    """2026-11-04 사장님: "기사 매일 여행신문쪽 50개 훑어보고 거기서 기사를 가지고와"."""
    import json
    import story_material as sm
    items = tmp_path / "data" / "items"
    items.mkdir(parents=True)
    rows = [{"id": f"x{i}", "grade": "B", "region": "industry", "source_name": "여행신문",
             "title": f"여행 소식 {i}", "summary": "요약", "published_at": f"2026-11-0{1 + i % 3}T0{i % 10}:00",
             "source_url": f"https://www.traveltimes.co.kr/a{i}"} for i in range(60)]
    rows.append({"id": "y", "grade": "B", "region": "industry", "source_name": "트래블데일리",
                 "title": "다른 매체", "published_at": "2026-11-03T00:00", "source_url": "https://t/1"})
    rows.append({"id": "z", "grade": "B", "region": "industry", "source_name": "여행신문",
                 "title": "[단독] 남의 단독", "published_at": "2026-11-03T09:00", "source_url": "https://t/2"})
    (items / "2026-11-03.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    picked = sm.latest_from("여행신문", 50)
    assert len(picked) == 50
    assert all(r["source_name"] == "여행신문" for r in picked)
    assert all("단독" not in r["title"] for r in picked)
    lines = sm.traveltimes_section(picked, {picked[0]["source_url"]})
    assert lines[0].startswith("## 여행신문 최근 50건")
    assert lines[5].startswith("- ✅ ")
    assert sum(1 for x in lines if x.startswith("- ✅")) == 1
