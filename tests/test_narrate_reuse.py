"""같은 날 나레이션을 다시 사지 않는다 (2026-10-16 크레딧 소진)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import narrate  # noqa: E402


def _fake_site(monkeypatch, meta):
    files = {"x.json": json.dumps(meta).encode(), "x.mp4": b"MP4", "x.jpg": b"JPG"}
    monkeypatch.setattr(narrate, "_get",
                        lambda url, timeout=60: files.get(url.rsplit("/", 1)[1].replace(
                            url.rsplit("/", 1)[1].split(".")[0], "x", 1)))


def test_오늘_목소리판이_있으면_받아_쓴다(tmp_path, monkeypatch):
    _fake_site(monkeypatch, {"kind": "voiced", "built_at": "2026-10-16T12:40:00+09:00"})
    assert narrate.reuse_today("peopleroad-week", str(tmp_path), "2026-10-16")
    assert (tmp_path / "peopleroad-week.mp4").read_bytes() == b"MP4"
    assert json.loads((tmp_path / "peopleroad-week.json").read_text())["kind"] == "voiced"


def test_무음판이나_어제_것은_다시_쓰지_않는다(tmp_path, monkeypatch):
    _fake_site(monkeypatch, {"kind": "silent", "built_at": "2026-10-16T12:40:00+09:00"})
    assert not narrate.reuse_today("peopleroad-week", str(tmp_path), "2026-10-16")
    _fake_site(monkeypatch, {"kind": "voiced", "built_at": "2026-10-15T12:40:00+09:00"})
    assert not narrate.reuse_today("peopleroad-week", str(tmp_path), "2026-10-16")


def test_이름에_오늘_날짜가_있으면_오늘_것이다(tmp_path, monkeypatch):
    _fake_site(monkeypatch, {"kind": "voiced"})
    assert narrate.reuse_today("peopleroad-guam-20261016-voiced", str(tmp_path), "2026-10-16")
