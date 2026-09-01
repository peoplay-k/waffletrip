#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NAS 사진을 폴더별로 훑어 인덱스를 만든다.

NAS(`/Volumes/GUAMPLAY`, SMB)에는 사진이 26,716장 있고, 이 작업에는 이미
값비싸게 배운 함정이 둘 있다. 둘 다 여기서 구조로 막는다.

**함정 1 — SMB 전체 순회는 조용히 끊긴다.**
`find` 한 번으로 훑었더니 26,716장 중 243장만 나오고 exit 0 으로 끝났다.
stderr 를 버려서 눈치채지 못했다. 그래서 이 도구는
  ① 폴더를 하나씩 나눠 훑고
  ② 오류를 절대 버리지 않고 폴더별로 기록하며
  ③ 같은 폴더를 두 번 세어 수가 흔들리면 '불안정'으로 표시한다.
끊긴 것을 "사진이 없다"로 착각하지 않는 것이 이 도구의 존재 이유다.

**함정 2 — 0.7MB/s 다.**
원본 픽셀을 열면 못 끝낸다. 인덱싱 단계에서는 **파일을 열지 않는다.**
크기·수정시각은 디렉터리 항목에서 나오고, 촬영일은 EXIF 헤더 앞부분만 읽는다.

    python3 tools/nas_index.py                     기본 경로 훑기
    python3 tools/nas_index.py /Volumes/GUAMPLAY   경로 지정
    python3 tools/nas_index.py --shallow           1단계 폴더만 (연결 확인용)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DEFAULT_ROOT = "/Volumes/GUAMPLAY"
OUT = "data/photos/index.json"
EXTS = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")

# 폴더 이름에서 지역을 읽는다. **없으면 비워 둔다 — 추측하지 않는다.**
# 지역을 잘못 붙이면 하와이 기사에 괌 사진이 실리고 아무도 눈치채지 못한다.
REGION_HINTS = {
    "guam": ("괌", "guam", "GUAM"),
    "saipan": ("사이판", "saipan"),
    "hawaii": ("하와이", "hawaii", "오아후", "호놀룰루"),
    "vietnam": ("베트남", "vietnam", "다낭", "나트랑", "호치민", "하노이", "푸꾸옥", "호이안"),
    "kota": ("코타키나발루", "코타", "kota"),
    "laos": ("라오스", "laos", "비엔티안", "루앙프라방", "방비엥"),
    "jeju": ("제주", "jeju"),
}


def region_of(path: str) -> str:
    """경로에서 지역을 읽는다. 확실하지 않으면 빈 문자열."""
    lowered = path.lower()
    hits = {r for r, words in REGION_HINTS.items()
            if any(w.lower() in lowered for w in words)}
    return hits.pop() if len(hits) == 1 else ""   # 둘 이상이면 사람이 정한다


def shot_date(path: str) -> str:
    """EXIF 촬영일. 헤더 앞부분만 읽는다 — 원본 전체를 열면 NAS 에서 못 끝낸다."""
    try:
        with open(path, "rb") as f:
            head = f.read(65536)
    except OSError:
        return ""
    marker = b"\x00\x00DateTimeOriginal"
    for tag in (b"DateTimeOriginal", b"DateTime"):
        i = head.find(tag)
        if i < 0:
            continue
        window = head[i:i + 120]
        for j in range(len(window) - 19):
            chunk = window[j:j + 19]
            if (len(chunk) == 19 and chunk[4:5] == b":" and chunk[7:8] == b":"
                    and chunk[10:11] == b" "):
                try:
                    return chunk.decode("ascii").replace(":", "-", 2).replace(" ", "T")
                except UnicodeDecodeError:
                    return ""
    return ""


