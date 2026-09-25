"""맥 편집실. 업로드는 검사에 걸리면 파일이 남지 않고, 저장은 커밋·푸시로 이어진다."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
import admin  # noqa: E402


def test_blocked_upload_leaves_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(admin, "UPLOADS", str(tmp_path / "uploads"))
    monkeypatch.setattr(admin, "inspect_upload", lambda p: (False, "얼굴 1건 검출"))
    web, err = admin.save_upload("me.jpg", b"jpg")
    assert web == "" and "얼굴 1건 검출" in err
    assert not os.listdir(tmp_path / "uploads")


def test_passing_upload_lands_in_uploads_with_web_path(tmp_path, monkeypatch):
    monkeypatch.setattr(admin, "UPLOADS", str(tmp_path / "uploads"))
    monkeypatch.setattr(admin, "inspect_upload", lambda p: (True, ""))
    web, err = admin.save_upload("../../evil name.jpg", b"jpg")
    assert err == "" and web.startswith("/content/uploads/") and web.endswith("_evilname.jpg")
    assert os.path.exists(tmp_path / "uploads" / web.rsplit("/", 1)[1])


def test_missing_detector_blocks_upload(tmp_path, monkeypatch):
    """검사기 없이 올리면 얼굴이 공개 저장소로 나갈 수 있다. 막는다."""
    monkeypatch.setattr(admin, "UPLOADS", str(tmp_path / "uploads"))
    monkeypatch.setattr(admin.sys, "path", [])           # photo_prepare 를 못 찾게
    import builtins
    real = builtins.__import__
    def fake(name, *a, **k):
        if name == "photo_prepare":
            raise ImportError("cv2")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    web, err = admin.save_upload("a.jpg", b"jpg")
    assert web == "" and "검사기" in err


def test_save_runs_git_add_commit_push(monkeypatch):
    calls = []
    class R:
        def __init__(self, rc=0): self.returncode = rc; self.stdout = ""; self.stderr = ""
    def fake_run(cmd, **kw):
        calls.append(cmd[1:])
        if cmd[1:3] == ["diff", "--cached"]:
            return R(1)                                  # 바뀐 것이 있다
        return R(0)
    monkeypatch.setattr(admin.subprocess, "run", fake_run)
    monkeypatch.setattr(admin, "PUSH", True)
    assert admin.commit_and_push("편집실: 제목") == ""
    ops = [c[0] for c in calls]
    assert ops[:3] == ["add", "diff", "commit"] and "push" in ops


def test_push_failure_is_reported_not_swallowed(monkeypatch):
    class R:
        def __init__(self, rc, err=""): self.returncode = rc; self.stdout = ""; self.stderr = err
    def fake_run(cmd, **kw):
        if cmd[1:3] == ["diff", "--cached"]:
            return R(1)
        if cmd[1] == "push":
            return R(1, "rejected")
        return R(0)
    monkeypatch.setattr(admin.subprocess, "run", fake_run)
    monkeypatch.setattr(admin, "PUSH", True)
    msg = admin.commit_and_push("m")
    assert "푸시 실패" in msg and "rejected" in msg


def test_multipart_parser_separates_fields_and_files():
    boundary = "XYZ"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"title\"\r\n\r\n제목\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo_file\"; filename=\"a.jpg\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\nBINARY\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo_file2\"; filename=\"\"\r\n\r\n\r\n"
            f"--{boundary}--\r\n").encode("utf-8")
    fields, files = admin.parse_multipart(body, f'multipart/form-data; boundary={boundary}')
    assert fields == {"title": "제목"}
    assert files == {"photo_file": ("a.jpg", b"BINARY")}      # 빈 파일칸은 무시
