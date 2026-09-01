#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""사진을 검사하고 웹용으로 굽는다. 사람이 잡히면 내보내지 않는다.

**저장소가 공개다.** 여기를 통과한 사진은 되돌릴 수 없이 공개된다. 그래서
기본값이 "내보낸다"가 아니라 "막는다"이다.

세 번 데인 자리를 그대로 반영했다.

 1. **EXIF 회전을 먼저 적용한다.** 사진이 90도 눕혀 저장돼 있으면 검출기가
    얼굴을 0점 준다 (오사카 도톤보리 사고).
 2. **그래도 못 믿어서 4방향으로 돌려가며 본다.**
 3. **축소 썸네일로 판단하지 않는다.** 검사 해상도를 충분히 크게 잡는다.

그리고 자동 검출은 오탐·미탐이 다 있다. 그래서 **콘택트시트를 항상 남긴다.**
최종 판단은 사람이 한다 — 이 도구는 사람이 볼 것을 줄여줄 뿐이다.

    python3 tools/photo_prepare.py --region guam --from ~/사진폴더
    python3 tools/photo_prepare.py --region guam --from ... --limit 20
    python3 tools/photo_prepare.py --region guam --from ... --commit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

KST = timezone(timedelta(hours=9))
OUT_ROOT = "assets/photos"
SHEET_ROOT = "data/photos/sheets"
MANIFEST = "assets/photos/manifest.json"

MAX_WIDTH = 1600          # 기사 본문 폭의 2배. 이보다 크면 공개 저장소만 무거워진다
WEBP_QUALITY = 80
SCAN_LONGEST = 1400       # 검사 해상도. 작게 잡으면 작은 얼굴을 놓친다
PERSON_AREA_LIMIT = 0.04  # 화면의 4% 이상을 사람이 차지하면 애초에 쓰지 않는다

# 검출을 **막는 쪽으로** 기울인다. 오탐이 나면 사람이 한 장 살리면 되지만,
# 미탐은 고객 얼굴이 공개 저장소로 나가는 것이라 되돌릴 수 없다.
# 실측에서 확인한 것 — 거의 같은 사진의 밝기 보정본끼리 판정이 갈렸다.
# 그래서 minNeighbors 를 낮추고 scaleFactor 를 두 번 훑는다.
# 민감도를 올려봤더니 로브스터 사진에서 "얼굴 68건"이 나왔다. 87%를 막으면
# 사람이 어차피 전부 다시 봐야 해서 도구가 무의미해진다. 그래서 검출기는
# **게이트가 아니라 표식**이다. 진짜 안전장치는 아래의 사람 승인 단계다.
_NEIGHBORS = 5
_MIN_FACE = (32, 32)

_FACE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_PROFILE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_profileface.xml")
_HOG = cv2.HOGDescriptor()
_HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


def load_upright(path: str, longest: int):
    """EXIF 회전을 적용해 세운 뒤 축소한다. 회전을 빼먹으면 검출이 무너진다."""
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    im = im.convert("RGB")
    if max(im.size) > longest:
        scale = longest / max(im.size)
        im = im.resize((int(im.width * scale), int(im.height * scale)),
                       Image.LANCZOS)
    return im


def _faces(bgr) -> int:
    gray = cv2.equalizeHist(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY))
    n = 0
    for cascade in (_FACE, _PROFILE):
        n += len(cascade.detectMultiScale(
            gray, 1.1, _NEIGHBORS, minSize=_MIN_FACE))
    return n


def _person_area(bgr) -> float:
    rects, _ = _HOG.detectMultiScale(bgr, winStride=(8, 8), padding=(8, 8),
                                     scale=1.06)
    if len(rects) == 0:
        return 0.0
    total = bgr.shape[0] * bgr.shape[1]
    return max(w * h for _, _, w, h in rects) / total


def inspect(path: str) -> dict:
    """(통과여부, 사유). 네 방향 중 한 번이라도 얼굴이 잡히면 막는다."""
    try:
        im = load_upright(path, SCAN_LONGEST)
    except Exception as e:
        return {"ok": False, "reason": f"열 수 없음 {type(e).__name__}", "faces": 0,
                "person": 0.0}

    base = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    faces = 0
    for k in range(4):                       # 0·90·180·270도
        rotated = base if k == 0 else np.ascontiguousarray(np.rot90(base, k))
        faces += _faces(rotated)
    person = _person_area(base)

    if faces:
        return {"ok": False, "reason": f"얼굴 {faces}건 검출", "faces": faces,
                "person": person}
    if person >= PERSON_AREA_LIMIT:
        return {"ok": False,
                "reason": f"사람이 화면의 {person*100:.0f}% 를 차지",
                "faces": 0, "person": person}
    return {"ok": True, "reason": "", "faces": 0, "person": person}


def bake(path: str, out_path: str) -> int:
    im = load_upright(path, MAX_WIDTH)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path, "WEBP", quality=WEBP_QUALITY, method=6)
    return os.path.getsize(out_path)


