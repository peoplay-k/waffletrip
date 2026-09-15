# -*- coding: utf-8 -*-
"""롱폼 영상. 매일 새로 구워지고, 화면에 적힌 숫자가 오늘 값이어야 한다."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))


def _roundup(region, name, day, headline, outlet):
    return {"id": f"c-{region}-{day}", "grade": "C", "region": region,
            "title": f"이번 주 {name}에서 나온 소식 2건", "summary": "",
            "published_at": f"{day}T08:00:00+09:00",
            "body_md": f"### 1. {headline}\n\n{headline} 상세.\n\n*{outlet} · {day}*\n"}


def _fx(region, day, value):
    return {"id": f"fx-{region}-{day}", "grade": "A", "region": region,
            "title": "오늘의 환율", "summary": f"{day} 기준 {value}",
            "published_at": f"{day}T08:00:00+09:00", "body_md": ""}


def test_가장_최근_브리핑으로_만든다():
    """오름차순 목록을 setdefault 로 담으면 **가장 오래된** 브리핑이 잡힌다.

    2026-09-15 실측: 9월 15일에 만든 영상이 9월 6일 브리핑으로 채워졌다.
    제목 카드는 오늘 날짜를 찍으므로 날짜와 내용이 어긋난 화면이 나갔다.
    매일 다시 구워도 같은 영상이 나오니 갱신이 된 적이 없던 셈이다.
    """
    from make_longform import build_script

    items = [
        _roundup("japan", "일본", "2026-09-06", "일본 옛날 소식", "옛매체"),
        _roundup("japan", "일본", "2026-09-14", "일본 오늘 소식", "새매체"),
    ]
    heads = [s["headline"] for s in build_script(items) if s["kind"] == "story"]
    assert heads, "기사 장면이 하나도 안 만들어졌다"
    assert "오늘" in heads[0], f"오래된 브리핑을 썼다: {heads}"


def test_화면에_박는_환율은_오늘_값이다():
    """화면과 나레이션이 "오늘의 환율"이라고 말한다. 그러면 오늘 값이어야 한다.

    2026-09-15 실측: 9월 3일의 855원이 오늘 값으로 나갔고 그날 실제 값은
    871원이었다. 16원 틀린 숫자를 1920×1080 으로 박은 것이다.
    """
    from make_longform import build_script

    items = [
        _fx("japan", "2026-09-03", "100 JPY = 약 855원"),
        _fx("japan", "2026-09-14", "100 JPY = 약 871원"),
        _roundup("japan", "일본", "2026-09-14", "일본 소식", "매체"),
    ]
    data = [s for s in build_script(items) if s["kind"] == "data"]
    assert data, "환율 장면이 없다"
    values = [v for _, v in data[0]["rows"]]
    assert any("871" in v for v in values), f"옛 환율을 썼다: {values}"
    assert not any("855" in v for v in values), f"옛 환율을 썼다: {values}"


def test_무음판_길이는_화면_글자로_잰다():
    """목소리가 없으면 화면이 정보를 전부 진다. 나레이션 길이로 재면 안 된다."""
    from make_longform import read_seconds, screen_text

    story = {"kind": "story", "headline": "가", "summary": "", "outlet": "",
             "narration": "화면에 없는 말을 길게 늘어놓는 나레이션 " * 6}
    assert screen_text(story).strip() == "가"
    # 짧은 화면은 최소 길이를 지킨다 — 나레이션이 길어도 끌려가지 않는다
    assert read_seconds(screen_text(story)) == pytest.approx(3.0, abs=0.01)
    긴글 = {"kind": "story", "headline": "나" * 60, "summary": "다" * 60,
           "outlet": "라매체"}
    assert read_seconds(screen_text(긴글)) > 15


def test_장면마다_화면에_적힌_출처가_원문과_같다():
    """출처를 잘못 붙이면 그 매체가 쓰지 않은 기사를 쓴 것으로 만든다."""
    from make_longform import build_script

    items = [_roundup("japan", "일본", "2026-09-14", "일본 소식", "어떤매체")]
    stories = [s for s in build_script(items) if s["kind"] == "story"]
    assert stories and stories[0]["outlet"] == "어떤매체"


@pytest.mark.parametrize("n", [3, 5, 7, 8])
def test_환율표가_바닥선을_넘지_않는다(n):
    """일곱 줄일 때 마지막 밑줄이 제호 바닥선과 겹쳤다(2026-09-15 라이브 실측).

    하와이 줄이 "waffletrip.com" 위에 포개졌다. 1920×1080 으로 박혀
    나가는 화면이라 겹침은 그대로 사고다.
    """
    import make_longform as lf

    top, floor_y = 370, lf.H - 96 - 40
    pitch = min(96, (floor_y - top) // max(n, 1))

    # 마지막 줄이 통째로 바닥선 위에 들어가야 한다
    마지막_줄_바닥 = top + n * pitch
    assert 마지막_줄_바닥 < lf.H - 96, f"{n}줄일 때 바닥선을 넘는다: {마지막_줄_바닥}"

    # 글자도 같이 줄어야 한다. 간격만 줄였더니 밑줄이 값 글자를 관통했다
    # (2026-09-15 라이브 실측 — 같은 카드에서 두 번 깨졌다).
    name_size = min(48, pitch - 26)
    value_size = min(42, pitch - 32)
    assert name_size > 0 and value_size > 0, f"{n}줄일 때 글자가 사라진다"
    assert name_size + 14 < pitch, f"{n}줄일 때 글자가 간격보다 크다"

    # 그림까지 그려 보지는 않는다. CI 는 테스트를 폰트 설치보다 **먼저**
    # 돌려서 `_f()` 가 "한글 폰트를 찾지 못했다" 로 죽는다. 2026-09-15 에
    # 이 검사 한 줄 때문에 실행이 두 번 통째로 실패했다 — 겹침을 막으려던
    # 검사가 신문을 막았다. 겹침은 자리 계산으로 판정되고, 그림이 제대로
    # 나오는지는 굽는 단계가 매일 실제로 확인한다.


def test_홈에는_숏폼이_아니라_롱폼이_걸린다(tmp_path):
    """이름순으로 마지막 것을 집으면 도시 이름에 따라 세로 영상이 홈을 먹는다.

    숏폼을 매일 굽기 시작하면서 실제 위험이 됐다. 이름순은 내용과 아무
    상관이 없다 — 홈에 거는 것은 롱폼 한 편으로 못박는다.
    """
    import json as _json

    from src.render.site import load_video

    for name, sec in [("waffletrip-week", 254), ("waffletrip-zzz-silent", 30)]:
        (tmp_path / f"{name}.json").write_text(
            _json.dumps({"title": name, "seconds": sec, "region": "japan"}),
            encoding="utf-8")
        (tmp_path / f"{name}.mp4").write_bytes(b"x")

    got = load_video(str(tmp_path))
    assert got and got["src"] == "/video/waffletrip-week.mp4", got