def walk_folders(root: str, shallow: bool = False):
    """폴더 목록을 먼저 만든다. 여기서 실패해도 통째로 죽지 않는다."""
    folders, errors = [root], []
    if shallow:
        try:
            with os.scandir(root) as it:
                folders += [e.path for e in it if e.is_dir(follow_symlinks=False)]
        except OSError as e:
            errors.append((root, f"{type(e).__name__}: {e}"))
        return folders, errors

    stack, seen = [root], set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            with os.scandir(current) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                        folders.append(entry.path)
        except OSError as e:
            # 버리지 않는다. 이게 함정 1 의 정체였다.
            errors.append((current, f"{type(e).__name__}: {e}"))
    return sorted(set(folders)), errors


def count_photos(folder: str):
    """(파일목록, 오류). 두 번 세어 수가 흔들리면 불안정으로 본다."""
    def once():
        out = []
        with os.scandir(folder) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False) and \
                        entry.name.lower().endswith(EXTS) and \
                        not entry.name.startswith("."):
                    out.append(entry)
        return out

    try:
        first = once()
        second = once()
    except OSError as e:
        return [], f"{type(e).__name__}: {e}"
    if len(first) != len(second):
        return first, f"불안정: 두 번 셌는데 {len(first)} vs {len(second)}"
    return first, ""


def build(root: str, shallow: bool = False, with_exif: bool = True) -> dict:
    if not os.path.isdir(root):
        print(f"경로를 열 수 없다: {root}", file=sys.stderr)
        print("NAS 가 마운트돼 있는지 확인하라 (Finder → 서버 연결 → smb://PEOPLAY).",
              file=sys.stderr)
        return {}

    folders, folder_errors = walk_folders(root, shallow)
    print(f"폴더 {len(folders)}개 발견. 하나씩 센다 "
          f"(전체 순회는 SMB 에서 조용히 끊긴다).")

    photos, per_folder, errors = [], [], list(folder_errors)
    for i, folder in enumerate(folders, 1):
        entries, err = count_photos(folder)
        if err:
            errors.append((folder, err))
        rel = os.path.relpath(folder, root)
        per_folder.append({"folder": rel, "count": len(entries), "error": err})
        if entries:
            print(f"  [{i}/{len(folders)}] {rel[:60]} — {len(entries)}장"
                  + (f"  ⚠ {err}" if err else ""))
        for entry in entries:
            try:
                stat = entry.stat()
            except OSError as e:
                errors.append((entry.path, f"{type(e).__name__}: {e}"))
                continue
            photos.append({
                "path": entry.path,
                "rel": os.path.relpath(entry.path, root),
                "bytes": stat.st_size,
                "mtime": datetime.fromtimestamp(stat.st_mtime, KST).isoformat(
                    timespec="seconds"),
                "region": region_of(entry.path),
                "shot": shot_date(entry.path) if with_exif else "",
            })

    return {
        "root": root,
        "indexed_at": datetime.now(KST).isoformat(timespec="seconds"),
        "total": len(photos),
        "folders": per_folder,
        "errors": [{"path": p, "error": e} for p, e in errors],
        "photos": photos,
    }


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    root = args[0] if args else DEFAULT_ROOT
    index = build(root, shallow="--shallow" in argv,
                  with_exif="--no-exif" not in argv)
    if not index:
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    by_region: dict[str, int] = {}
    for p in index["photos"]:
        by_region[p["region"] or "(미분류)"] = by_region.get(p["region"] or "(미분류)", 0) + 1

    print(f"\n사진 {index['total']}장 → {OUT}")
    print("지역별:")
    for region, n in sorted(by_region.items(), key=lambda x: -x[1]):
        print(f"  {region:12} {n:6}장")

    if index["errors"]:
        print(f"\n⚠ 오류 {len(index['errors'])}건 — 이걸 '사진 없음'으로 읽지 마라:",
              file=sys.stderr)
        for e in index["errors"][:10]:
            print(f"    {e['path']}: {e['error']}", file=sys.stderr)
    empty = [f for f in index["folders"] if f["count"] == 0 and not f["error"]]
    if empty:
        print(f"\n빈 폴더 {len(empty)}개 (정상일 수 있으나 눈으로 확인할 것)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
