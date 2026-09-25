"""편집실 업로드 사진 반입. 사람이 시트를 볼 수 없으니 검출기가 최종이고, 막는 쪽으로 튄다."""
from __future__ import annotations

import json
import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
import photo_intake  # noqa: E402


class FakePrep:
    """가짜 검사기. 파일 이름에 'face' 가 있으면 막는다."""
    def inspect(self, path):
        if "face" in os.path.basename(path):
            return {"ok": False, "reason": "얼굴 2건 검출", "faces": 2, "person": 0.0}
        return {"ok": True, "reason": "", "faces": 0, "person": 0.0}

    def bake(self, src, out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"webp")
        return 4, 0


def _setup(tmp_path, monkeypatch, name="pic.jpg", **front):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "content/uploads").mkdir(parents=True)
    (tmp_path / "content/review").mkdir(parents=True)
    (tmp_path / "content/uploads" / name).write_bytes(b"jpg")
    base = {"id": "art-guam-1", "channel": "travel", "region": "guam", "title": "제목",
            "photo": f"/content/uploads/{name}", "status": "approved"}
    base.update(front)
    path = tmp_path / "content/review/20260925_x.md"
    path.write_text("---\n" + yaml.safe_dump(base, allow_unicode=True, sort_keys=False)
                    + "---\n본문\n", encoding="utf-8")
    monkeypatch.setattr(photo_intake, "_inspector", lambda: FakePrep())
    monkeypatch.setattr(photo_intake, "_remove_upload",
                        lambda p: os.path.exists(p) and os.remove(p))
    return path


def _front(path):
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


def test_passing_photo_is_baked_registered_and_upload_removed(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)
    records = photo_intake.run("content/review")
    assert records and records[0]["ok"]
    front = _front(path)
    assert front["photo"] == "/img/guam/up_pic.webp"
    assert front["photo_note"] == "통과"
    assert (tmp_path / "assets/photos/guam/up_pic.webp").exists()
    manifest = json.loads((tmp_path / "assets/photos/manifest.json").read_text(encoding="utf-8"))
    entry = manifest["guam"][0]
    assert entry["origin"] == "편집실 업로드" and entry["file"] == "assets/photos/guam/up_pic.webp"
    used = json.loads((tmp_path / "data/photos/used.json").read_text(encoding="utf-8"))
    assert used["/img/guam/up_pic.webp"] == "art-guam-1"
    assert not (tmp_path / "content/uploads/pic.jpg").exists()
    assert (tmp_path / "data/photo_intake.json").exists()


def test_blocked_photo_is_dropped_and_upload_removed(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, name="face.jpg")
    records = photo_intake.run("content/review")
    assert records and not records[0]["ok"]
    front = _front(path)
    assert front["photo"] == ""
    assert "얼굴 2건 검출" in front["photo_note"] and "싣지 않았다" in front["photo_note"]
    assert not (tmp_path / "assets/photos/guam/up_face.webp").exists()
    assert not (tmp_path / "content/uploads/face.jpg").exists()


def test_missing_upload_file_is_noted(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)
    (tmp_path / "content/uploads/pic.jpg").unlink()
    photo_intake.run("content/review")
    front = _front(path)
    assert front["photo"] == "" and "찾지 못했다" in front["photo_note"]


def test_ent_photo_goes_to_the_ent_bucket(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, channel="ent", region="", category="movie",
                  id="art-ent-movie-1")
    photo_intake.run("content/review")
    assert _front(path)["photo"] == "/img/ent/up_pic.webp"
    manifest = json.loads((tmp_path / "assets/photos/manifest.json").read_text(encoding="utf-8"))
    assert "ent" in manifest and "guam" not in manifest


def test_hero_flag_reaches_the_manifest(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, photo_hero=True)
    photo_intake.run("content/review")
    manifest = json.loads((tmp_path / "assets/photos/manifest.json").read_text(encoding="utf-8"))
    assert manifest["guam"][0]["hero"] is True


def test_without_a_detector_nothing_passes(tmp_path, monkeypatch):
    """cv2 가 없으면 사람 얼굴이 검사 없이 공개될 수 있다. 막는 쪽으로 튄다."""
    path = _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(photo_intake, "_inspector", lambda: None)
    photo_intake.run("content/review")
    assert _front(path)["photo"] == ""


def test_drafts_without_uploads_are_untouched(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch, photo="/img/guam/already.webp")
    (tmp_path / "content/uploads/pic.jpg").unlink()        # 고아 파일 없이
    before = path.read_text(encoding="utf-8")
    assert photo_intake.run("content/review") == []
    assert path.read_text(encoding="utf-8") == before


def test_orphan_uploads_are_removed(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, photo="")
    (tmp_path / "content/uploads/stray.jpg").write_bytes(b"x")
    records = photo_intake.run("content/review")
    assert not (tmp_path / "content/uploads/stray.jpg").exists()
    assert any("초안이 가리키지 않는" in r.get("reason", "") for r in records)


def test_dry_run_changes_nothing(tmp_path, monkeypatch):
    path = _setup(tmp_path, monkeypatch)
    before = path.read_text(encoding="utf-8")
    photo_intake.run("content/review", dry=True)
    assert path.read_text(encoding="utf-8") == before
    assert (tmp_path / "content/uploads/pic.jpg").exists()


def test_ent_photo_pool_is_not_used_for_regional_assignment():
    """ent 매니페스트 키는 지역이 아니라 자동 배정 대상이 아니어야 한다."""
    from src.photos import photos_for
    manifest = {"ent": [{"file": "assets/photos/ent/up_a.webp"}]}
    assert photos_for(manifest, "guam") == []
