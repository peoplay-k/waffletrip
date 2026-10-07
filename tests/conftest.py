"""테스트 공통 설정.

**시한폭탄 검사.** 날짜를 박아 둔 테스트가 '오늘 기준 30일' 같은 규칙과 만나면, 코드는
멀쩡한데 시간이 지나 저절로 깨진다. 워크플로가 테스트를 발행보다 먼저 돌리므로 그날
지면이 통째로 멈춘다 — 2026-09-30(중복검사 테스트, 8/30)과 2026-10-03(건강검진 테스트,
9/2) 두 번 실제로 그랬다. 그래서 시계를 앞으로 돌려 미리 깨 본다.

    TEST_DAYS_AHEAD=60 python -m pytest -q     # 60일 뒤에도 통과하나

값이 없으면 아무것도 하지 않는다(평소 테스트는 실제 시계로 돈다).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

_AHEAD = int(os.environ.get("TEST_DAYS_AHEAD") or 0)


@pytest.fixture(autouse=True)
def _shift_clock():
    if not _AHEAD:
        yield
        return
    from freezegun import freeze_time
    target = datetime.now(timezone.utc) + timedelta(days=_AHEAD)
    with freeze_time(target, tick=True):
        yield


@pytest.fixture(autouse=True)
def _isolate_photo_usage(tmp_path_factory, monkeypatch):
    """테스트가 진짜 사진 사용 기록(data/photos/used.json)을 쓰지 못하게 한다.

    사진은 한 번 쓰면 다시 안 쓰므로, 테스트가 가짜 기사로 사진을 잡으면 그 사진은
    지면에 영영 안 나간다. CI 는 테스트 뒤 data/ 를 커밋하므로 매일 사진이 새어 나갔다.
    """
    import src.photos as photos
    # tmp_path 와 다른 폴더에 둔다 — 출력 폴더 밖에 파일이 생기는지 보는 테스트가 있다.
    monkeypatch.setattr(photos, "USED",
                        str(tmp_path_factory.mktemp("photo_usage") / "used.json"))
    yield
