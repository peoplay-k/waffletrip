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


def test_연예_숏폼은_여행_채널에_올리지_않는다():
    latest = {"stem": "peopleroad-tv-20261028-1", "city": "tv", "caption": "x"}
    assert yt.plan_short({"posted": []}, latest) is None


# ★ 2026-10-30 연예 채널(@waffletrip)
ENT_META = {"date": "2026-10-30", "videos": [
    {"file": "peopleroad-tv-20261030.mp4", "kind": "voiced"},
    {"file": "peopleroad-tv-20261030-1.mp4", "kind": "voiced"},
    {"file": "peopleroad-tv-20261030-2.mp4", "kind": "voiced"},
    {"file": "peopleroad-tv-20261030-3.mp4", "kind": "silent"}],
    "youtube": {"title": "[오늘의 방송] 10/30 취미는 과학", "description": "설명", "tags": ["오늘의방송", "취미는과학"]}}
NOW = datetime(2026, 10, 30, 12, tzinfo=KST)


def test_연예는_그날것만_롱폼먼저_하루상한():
    plans = yt.plan_ent({"posted": []}, ENT_META, NOW, limit=2)
    assert [p["kind"] for p in plans] == ["ent_longform", "ent_short"]
    assert plans[0]["url"].endswith("/video/peopleroad-tv-20261030.mp4")
    assert plans[1]["title"].endswith("(1) #Shorts") and plans[1]["channel"] == "ent"
    assert yt.plan_ent({"posted": []}, ENT_META, NOW + timedelta(days=1)) == []      # 어제 json 은 안 올린다
    assert yt.plan_ent({"posted": []}, {**ENT_META, "youtube": {}}, NOW) == []
    assert all("silent" not in p["url"] and "-3" not in p["url"] for p in yt.plan_ent({"posted": []}, ENT_META, NOW, limit=9))


def test_연예_같은편_두번없음_하루상한은_기록으로():
    state = {"posted": [{"key": "ent:peopleroad-tv-20261030", "channel": "ent", "at": "2026-10-30T10:00:00+09:00"}]}
    plans = yt.plan_ent(state, ENT_META, NOW, limit=2)
    assert [p["key"] for p in plans] == ["ent:peopleroad-tv-20261030-1"]
    state["posted"].append({"key": "ent:peopleroad-tv-20261030-1", "channel": "ent", "at": "2026-10-30T11:00:00+09:00"})
    assert yt.plan_ent(state, ENT_META, NOW, limit=2) == []


def test_연예는_waffletrip_채널만():
    assert yt.handle_ok("@waffletrip", yt.ENT_HANDLE) and not yt.handle_ok("@peopleroad", yt.ENT_HANDLE)
    assert yt.ENT_CHANNEL_ID == "UCixhDwh_YbJqyB6SYiadRAA"


def test_연예_시크릿이_없으면_여행만_그대로(monkeypatch, tmp_path, capsys):
    for k in ("WAFFLETRIP_YT_CLIENT_ID", "WAFFLETRIP_YT_CLIENT_SECRET", "WAFFLETRIP_YT_REFRESH_TOKEN",
              "WAFFLETRIP_ENT_YT_CLIENT_ID", "WAFFLETRIP_ENT_YT_CLIENT_SECRET", "WAFFLETRIP_ENT_YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(yt, "POSTED", str(tmp_path / "posted.json"))
    monkeypatch.setattr(yt, "_fetch_json", lambda url: ENT_META if "peopleroad-tv-" in url else None)
    monkeypatch.setattr(yt, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: NOW),
                                                       "fromisoformat": staticmethod(datetime.fromisoformat)}))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    assert yt.main(["--post"]) == 0
    out = capsys.readouterr().out
    assert "WAFFLETRIP_ENT_YT_* 시크릿이 없어 건너뛴다" in out


def test_연예_토큰이_다른채널이면_안올림(monkeypatch, capsys):
    monkeypatch.setenv("WAFFLETRIP_ENT_YT_REFRESH_TOKEN", "r")
    monkeypatch.setenv("WAFFLETRIP_YT_CLIENT_ID", "c")
    monkeypatch.setenv("WAFFLETRIP_YT_CLIENT_SECRET", "s")
    monkeypatch.setattr(yt, "access_token", lambda *a: "t")
    monkeypatch.setattr(yt, "channel_handle", lambda tok, want_id=None: ("", "(다른 채널 UCkhVoG8C8OtKX60WpCpP99A)"))
    called = []
    monkeypatch.setattr(yt, "upload", lambda *a: called.append(1) or "x")
    yt.post_ent({"posted": []}, yt.plan_ent({"posted": []}, ENT_META, NOW))
    assert not called and "[중단]" in capsys.readouterr().out


def test_연예_채널목록을_못읽으면_안올림(monkeypatch, capsys):
    monkeypatch.setenv("WAFFLETRIP_ENT_YT_REFRESH_TOKEN", "r")
    monkeypatch.setenv("WAFFLETRIP_YT_CLIENT_ID", "c")
    monkeypatch.setenv("WAFFLETRIP_YT_CLIENT_SECRET", "s")
    monkeypatch.setattr(yt, "access_token", lambda *a: "t")
    monkeypatch.setattr(yt, "channel_handle", lambda tok, want_id=None: ("@waffletrip", "waffletrip"))
    monkeypatch.setattr(yt, "recent_titles", lambda tok, cid: None)
    called = []
    monkeypatch.setattr(yt, "upload", lambda *a: called.append(1) or "x")
    yt.post_ent({"posted": []}, yt.plan_ent({"posted": []}, ENT_META, NOW))
    assert not called and "중복을 확인할 수 없다" in capsys.readouterr().out
