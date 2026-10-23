"""숏폼은 우리가 쓴 기사로 만들고, 매일 다른 이름을 갖는다 (2026-10-15)."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from make_shorts import caption_for, own_facts, stem_of  # noqa: E402

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 15, 12, 0, tzinfo=KST)


def row(i, title, summary="요약입니다.", grade="C", region="guam", days_ago=1,
        section="news"):
    at = (NOW - timedelta(days=days_ago)).isoformat()
    return dict(id=str(i), title=title, summary=summary, grade=grade, region=region,
                section=section, channel="travel", published_at=at)


def test_인용과_옛_묶음과_지난주_기사는_재료가_아니다():
    items = [
        row(1, "괌 노선 증편", "진에어가 괌 노선을 늘린다."),
        row(2, "괌 인용 기사", grade="B"),
        row(3, "이번 주 괌에서 나온 소식"),
        row(4, "괌 오래된 소식", days_ago=9),
        row(5, "사이판 소식", region="saipan"),
        row(6, "10월 15일 여행 데이터", section="data"),
    ]
    got = own_facts(items, "guam", "", "괌", now=NOW)
    assert [f["headline"] for f in got] == ["괌 노선 증편"]
    assert got[0]["outlet"] == ""          # 남의 매체 이름을 읽지 않는다


def test_같은_소식을_두_번_쓴_기사는_한_번만():
    s = "켄싱턴호텔 사이판이 숙박·식사·액티비티를 한 번에 묶은 패키지를 내놨습니다."
    items = [row(1, "켄싱턴 패키지", s, region="saipan"),
             row(2, "켄싱턴 패키지 출시", s.replace("한 번에", "하나로"), region="saipan",
                 days_ago=2)]
    assert len(own_facts(items, "saipan", "", "사이판", now=NOW)) == 1


def test_도시_영상은_그_도시_이름이_든_기사만():
    items = [row(1, "하노이 호텔 개관", region="vietnam"),
             row(2, "다낭 리조트 수상", region="vietnam")]
    got = own_facts(items, "vietnam", "hanoi", "하노이", now=NOW)
    assert [f["headline"] for f in got] == ["하노이 호텔 개관"]


def test_영상_이름에_날짜가_들어가_매일_다르다():
    a = stem_of("guam", NOW)
    b = stem_of("guam", NOW + timedelta(days=1))
    assert a == "peopleroad-guam-20261015" and a != b


def test_캡션에_인용_매체가_없다():
    scenes = [{"kind": "fact", "headline": "괌 노선 증편", "outlet": ""}]
    assert "인용" not in caption_for("guam", scenes)


def test_연예_숏폼을_릴스_대상으로_올린다(tmp_path, monkeypatch):
    import json as _json
    import make_shorts as ms
    monkeypatch.chdir(tmp_path)
    day = ms.datetime.now(ms.KST).strftime("%Y%m%d")
    out = tmp_path / "video"
    out.mkdir()
    (out / f"peopleroad-tv-{day}-1.mp4").write_bytes(b"x")
    (out / f"peopleroad-tv-{day}.json").write_text(_json.dumps({
        "videos": [{"file": f"peopleroad-tv-{day}-1.mp4", "kind": "voiced", "seconds": 19}],
        "youtube": {"title": "[오늘의 방송] 10/23 a", "description": "설명\n\n기사 전문 x", "tags": ["오늘의방송"]}}),
        encoding="utf-8")
    assert ms.use_ent_short(str(out))
    latest = _json.loads((tmp_path / "data" / "shorts_latest.json").read_text(encoding="utf-8"))
    assert latest["stem"] == f"peopleroad-tv-{day}-1" and "#오늘의방송" in latest["caption"]


def test_연예_숏폼이_무음이면_올리지_않는다(tmp_path):
    import json as _json
    import make_shorts as ms
    day = ms.datetime.now(ms.KST).strftime("%Y%m%d")
    (tmp_path / f"peopleroad-tv-{day}-1.mp4").write_bytes(b"x")
    (tmp_path / f"peopleroad-tv-{day}.json").write_text(_json.dumps({
        "videos": [{"file": f"peopleroad-tv-{day}-1.mp4", "kind": "silent"}]}), encoding="utf-8")
    assert not ms.use_ent_short(str(tmp_path))
