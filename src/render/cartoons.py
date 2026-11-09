"""여행 카툰 그림을 지면에 싣는다. 사진이 아니라 AI 로 그린 그림이다.

사진 매니페스트(assets/photos/manifest.json)에 넣지 않는다 — 그 목록은 'NAS 에서 온 실사'만
받는다(tests/test_photos.py). 사진 자동 배정과 얼굴 검사를 타지 않고, 캡션에 '직접 촬영'이
붙지 않게 /img/cartoon/ 으로 따로 둔다.
"""
from __future__ import annotations

import glob
import os
import shutil

from src.photos import OG_SIZE


def copy_cartoons(out_dir: str, source: str = os.path.join("assets", "cartoon")) -> int:
    """assets/cartoon/*.webp → /img/cartoon/ + 공유 카드 /og/cartoon/*.jpg(제목이 보이게 위쪽 기준)."""
    from PIL import Image, ImageOps
    n = 0
    for path in sorted(glob.glob(os.path.join(source, "*.webp"))):
        name = os.path.splitext(os.path.basename(path))[0]
        img_dir, og_dir = os.path.join(out_dir, "img", "cartoon"), os.path.join(out_dir, "og", "cartoon")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(og_dir, exist_ok=True)
        shutil.copy2(path, os.path.join(img_dir, name + ".webp"))
        with Image.open(path) as im:
            ImageOps.fit(im.convert("RGB"), OG_SIZE, Image.LANCZOS, centering=(0.5, 0.0)).save(
                os.path.join(og_dir, name + ".jpg"), "JPEG", quality=82, optimize=True)
        n += 1
    return n
