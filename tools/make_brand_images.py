#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""제호 이미지를 만든다 — 로고(JSON-LD용 600×60), 기본 공유 카드(1200×630), 파비콘(SVG).

제호가 와플트립에서 피플로드로 바뀌었는데 이미지 세 개는 옛 이름이었다.
글자를 그림으로 박아 두면 이름이 바뀔 때마다 이렇게 어긋난다. 그래서 스크립트로
만들고, 이름과 문구는 src/brand.py 에서 읽는다.

    python3 tools/make_brand_images.py            # static/ 에 세 파일을 다시 만든다
    python3 tools/make_brand_images.py --out /tmp # 다른 곳에

글꼴은 있는 것 중 가장 좋은 것을 쓴다 — Pretendard(사이트 본문 글꼴) > 애플 SD 고딕(맥)
> Noto Sans CJK(CI, fonts-noto-cjk) > 문천역정흑(리눅스 기본). 한글이 없는 글꼴은 안 쓴다.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from src.brand import DOMAIN, SITE_KIND, SITE_NAME, SITE_NAME_EN, SITE_TAGLINE  # noqa: E402

INK = (14, 14, 15)
PAPER = (255, 255, 255)
CORAL = (240, 78, 55)
MUTED = (110, 110, 115)

_FONT_CANDIDATES = (
    "~/Library/Fonts/Pretendard-ExtraBold.otf", "~/Library/Fonts/Pretendard-Bold.otf",
    "/Library/Fonts/Pretendard-Bold.otf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def find_font() -> str | None:
    for pattern in _FONT_CANDIDATES:
        for path in glob.glob(os.path.expanduser(pattern)):
            try:
                ImageFont.truetype(path, 20, index=0)
                return path
            except OSError:
                continue
    return None


def font(path: str | None, size: int):
    if path:
        try:
            return ImageFont.truetype(path, size, index=0)
        except OSError:
            pass
    return ImageFont.load_default()


def _w(draw, text, f) -> int:
    return int(draw.textlength(text, font=f))


def make_logo(path: str, fpath: str | None) -> None:
    """600×60 투명 배경. 검은 제호 + 코랄 마침표. 구조화 데이터 publisher.logo."""
    im = Image.new("RGBA", (600, 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(fpath, 46)
    d.text((6, 2), SITE_NAME, font=f, fill=INK + (255,))
    x = 6 + _w(d, SITE_NAME, f) + 2
    d.ellipse((x, 40, x + 11, 51), fill=CORAL + (255,))
    small = font(fpath, 16)
    d.text((x + 24, 22), f"{SITE_NAME_EN} · {SITE_KIND}", font=small, fill=MUTED + (255,))
    im.save(path, "PNG", optimize=True)


def make_og(path: str, fpath: str | None) -> None:
    """1200×630 흰 카드. 링크를 카톡·페북에 보냈을 때 나오는 기본 그림."""
    im = Image.new("RGB", (1200, 630), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 1200, 10), fill=INK)                 # 신문 상단 굵은 선
    big = font(fpath, 124)
    d.text((80, 190), SITE_NAME, font=big, fill=INK)
    x = 80 + _w(d, SITE_NAME, big) + 6
    d.ellipse((x, 290, x + 26, 316), fill=CORAL)
    d.text((84, 350), SITE_TAGLINE, font=font(fpath, 44), fill=MUTED)
    d.line((80, 440, 1120, 440), fill=(234, 234, 231), width=2)
    d.text((84, 468), SITE_KIND, font=font(fpath, 30), fill=INK)
    d.text((84, 520), f"{SITE_NAME_EN} · {DOMAIN}", font=font(fpath, 26), fill=MUTED)
    d.rectangle((0, 620, 1200, 630), fill=CORAL)
    im.save(path, "JPEG", quality=90, optimize=True)


def make_favicon(path: str) -> None:
    """SVG 는 글꼴을 브라우저가 그린다. 첫 글자 '피' 와 코랄 점."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="12" fill="#0E0E0F"/>
  <text x="30" y="45" font-family="Pretendard,-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Noto Sans KR',sans-serif"
        font-size="38" font-weight="800" fill="#FFFFFF" text-anchor="middle">{SITE_NAME[0]}</text>
  <circle cx="52" cy="44" r="5" fill="#F04E37"/>
</svg>
"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "static"))
    args = ap.parse_args()
    fpath = find_font()
    if not fpath:
        print("한글 글꼴을 찾지 못했다. 그림에 네모만 찍히므로 만들지 않는다.", file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)
    make_logo(os.path.join(args.out, "logo.png"), fpath)
    make_og(os.path.join(args.out, "og-default.jpg"), fpath)
    make_favicon(os.path.join(args.out, "favicon.svg"))
    print(f"글꼴 {fpath}\n→ {args.out}/logo.png · og-default.jpg · favicon.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
