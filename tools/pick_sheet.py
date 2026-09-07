#!/usr/bin/env python3
"""고르기 좋은 콘택트시트를 만든다.

검출기는 오탐이 심하다. 실측에서 168장 중 8장만 통과시켰고, 막힌 것 안에
음식 접시와 빈 복도가 섞여 있었다. 그래서 **사람이 볼 것을 잘 추려서
한 장에 모으는 일**이 이 도구가 하는 전부다.

번호 순서는 고정이다(폴더·파일명 순). 사람이 "3, 7, 12-15" 처럼 번호를
불러 주면 그 번호로 굽는다.

    python3 tools/pick_sheet.py --verdicts japan_verdicts.json --out sheet.png
"""
from __future__ import annotations

import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

CELL = 300
COLS = 6
PAD = 6
LABEL = 26


def _font(size: int):
    for p in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build(rows: list[dict], out: str, note: str = "") -> str:
    n = len(rows)
    cols = COLS
    lines = (n + cols - 1) // cols
    W = cols * (CELL + PAD) + PAD
    H = lines * (CELL + PAD + LABEL) + PAD + 46
    sheet = Image.new("RGB", (W, H), (250, 250, 249))
    d = ImageDraw.Draw(sheet)
    d.text((PAD + 4, 12), note or f"{n}장 — 쓸 번호를 알려주세요",
           font=_font(24), fill=(14, 14, 15))

    small = _font(20)
    for i, row in enumerate(rows):
        try:
            im = Image.open(row["src"]).convert("RGB")
            im.thumbnail((CELL, CELL), Image.LANCZOS)
        except Exception:
            continue
        cx = PAD + (i % cols) * (CELL + PAD)
        cy = 46 + (i // cols) * (CELL + PAD + LABEL)
        box = Image.new("RGB", (CELL, CELL), (235, 235, 232))
        box.paste(im, ((CELL - im.width) // 2, (CELL - im.height) // 2))
        sheet.paste(box, (cx, cy))
        # 검출기 의견은 참고로만 적는다. 판단은 사람이 한다.
        faces = row.get("faces", 0)
        tag = "얼굴 없음" if row.get("ok") else f"얼굴 {faces}건"
        color = (47, 125, 91) if row.get("ok") else (154, 107, 0)
        d.text((cx + 2, cy + CELL + 3), f"{i + 1}. {tag}", font=small, fill=color)
    sheet.save(out, quality=88)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="고르기용 콘택트시트")
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-faces", type=int, default=2,
                    help="얼굴이 이 수 이하로 잡힌 것까지 시트에 넣는다")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    with open(args.verdicts, encoding="utf-8") as f:
        rows = json.load(f)
    # 통과한 것 먼저, 그 다음 얼굴이 적게 잡힌 것(오탐 의심) 순
    rows.sort(key=lambda r: (not r.get("ok"), r.get("faces", 99)))
    picked = [r for r in rows
              if r.get("ok") or r.get("faces", 99) <= args.max_faces][:args.limit]
    out = build(picked, args.out,
                f"{len(picked)}장 — 쓸 번호를 알려주세요 "
                f"(초록=얼굴 없음, 주황=얼굴 의심)")
    with open(args.out + ".json", "w", encoding="utf-8") as f:
        json.dump(picked, f, ensure_ascii=False)
    print(f"{out} ({len(picked)}장)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
