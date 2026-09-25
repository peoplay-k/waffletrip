#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""편집실에서 올린 사진을 검사해 지면용으로 굽는다. 사람이 잡히면 싣지 않는다.

2026-09-16 사장님 결정: 사진은 **웹 편집실에서도 올린다.** 원본이 공개 저장소 이력에
남는 것을 감수하고, 대신 CI 가 얼굴·사람을 검사해 지면에는 안 나가게 한다.
2026-09-25 "전부 손봐라"로 구현. 설계서 docs/superpowers/specs/2026-09-16-…-design.md §2.2.

파이프라인에서 **해설 발행(publish_drafts) 바로 앞**에 돈다. publish_drafts 가
프론트매터 `photo` 를 읽기 전에 웹 경로로 바꿔 놓아야 하기 때문이다.

기사(content/review/*.md) 단위로:
  1. `photo` 가 `/content/uploads/` 로 시작하는 초안을 찾는다.
  2. 파일이 없으면 photo 를 비우고 `photo_note` 에 적는다.
  3. photo_prepare.inspect() — EXIF 회전 + 4방향 얼굴 + 사람 면적. **검출기가 최종이다.**
     로컬 도구와 달리 여기엔 콘택트시트를 볼 사람이 없으므로 fail-closed.
     - 통과: bake() 로 assets/photos/<region|ent>/up_<stem>.webp (1600px, q80).
       매니페스트에 {src, file, bytes, baked_at, origin: "편집실 업로드", hero} 추가.
       프론트매터 photo 를 /img/... 로 바꾸고 used.json 에 기사 id 를 적어 다른 기사에
       자동 배정되지 않게 한다. photo_note: "통과".
     - 차단: photo 비움, photo_note: "<사유> — 지면에 싣지 않았다".
     두 경우 모두 content/uploads/ 의 원본을 지운다(git rm). 폴더는 늘 비어 있어야 한다.
  4. 연예 기사(channel: ent)는 region 이 없으므로 assets/photos/ent/ 에 굽는다.
     자동 배정 풀에는 들어가지 않는다(ent 는 지역면이 아니다).
  5. 결과를 data/photo_intake.json 에 누적한다.

`up_` 접두사는 표식이다. 검출기 통과를 100% 믿지 않으므로, 문제가 생기면 이 접두사로
한 번에 걷어낼 수 있게 한다. 캡션은 기존대로 "직접 촬영".

    python3 tools/photo_intake.py            # content/review 전체
    python3 tools/photo_intake.py --dry      # 무엇을 할지만 보여준다
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

KST = timezone(timedelta(hours=9))
UPLOAD_PREFIX = "/content/uploads/"
UPLOAD_DIR = "content/uploads"
OUT_ROOT = "assets/photos"
MANIFEST = "assets/photos/manifest.json"
USED = "data/photos/used.json"
LOG = "data/photo_intake.json"
ORIGIN = "편집실 업로드"
_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _split(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    return (yaml.safe_load(parts[1]) or {}), parts[2]


def _write_front(path: str, front: dict, body: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n")
        f.write(body.lstrip("\n"))


def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=isinstance(data, dict))


def _remove_upload(path: str) -> None:
    """원본을 지운다. git 이 추적 중이면 git rm 으로 — 다음 커밋이 삭제를 담는다."""
    if not os.path.exists(path):
        return
    try:
        subprocess.run(["git", "rm", "-q", "--cached", path], check=False,
                       capture_output=True)
    except Exception:
        pass
    try:
        os.remove(path)
    except OSError:
        pass


def _inspector():
    """검사기. cv2 가 없으면 None — 그때는 아무것도 통과시키지 않는다(fail-closed)."""
    try:
        import photo_prepare  # noqa: WPS433 — tools/ 의 로컬 도구를 그대로 쓴다
        return photo_prepare
    except Exception:
        return None


def target_bucket(front: dict) -> str:
    """사진이 들어갈 매니페스트 키. 연예는 ent, 여행은 지역."""
    if str(front.get("channel") or "travel") == "ent":
        return "ent"
    return str(front.get("region") or "").strip() or "etc"


def intake_one(path: str, front: dict, body: str, prep, manifest: dict,
               used: dict, dry: bool = False) -> dict | None:
    """초안 하나를 처리한다. 업로드 사진이 없으면 None."""
    photo = str(front.get("photo") or "")
    if not photo.startswith(UPLOAD_PREFIX):
        return None
    now = datetime.now(KST).isoformat(timespec="seconds")
    name = os.path.basename(photo)
    src = os.path.join(UPLOAD_DIR, name)
    record = {"draft": os.path.basename(path), "upload": photo, "at": now,
              "article": str(front.get("id") or "")}

    if not os.path.isfile(src):
        front["photo"] = ""
        front["photo_note"] = "업로드 파일을 찾지 못했다"
        record.update(ok=False, reason="파일 없음")
        if not dry:
            _write_front(path, front, body)
        return record

    if prep is None:
        verdict = {"ok": False, "reason": "검사기(cv2)를 쓸 수 없어 막았다"}
    else:
        verdict = prep.inspect(src)

    if verdict.get("ok"):
        bucket = _SAFE.sub("", target_bucket(front)) or "etc"
        stem = _SAFE.sub("", os.path.splitext(name)[0])[:40] or "photo"
        out = os.path.join(OUT_ROOT, bucket, f"up_{stem}.webp")
        web = f"/img/{bucket}/up_{stem}.webp"
        if not dry:
            size, _ = prep.bake(src, out)
            entry = {"src": photo, "file": out, "bytes": size, "baked_at": now,
                     "origin": ORIGIN, "hero": bool(front.get("photo_hero"))}
            rows = [e for e in (manifest.get(bucket) or [])
                    if not (isinstance(e, dict) and e.get("file") == out)]
            rows.append(entry)
            manifest[bucket] = rows
            if front.get("id"):
                used[web] = str(front["id"])      # 다른 기사에 자동 배정되지 않게
        front["photo"] = web
        front["photo_note"] = "통과"
        record.update(ok=True, reason="", photo=web)
    else:
        reason = verdict.get("reason") or "차단"
        front["photo"] = ""
        front["photo_note"] = f"{reason} — 지면에 싣지 않았다"
        record.update(ok=False, reason=reason)

    if not dry:
        _write_front(path, front, body)
        _remove_upload(src)          # 통과든 차단이든 원본은 지운다
    return record


def run(review_dir: str = "content/review", dry: bool = False) -> list[dict]:
    if not os.path.isdir(review_dir):
        return []
    prep = _inspector()
    manifest = _load_json(MANIFEST, {})
    used = _load_json(USED, {})
    if not isinstance(manifest, dict):
        manifest = {}
    if not isinstance(used, dict):
        used = {}
    records: list[dict] = []
    for name in sorted(os.listdir(review_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(review_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                front, body = _split(f.read())
        except Exception as e:
            print(f"  초안을 읽지 못했다: {name} — {type(e).__name__}: {e}", file=sys.stderr)
            continue
        rec = intake_one(path, front, body, prep, manifest, used, dry=dry)
        if rec:
            records.append(rec)
    if records and not dry:
        _save_json(MANIFEST, manifest)
        _save_json(USED, used)
        log = _load_json(LOG, [])
        if not isinstance(log, list):
            log = []
        log.extend(records)
        _save_json(LOG, log[-500:])
    # 남아 있는 고아 업로드(초안이 가리키지 않는 파일)도 지운다. 폴더는 비어 있어야 한다.
    if not dry and os.path.isdir(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            if f.startswith("."):
                continue
            _remove_upload(os.path.join(UPLOAD_DIR, f))
            records.append({"upload": f, "ok": False, "reason": "초안이 가리키지 않는 파일 — 지웠다",
                            "at": datetime.now(KST).isoformat(timespec="seconds")})
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--review", default="content/review")
    args = ap.parse_args()
    os.chdir(ROOT)
    records = run(args.review, dry=args.dry)
    if not records:
        print("반입할 업로드 사진이 없다.")
        return 0
    passed = sum(1 for r in records if r.get("ok"))
    print(f"사진 반입: 통과 {passed}건 · 차단 {len(records) - passed}건")
    for r in records:
        mark = "✓" if r.get("ok") else "✗"
        print(f"  {mark} {r.get('draft', r.get('upload'))} — {r.get('photo') or r.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
