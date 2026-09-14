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