def _font(size: int):
    for path in ("/System/Library/Fonts/AppleSDGothicNeo.ttc",   # 한글
                 "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
                 "/System/Library/Fonts/Supplemental/Arial Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheet(items: list[dict], out_png: str, cols: int = 5, cell: int = 340):
    """번호를 찍어 한 장에 모은다. **이 시트가 이 도구의 주된 산출물이다.**

    번호가 있어야 사람이 --approve 로 고를 수 있다. 테두리 색은 검출기의
    의견일 뿐이고, 무엇을 실을지는 이 시트를 본 사람이 정한다.
    """
    if not items:
        return ""
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), (18, 18, 20))
    draw = ImageDraw.Draw(sheet)
    font = _font(int(cell * 0.09))
    small = _font(int(cell * 0.055))

    for i, it in enumerate(items):
        x, y = (i % cols) * cell, (i // cols) * cell
        try:
            thumb = ImageOps.fit(load_upright(it["src"], cell),
                                 (cell - 8, cell - 8), Image.LANCZOS)
        except Exception:
            thumb = Image.new("RGB", (cell - 8, cell - 8), (40, 40, 44))
        color = (60, 160, 100) if it["ok"] else (190, 60, 50)
        framed = Image.new("RGB", (cell, cell), color)
        framed.paste(thumb, (4, 4))
        sheet.paste(framed, (x, y))

        label = str(i + 1)
        draw.rectangle([x + 8, y + 8, x + 8 + int(cell * 0.22),
                        y + 8 + int(cell * 0.14)], fill=(0, 0, 0))
        draw.text((x + 16, y + 12), label, fill=(255, 255, 255), font=font)
        if it["reason"]:
            draw.rectangle([x + 4, y + cell - int(cell * 0.11),
                            x + cell - 4, y + cell - 4], fill=(0, 0, 0, 200))
            draw.text((x + 12, y + cell - int(cell * 0.10)),
                      it["reason"][:26], fill=(255, 190, 180), font=small)

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    sheet.save(out_png, "PNG")
    return out_png


def parse_approve(spec: str, total: int) -> list[int]:
    """"1,4,7-9" → [1,4,7,8,9]. 범위를 벗어난 번호는 버린다."""
    picked: list[int] = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                picked += list(range(int(a), int(b) + 1))
            except ValueError:
                continue
        else:
            try:
                picked.append(int(part))
            except ValueError:
                continue
    return sorted({i for i in picked if 1 <= i <= total})


def _stem(path: str) -> str:
    """밝기 보정본(_hi)·연번 접미사를 떼어 같은 장면끼리 묶는다."""
    name = os.path.splitext(os.path.basename(path))[0]
    return name[:-3] if name.endswith("_hi") else name


def propagate_blocks(results: list[dict]) -> int:
    """한 장면의 변형 중 하나라도 걸리면 그 장면을 통째로 막는다.

    실측에서 나온 것 — 거의 같은 로비 사진 두 장 중 하나는 '얼굴 2건'으로
    막히고 다른 하나는 통과했다. 통과한 쪽에도 사람이 서 있었다.
    검출기가 흔들리는 만큼, **한 번이라도 걸린 장면은 전부 막는 쪽**으로 간다.
    """
    groups: dict[str, list[dict]] = {}
    for v in results:
        groups.setdefault(_stem(v["src"]), []).append(v)

    spread = 0
    for stem, group in groups.items():
        if len(group) < 2 or all(v["ok"] for v in group):
            continue
        culprit = next(v for v in group if not v["ok"])
        for v in group:
            if v["ok"]:
                v["ok"] = False
                v["reason"] = f"같은 장면({stem})이 걸림 — {culprit['reason']}"
                spread += 1
    return spread


def warn_near_duplicates(results: list[dict]) -> None:
    """파일명이 거의 같은데 판정이 갈린 쌍을 알린다.

    같은 장면의 보정본끼리 통과·차단이 갈리면 그건 장면의 문제가 아니라
    **검출기가 흔들린다는 신호**다. 통과 쪽을 믿으면 안 된다.
    """
    def stem(path):
        name = os.path.splitext(os.path.basename(path))[0]
        return name[:-3] if name.endswith("_hi") else name

    groups: dict[str, list[dict]] = {}
    for v in results:
        groups.setdefault(stem(v["src"]), []).append(v)
    split = [k for k, g in groups.items()
             if len(g) > 1 and len({v["ok"] for v in g}) > 1]
    if split:
        print(f"\n⚠ 같은 장면인데 판정이 갈린 것 {len(split)}건: "
              f"{', '.join(split[:6])}", file=sys.stderr)
        print("   검출기가 흔들린다는 뜻이다. 해당 컷은 확대해서 직접 볼 것.",
              file=sys.stderr)


def gather(source: str, limit: int) -> list[str]:
    exts = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")
    found = []
    for root, _, files in os.walk(source):
        for name in sorted(files):
            if name.lower().endswith(exts) and not name.startswith("."):
                found.append(os.path.join(root, name))
    return found[:limit] if limit else found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--from", dest="source", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--approve", default="",
                    help="콘택트시트를 눈으로 본 뒤 구울 번호. 예: 1,4,7-9")
    ap.add_argument("--hero", action="store_true",
                    help="1면에 쓸 풍경 사진으로 표시한다.")
    ap.add_argument("--commit", action="store_true",
                    help="--approve 로 고른 것만 굽는다.")
    args = ap.parse_args()

    from src.models import REGIONS
    if args.region not in REGIONS:
        print(f"모르는 지역: {args.region}. 가능한 값 {REGIONS}", file=sys.stderr)
        return 1

    paths = gather(os.path.expanduser(args.source), args.limit)
    if not paths:
        print(f"사진이 없다: {args.source}", file=sys.stderr)
        return 1
    print(f"{len(paths)}장 검사 (EXIF 회전 + 4방향)\n")

    results, passed, blocked, total_bytes = [], [], [], 0
    for i, src in enumerate(paths, 1):
        verdict = inspect(src)
        verdict["src"] = src
        results.append(verdict)
        mark = "통과" if verdict["ok"] else "차단"
        print(f"  [{i}/{len(paths)}] {mark}  {os.path.basename(src)[:44]}"
              + (f"  — {verdict['reason']}" if verdict["reason"] else ""))
        (passed if verdict["ok"] else blocked).append(verdict)

    spread = propagate_blocks(results)
    if spread:
        print(f"\n같은 장면 전파로 {spread}장 추가 차단 "
              f"(변형 하나가 걸리면 그 장면은 전부 막는다).")
    passed = [v for v in results if v["ok"]]
    blocked = [v for v in results if not v["ok"]]

    day = datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    sheet = contact_sheet(results, os.path.join(
        SHEET_ROOT, f"{args.region}_{day}.png"))

    approved_ix = parse_approve(args.approve, len(results))
    # 검출기가 통과시켰다고 굽지 않는다. **사람이 고른 것만 굽는다.**
    # 실측에서 거의 같은 사진의 보정본끼리 판정이 갈렸다 — 통과는 신뢰할 수 없다.
    to_bake = [results[i - 1] for i in approved_ix]

    # 검출기에 거부권을 주지 않는다. 실측이 그렇게 하라고 말한다 —
    # 66장 중 62장을 막았고 그 안에 로브스터 접시가 있었다. 거부권을 주면
    # 사람이 승인해도 아무것도 못 굽는다. 반대로 검출기의 '통과'도 믿을 수
    # 없다(사람이 서 있는 로비를 통과시켰다).
    #
    # 그래서 **사람 승인이 최종이고, 재정의한 사실을 기록에 남긴다.**
    # 실수로 넘어가지 않도록 무엇을 왜 재정의하는지 크게 찍는다.
    overridden = [v for v in to_bake if not v["ok"]]
    if overridden:
        print(f"\n검출기 판정을 재정의한다 — {len(overridden)}장", file=sys.stderr)
        for v in overridden:
            print(f"    {os.path.basename(v['src'])} — {v['reason']}", file=sys.stderr)
        print("    승인한 사람이 시트를 봤다고 보고 굽는다. 매니페스트에 남긴다.",
              file=sys.stderr)

    if args.commit and to_bake:
        manifest = {}
        if os.path.exists(MANIFEST):
            with open(MANIFEST, encoding="utf-8") as f:
                manifest = json.load(f)
        entries = manifest.setdefault(args.region, [])
        known = {e["src"] for e in entries}
        for verdict in to_bake:
            src = verdict["src"]
            if src in known:
                continue
            name = os.path.splitext(os.path.basename(src))[0]
            safe = "".join(c for c in name if c.isalnum() or c in "-_")[:48] or "photo"
            out_path = os.path.join(OUT_ROOT, args.region, f"{safe}.webp")
            size = bake(src, out_path)
            total_bytes += size
            entry = {"src": src, "file": out_path, "bytes": size,
                     "baked_at": datetime.now(KST).isoformat(timespec="seconds")}
            if args.hero:
                entry["hero"] = True
            if not verdict["ok"]:
                # 나중에 문제가 생기면 무엇을 재정의했는지 되짚을 수 있어야 한다.
                entry["overrode"] = verdict["reason"]
            entries.append(entry)
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n통과 {len(passed)} · 차단 {len(blocked)}")
    warn_near_duplicates(results)
    if sheet:
        print(f"콘택트시트: {sheet}")
        print("  ★ 시트를 열어 눈으로 확인하고, 쓸 번호를 --approve 로 넘겨라.")
        print("    자동 통과만으로는 굽지 않는다. 검출기는 보조 수단이다.")
    if args.commit and not approved_ix:
        print("\n--approve 로 고른 번호가 없어 아무것도 굽지 않았다.", file=sys.stderr)
    if args.commit and approved_ix:
        print(f"구운 용량: {total_bytes/1024/1024:.1f}MB → {OUT_ROOT}/{args.region}/")
        print("  저장소가 공개다. 올린 사진은 되돌릴 수 없이 공개된다.")
    else:
        print("검사만 했다. 실제로 구우려면 --commit 을 붙여라.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    raise SystemExit(main())
