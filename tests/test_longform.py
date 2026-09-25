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

    for name, sec in [("peopleroad-week", 254), ("peopleroad-zzz-silent", 30)]:
        (tmp_path / f"{name}.json").write_text(
            _json.dumps({"title": name, "seconds": sec, "region": "japan"}),
            encoding="utf-8")
        (tmp_path / f"{name}.mp4").write_bytes(b"x")

    got = load_video(str(tmp_path))
    assert got and got["src"] == "/video/peopleroad-week.mp4", got


def test_사진_없는_곳은_영상을_만들지_않는다():
    """글자만 넘어가는 영상은 릴스가 아니다(2026-09-15 사장님 지적).

    방콕·도쿄·타이베이는 자사 촬영본이 0장이다. 그런데도 영상을 만들어
    인스타에 올렸다 — 사진 153장을 갖고 있으면서 한 장도 안 썼다.
    사진이 모자라면 **만들지 않는다.** 같은 사진을 돌려써도 티가 난다.
    """
    import make_shorts as ms

    assert ms.MIN_PHOTOS >= 3, "장면 수만큼은 있어야 반복이 안 보인다"
    with pytest.raises(SystemExit) as e:
        ms.build("bangkok")
    assert "사진" in str(e.value)


def test_제목_끝에_붙은_분류_딱지를_뗀다():
    """RSS 제목 끝에 "…출시, , 생활/문화" 가 붙어 들어온다(실측).

    화면에 그대로 얹히면 기사 제목이 아니라 긁어온 티가 난다.
    """
    from make_shorts import tidy

    assert tidy("휴양 결합 패키지 출시, , 생활/문화") == "휴양 결합 패키지 출시"
    assert tidy("괌 여행 소식, 사회") == "괌 여행 소식"
    assert tidy("정상 제목입니다") == "정상 제목입니다"
    # 본문 안의 쉼표는 건드리지 않는다
    assert tidy("도쿄, 오사카, 후쿠오카") == "도쿄, 오사카, 후쿠오카"


def test_영상_속_사진은_그_지역_것이다():
    """다낭 편에 하노이 훅교가 나오면 그건 그냥 틀린 화면이다."""
    import json

    import make_shorts as ms

    manifest = json.load(open("assets/photos/manifest.json", encoding="utf-8"))
    files = {e["file"] for e in manifest.get("saipan", [])}
    got = ms.region_photos("saipan")
    assert got, "사이판 사진을 못 찾았다"
    assert set(got) <= files, "다른 지역 사진이 섞였다"


def test_하루_한_편은_간격이_아니라_날짜로_센다():
    """간격으로 재면 매일 정해진 시각에 도는 일정과 어긋난다.

    2026-09-16 실측: 전날 17:14 에 나갔더니 이튿날 10:05 회차가 18시간에
    1.1시간 모자라 건너뛰었고, 그날은 한 편도 안 나갔다. 깃허브 크론은
    몇 시간씩 밀리므로 간격 규칙으로는 이런 날이 계속 생긴다.
    """
    import sys
    from datetime import datetime, timedelta, timezone

    sys.path.insert(0, "tools")
    from publish_instagram import posted_today

    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    어제늦게 = (now - timedelta(days=1)).replace(hour=17, minute=14)
    오늘 = now.replace(hour=10, minute=5)

    assert posted_today({"log": []}) == ""
    # 어제 늦게 나갔어도 오늘은 나가야 한다
    assert posted_today({"log": [{"at": 어제늦게.strftime("%Y-%m-%d %H:%M:%S")}]}) == ""
    # 오늘 이미 나갔으면 예비 크론이 깨도 막힌다
    assert posted_today({"log": [{"at": 오늘.strftime("%Y-%m-%d %H:%M:%S")}]})


def test_영문_제목은_영상에_안_올린다():
    """지역 매체 제목이 영문 그대로 들어온다.

    2026-09-16 실측: 인스타에 "First Alert Forecast: Mostly dry trade winds"
    한 줄짜리 하와이 편이 그대로 올라갔다. 한국어로 읽는 독자에게 영문
    제목은 빈 화면과 같고, 한 건짜리는 릴스로 낼 값이 안 된다.
    """
    import make_shorts as ms

    assert ms.is_korean("괌정부관광청, 팸트립 개최")
    assert not ms.is_korean("First Alert Forecast: Mostly dry trade winds")
    assert not ms.is_korean("")
    assert ms.MIN_FACTS >= 3, "한 건짜리 영상은 내지 않는다"


def test_speakable_drops_broadcast_credit_blocks():
    import sys
    sys.path.insert(0, "tools")
    from video_brief import _speakable
    assert _speakable("■ 방송 : 아시아경제 '소종섭의 시사쇼'■ 진행 : 소종섭 정치스페셜리스트■ 연출 : 이미리 PD", 150) == ""
    assert _speakable("일본에서 스시자로 열풍이 불고 있다. 두 번째 문장.", 150).startswith("일본에서")


def test_voiced_flag_falls_back_to_silent_when_narration_fails(tmp_path, monkeypatch):
    """키가 없으면 나레이션이 SystemExit 을 던진다. 그래도 영상은 나가야 한다."""
    import sys
    sys.path.insert(0, "tools")
    import make_longform as lf
    monkeypatch.setattr(lf, "build_script", lambda items: [{"kind": "open", "headline": "h",
                                                              "narration": "안녕하세요", "region": "japan"}])
    monkeypatch.setattr(lf, "load_items", lambda: [])
    monkeypatch.setattr(lf, "build_voiced", lambda scenes, out: (_ for _ in ()).throw(SystemExit("[중단] 키 없음")))
    called = {}
    monkeypatch.setattr(lf, "build_silent", lambda scenes, out: called.setdefault("silent", out) or str(tmp_path / "x.mp4"))
    monkeypatch.setattr(lf, "read_seconds", lambda t: 1.0)
    monkeypatch.setattr(lf, "screen_text", lambda s: "x")
    monkeypatch.setattr(sys, "argv", ["make_longform", "--voiced", "--out", str(tmp_path)])
    assert lf.main() == 0
    assert called.get("silent") == str(tmp_path)
