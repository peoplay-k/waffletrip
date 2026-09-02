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


def hero_photos(manifest: dict, region: str) -> list[str]:
    """풍경으로 표시된 사진만."""
    return [web_path(e["file"]) for e in (manifest.get(region) or [])
            if isinstance(e, dict) and e.get("file") and e.get("hero")]


def photos_for(manifest: dict, region: str) -> list[str]:
    """지역의 사진 목록. **풍경(hero)이 앞에 온다.**

    1면 사진은 그 매체의 인상을 결정한다. 해시로만 고르면 양념치킨
    클로즈업이 톱기사에 걸린다 — 실제로 그랬다. 풍경으로 표시된 사진을
    먼저 쓰고, 모자라면 나머지로 채운다.
    """
    entries = [e for e in (manifest.get(region) or [])
               if isinstance(e, dict) and e.get("file")]
    heroes = [e for e in entries if e.get("hero")]
    rest = [e for e in entries if not e.get("hero")]
    return [web_path(e["file"]) for e in heroes + rest]


def assign(manifest: dict, region: str, seeds: list[str]) -> dict:
    """한 지역면의 기사들에 사진을 겹치지 않게 배정한다.

    pick() 만 쓰면 해시가 충돌해 같은 사진이 한 화면에 두 번 나온다.
    실제로 톱기사와 카드에 같은 스테이크 접시가 걸렸다.

    기사 고유의 자리(pick)를 먼저 잡고, 이미 쓰인 사진이면 다음 것으로 밀어
    비어 있는 자리를 찾는다. 같은 입력이면 결과가 같다 — 빌드마다 사진이
    바뀌면 어제 본 기사가 오늘 달라 보인다.
    """
    pool = photos_for(manifest, region)
    if not pool:
        return {}
    used: set[str] = set()
    out: dict[str, str] = {}
    # 첫 화면(톱 + 사이드 둘)은 풍경 사진으로 채운다. 거기에 음식 클로즈업이
    # 걸리면 여행신문으로 안 보인다. 나머지는 해시로 흩는다.
    heroes = hero_photos(manifest, region)
    lead_count = min(3, len(heroes), len(seeds))
    for i in range(lead_count):
        out[seeds[i]] = heroes[i]
        used.add(heroes[i])
    for seed in seeds[lead_count:]:
        start = sum(ord(c) for c in seed) % len(pool)
        for step in range(len(pool)):
            candidate = pool[(start + step) % len(pool)]
            if candidate not in used:
                used.add(candidate)
                out[seed] = candidate
                break
        else:
            out[seed] = pool[start]      # 사진보다 기사가 많으면 돌려 쓴다
    return out


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
