"""구운 사진을 사이트에 붙인다.

`assets/photos/manifest.json` 은 `tools/photo_prepare.py` 가 쓴다. 그 도구를
거치지 않은 사진은 여기 없고, 따라서 사이트에 나가지 않는다. **사람 승인을
통과한 것만 매니페스트에 들어간다**는 것이 이 파이프라인의 유일한 안전장치다.

매니페스트가 없어도 빌드는 돈다. 사진은 있으면 좋은 것이지 없으면 안 되는
것이 아니다 — 신문이 사진 때문에 안 나가면 안 된다.
"""
from __future__ import annotations

import json
import os
import shutil

MANIFEST = "assets/photos/manifest.json"
PUBLIC_DIR = "img"          # public/ 아래 경로


def load_manifest(path: str = MANIFEST) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def web_path(baked_file: str) -> str:
    """assets/photos/guam/x.webp → /img/guam/x.webp"""
    rel = baked_file.replace("assets/photos/", "", 1).lstrip("/")
    return f"/{PUBLIC_DIR}/{rel}"


def photos_for(manifest: dict, region: str) -> list[str]:
    entries = manifest.get(region) or []
    return [web_path(e["file"]) for e in entries
            if isinstance(e, dict) and e.get("file")]


def pick(manifest: dict, region: str, seed: str) -> str:
    """지역 사진 하나를 고른다. 같은 기사는 항상 같은 사진을 받는다.

    난수를 쓰지 않는 이유 — 빌드할 때마다 사진이 바뀌면 캐시가 무의미해지고,
    무엇보다 '어제 본 기사'가 오늘 달라 보인다.
    """
    pool = photos_for(manifest, region)
    if not pool:
        return ""
    return pool[sum(ord(c) for c in seed) % len(pool)]


def copy_into(out_dir: str, source_root: str = "assets/photos") -> int:
    """구운 사진을 public/img 로 옮긴다. 매니페스트에 있는 것만 옮긴다."""
    manifest = load_manifest()
    if not manifest:
        return 0
    copied = 0
    for entries in manifest.values():
        for entry in entries:
            src = entry.get("file") if isinstance(entry, dict) else None
            if not src or not os.path.exists(src):
                continue
            dest = os.path.join(out_dir, web_path(src).lstrip("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
    return copied
