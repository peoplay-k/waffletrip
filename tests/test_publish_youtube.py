"""와플트립 유튜브 발행기 — 중복 방지, 롱폼 주 1회, 채널 핸들 확인."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "tools")
import publish_youtube as yt  # noqa: E402

KST = timezone(timedelta(hours=9))
LATEST = {"stem": "peopleroad-guam-20261016-voiced", "name": "괌",
          "caption": "괌 이번 주 소식 4건\n\n· 첫 소식\n\n전문은 waffletrip.com\n\n#괌 #괌여행 #travel"}
META = {"title": "이번 주 여행 뉴스", "kind": "voiced", "built_at": "2026-10-19T09:00:00+09:00",
        "outlets": ["Pacific Daily News"]}


def test_short_is_planned_once():
    state = {"posted": []}
    p = yt.plan_short(state, LATEST)
    assert p["url"].endswith("/video/peopleroad-guam-20261016-voiced.mp4")
    assert p["title"].endswith("#Shorts") and p["tags"] == ["괌", "괌여행", "travel"]
    state["posted"].append({"key": p["key"], "kind": "short"})
    assert yt.plan_short(state, LATEST) is None


def test_longform_at_most_weekly_and_only_voiced():
    now = datetime(2026, 10, 19, 10, tzinfo=KST)
    assert yt.plan_longform({"posted": []}, META, now)["kind"] == "longform"
    recent = {"posted": [{"kind": "longform", "key": "longform:x", "at": (now - timedelta(days=3)).isoformat()}]}
    assert yt.plan_longform(recent, META, now) is None
    old = {"posted": [{"kind": "longform", "key": "longform:x", "at": (now - timedelta(days=8)).isoformat()}]}
    assert yt.plan_longform(old, META, now) is not None
    assert yt.plan_longform({"posted": []}, {**META, "kind": "silent"}, now) is None


def test_only_the_peopleroad_channel_passes():
    assert yt.handle_ok("@peopleroad") and yt.handle_ok("@PeopleRoad") and yt.handle_ok("peopleroad")
    assert not yt.handle_ok("@waffletrip") and not yt.handle_ok("@피플로드")
    assert not yt.handle_ok("@guami_travel") and not yt.handle_ok("")


def test_no_secrets_means_no_upload(monkeypatch, tmp_path, capsys):
    for k in ("WAFFLETRIP_YT_CLIENT_ID", "WAFFLETRIP_YT_CLIENT_SECRET", "WAFFLETRIP_YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(yt, "POSTED", str(tmp_path / "posted.json"))
    monkeypatch.setattr(yt, "_fetch_json", lambda url: None)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "shorts_latest.json").write_text(__import__("json").dumps(LATEST), encoding="utf-8")
    assert yt.main(["--post"]) == 0
    assert "시크릿이 없어 건너뛴다" in capsys.readouterr().out
