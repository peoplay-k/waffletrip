#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유튜브·릴스 썸네일(표지)을 만든다 (2026-11-14 사장님: "썸네일이 다 별로야, 제대로 만들어").

그전까지 표지는 따로 없었다. 유튜브가 영상의 한 장면을 골랐고, 그 장면은
- 쇼츠: 사진 전체에 어두운 막을 깔고 가는 글씨로 "이번 주 / 괌 / 소식 4건" — 폰 목록에서
  흐린 회색 사진에 글자가 묻혔다.
- 주간 롱폼·오늘의 방송: 흰 바탕에 검은 가는 글씨 한 줄 — 무엇을 보는 영상인지 안 보였다.

목록에서 썸네일은 손톱만 하게 보인다(폭 160~360px). 그 크기에서 읽히게 만드는 규칙:
1. **글자는 크고 굵게, 3줄 이내.** 가장 굵은 한글 서체에 검은 테두리를 둘러 어떤 사진 위에서도 읽힌다.
2. **한 단어만 노랑.** 지명·숫자 같은 붙잡는 말 하나만 강조색으로, 나머지는 흰색.
3. **사진은 밝고 선명하게.** 화면 전체를 어둡게 덮지 않는다. 글자가 앉는 쪽에만 그라데이션.
4. **무엇에 대한 영상인지 한눈에.** 지역 딱지(칩)와 건수를 붙인다. 문장은 실제 기사 제목에서만 가져온다.
5. **제호는 늘 같은 자리.** 왼쪽 위 작은 딱지 — 어느 썸네일을 봐도 같은 매체다.

글자 내용은 지어내지 않는다. 지명·건수·기사 제목·방송 정보처럼 영상에 실제로 나오는 것만 쓴다.
"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

# 굵은 한글. NotoSansCJK-Bold.ttc 의 1번이 한국어(KR) 글리프다.
_BOLD = (
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc", 1),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 1),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 1),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 8),        # macOS ExtraBold
)

YELLOW = (255, 214, 0)
CORAL = (240, 78, 55)
WHITE = (255, 255, 255)
BLACK = (10, 10, 12)
NAVY = (14, 22, 38)


def font(size: int) -> ImageFont.FreeTypeFont:
    for path, idx in _BOLD:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size, index=idx)
            except OSError:
                continue
    raise RuntimeError("굵은 한글 폰트를 찾지 못했다 — sudo apt-get install -y fonts-noto-cjk")


# ── 사진 ──────────────────────────────────────────────────────────
def cover(path: str | None, size: tuple[int, int], top_bias: float = 0.4) -> Image.Image:
    """사진을 화면에 꽉 차게 자르고 색을 조금 살린다. 사진이 없으면 짙은 남색 바탕."""
    w, h = size
    if not path or not os.path.exists(path):
        return Image.new("RGB", size, NAVY)
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im = ImageOps.fit(im, size, Image.LANCZOS, centering=(0.5, top_bias))
    im = ImageEnhance.Color(im).enhance(1.25)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    return im


def shade(img: Image.Image, side: str = "bottom", start: float = 0.45, strength: int = 225) -> Image.Image:
    """글자가 앉는 쪽만 어둡게. 사진의 나머지는 밝게 둔다."""
    w, h = img.size
    n = h if side in ("bottom", "top") else w
    ramp = Image.new("L", (1, n) if side in ("bottom", "top") else (n, 1))
    for i in range(n):
        t = i / n
        if side in ("top", "left"):
            t = 1 - t
        a = 0 if t < start else int(strength * ((t - start) / (1 - start)) ** 1.3)
        ramp.putpixel((0, i) if side in ("bottom", "top") else (i, 0), a)
    mask = ramp.resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), BLACK), img, mask)


# ── 글자 ──────────────────────────────────────────────────────────
def wrap(d: ImageDraw.ImageDraw, text: str, f, max_w: int, max_lines: int) -> list[str]:
    """단어 단위로 줄을 나눈다. 넘치면 마지막 줄 끝을 '…' 로."""
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        nxt = f"{cur} {w}".strip()
        if d.textlength(nxt, font=f) <= max_w or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and d.textlength(last + "…", font=f) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def fit_lines(d, text: str, max_w: int, max_lines: int, sizes) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """가장 큰 글자 크기부터 줄여 가며, 말줄임 없이 들어가는 크기를 고른다."""
    for s in sizes:
        f = font(s)
        lines = wrap(d, text, f, max_w, max_lines)
        if not lines[-1].endswith("…"):
            return lines, f
    f = font(sizes[-1])
    return wrap(d, text, f, max_w, max_lines), f


def stroke_text(d, xy, text, f, fill=WHITE, stroke=None):
    sw = stroke if stroke is not None else max(4, f.size // 14)
    d.text(xy, text, font=f, fill=fill, stroke_width=sw, stroke_fill=BLACK)


def chip(d, xy, text, f, bg=CORAL, fg=WHITE, pad=(22, 10)) -> int:
    """둥근 딱지. 그린 폭을 돌려준다."""
    x, y = xy
    tw = d.textlength(text, font=f)
    box = (x, y, x + tw + pad[0] * 2, y + f.size + pad[1] * 2 + 4)
    d.rounded_rectangle(box, radius=(box[3] - box[1]) // 2, fill=bg)
    d.text((x + pad[0], y + pad[1] - f.size * 0.08), text, font=f, fill=fg)
    return int(box[2] - box[0])


def brand(d, xy, size: int, on_dark: bool = True):
    """왼쪽 위 제호 딱지 — '피플로드.' 흰 바탕 둥근 상자."""
    f = font(size)
    x, y = xy
    tw = d.textlength("피플로드.", font=f)
    d.rounded_rectangle((x, y, x + tw + size, y + size * 1.55), radius=int(size * 0.35),
                        fill=WHITE if on_dark else BLACK)
    d.text((x + size / 2, y + size * 0.18), "피플로드", font=f, fill=BLACK if on_dark else WHITE)
    d.text((x + size / 2 + d.textlength("피플로드", font=f), y + size * 0.18), ".", font=f, fill=CORAL)


def headline_block(d, x, y, lines, f, highlight: str = "", line_gap: float = 1.18):
    """여러 줄 제목. highlight 낱말이 들어 있는 첫 줄의 그 낱말만 노랑."""
    done = False
    for line in lines:
        if highlight and not done and highlight in line:
            pre, post = line.split(highlight, 1)
            cx = x
            for part, col in ((pre, WHITE), (highlight, YELLOW), (post, WHITE)):
                if part:
                    stroke_text(d, (cx, y), part, f, fill=col)
                    cx += d.textlength(part, font=f)
            done = True
        else:
            stroke_text(d, (x, y), line, f)
        y += int(f.size * line_gap)
    return y


# ── 여행 쇼츠 표지 (1080×1920) ───────────────────────────────────────
SHORT_W, SHORT_H = 1080, 1920
SHORT_SAFE_BOTTOM = 420      # 세 플랫폼 모두 아래를 UI 로 덮는다
SHORT_PAD = 72


def short_cover(name: str, count: int, hook: str = "", photo: str | None = None,
                seconds: int | None = None, period: str = "이번 주") -> Image.Image:
    """'괌 이번 주 소식 4건' + 대표 기사 제목. 사진은 위쪽을 밝게 살린다."""
    img = shade(cover(photo, (SHORT_W, SHORT_H), 0.35), "bottom", start=0.30, strength=235)
    d = ImageDraw.Draw(img)
    brand(d, (SHORT_PAD, 110), 40)

    # 아래에서부터 쌓는다 — 안전선 위에 글자 덩어리의 바닥을 맞춘다.
    bottom = SHORT_H - SHORT_SAFE_BOTTOM - 20
    hook_lines, hf = ([], None)
    if hook:
        hook_lines, hf = fit_lines(d, hook, SHORT_W - SHORT_PAD * 2, 3, (72, 66, 60, 56))
    hook_h = int(len(hook_lines) * (hf.size * 1.22)) if hf else 0

    name_f = font(210 if len(name) <= 3 else 170 if len(name) <= 5 else 130)
    sub_f = font(64)
    y = bottom - hook_h - (40 if hook_lines else 0)
    # '이번 주 소식 N건' 딱지
    y_chip = y - int(name_f.size * 1.32) - 80
    w = chip(d, (SHORT_PAD, y_chip), f"{period} 여행 소식", font(46))
    chip(d, (SHORT_PAD + w + 16, y_chip), f"{count}건", font(46), bg=YELLOW, fg=BLACK)
    # 지명 — 가장 크게, 노랑
    stroke_text(d, (SHORT_PAD, y_chip + 80), name, name_f, fill=YELLOW, stroke=10)
    y = y_chip + 80 + int(name_f.size * 1.32)
    if hook_lines:
        headline_block(d, SHORT_PAD, y, hook_lines, hf, line_gap=1.22)
    if seconds:
        d.text((SHORT_PAD, SHORT_H - SHORT_SAFE_BOTTOM + 70), f"{seconds}초 정리 · waffletrip.com",
               font=font(36), fill=(225, 228, 232))
    del sub_f
    return img


# ── 여행 주간 롱폼 썸네일 (가로) ─────────────────────────────────────
def long_thumb(regions: list[str], count: int, photos: list[str], size=(1280, 720),
               title: str = "이번 주 여행 뉴스") -> Image.Image:
    """왼쪽엔 큰 제목, 오른쪽엔 사진 두 장. 지역 이름을 딱지로 줄 세운다."""
    w, h = size
    s = w / 1280
    img = Image.new("RGB", size, NAVY)
    # 오른쪽 사진 두 장(위·아래)
    px = int(w * 0.50)
    pics = [p for p in photos if p and os.path.exists(p)][:2]
    if pics:
        if len(pics) == 1:
            img.paste(cover(pics[0], (w - px, h)), (px, 0))
        else:
            img.paste(cover(pics[0], (w - px, h // 2)), (px, 0))
            img.paste(cover(pics[1], (w - px, h - h // 2)), (px, h // 2))
    img = shade(img, "left", start=0.38, strength=255)
    d = ImageDraw.Draw(img)
    pad = int(56 * s)
    brand(d, (pad, int(40 * s)), int(30 * s))
    words = title.split()
    big = font(int(128 * s))
    # '이번 주' / '여행 뉴스' 두 줄. 둘째 줄은 노랑.
    if len(words) >= 3:
        l1, l2 = " ".join(words[:2]), " ".join(words[2:])
    else:
        l1, l2 = title, ""
    y = int(170 * s)
    stroke_text(d, (pad, y), l1, big, stroke=int(8 * s))
    if l2:
        stroke_text(d, (pad, y + int(150 * s)), l2, big, fill=YELLOW, stroke=int(8 * s))
    y += int(330 * s)
    cf = font(int(34 * s))
    x = pad
    for r in regions[:5]:
        cw = chip(d, (x, y), r, cf, pad=(int(18 * s), int(8 * s)))
        x += cw + int(12 * s)
        if x > px - int(80 * s):
            break
    d.text((pad, h - int(70 * s)), f"핵심 {count}건 · waffletrip.com", font=font(int(30 * s)),
           fill=(220, 224, 230))
    return img


# ── 연예 '오늘의 방송' 썸네일 (가로) ────────────────────────────────────
def ent_thumb(date_label: str, programs: list[str], count: int, photo_img: Image.Image | None = None,
              size=(1280, 720), credit: str = "") -> Image.Image:
    """'11월 14일 오늘의 방송' + 프로그램 이름 딱지. 출연자 사진(자유 이용)이 있으면 오른쪽에."""
    w, h = size
    s = w / 1280
    img = Image.new("RGB", size, (26, 16, 40))
    if photo_img is not None:
        pw = int(w * 0.42)
        ph = ImageOps.fit(photo_img.convert("RGB"), (pw, h), Image.LANCZOS, centering=(0.5, 0.3))
        img.paste(ph, (w - pw, 0))
        img = shade(img, "left", start=0.45, strength=255)
    d = ImageDraw.Draw(img)
    pad = int(56 * s)
    if photo_img is None:
        # 사진이 없으면 오른쪽에 오늘 방송 목록을 번호와 함께 크게 세운다.
        bx = int(w * 0.60)
        d.rectangle((bx, 0, w, h), fill=CORAL)
        lf = font(int(46 * s))
        y0 = int(110 * s)
        for i, p in enumerate([x for x in programs if x][:5], 1):
            line = p
            while d.textlength(line, font=lf) > w - bx - int(150 * s) and len(line) > 2:
                line = line[:-1]
            if line != p:
                line = line.rstrip() + "…"
            d.text((bx + int(44 * s), y0), f"{i:02d}", font=font(int(34 * s)), fill=(255, 225, 215))
            d.text((bx + int(110 * s), y0 - int(8 * s)), line, font=lf, fill=WHITE)
            y0 += int(104 * s)
    brand(d, (pad, int(40 * s)), int(30 * s))
    chip(d, (pad, int(150 * s)), date_label, font(int(40 * s)), bg=YELLOW, fg=BLACK)
    stroke_text(d, (pad, int(230 * s)), "오늘의", font(int(140 * s)), stroke=int(8 * s))
    stroke_text(d, (pad, int(390 * s)), "방송", font(int(140 * s)), fill=YELLOW, stroke=int(8 * s))
    cf = font(int(32 * s))
    x, y = pad, int(585 * s)
    limit = w - int(w * 0.42) - pad if photo_img is not None else int(w * 0.60) - pad
    for p in (programs if photo_img is not None else []):
        if not p:
            continue
        tw = d.textlength(p, font=cf) + 36 * s
        if x + tw > limit:
            break
        x += chip(d, (x, y), p, cf, pad=(int(18 * s), int(8 * s))) + int(12 * s)
    if photo_img is not None and credit:
        # 자유 이용 사진은 작성자·라이선스를 사진 곁에 밝혀야 쓸 수 있다(CC BY).
        cf2 = font(max(12, int(16 * s)))
        pw = int(w * 0.42)
        cap = credit
        while d.textlength(cap, font=cf2) > pw - int(24 * s) and len(cap) > 8:
            cap = cap[:-2]
        if cap != credit:
            cap += "…"
        d.text((w - pw + int(12 * s), int(14 * s)), cap, font=cf2, fill=(235, 235, 240),
               stroke_width=2, stroke_fill=(0, 0, 0))
    d.text((w - pad - d.textlength(f"{count}편 미리보기", font=font(int(30 * s))), h - int(64 * s)),
           f"{count}편 미리보기", font=font(int(30 * s)), fill=(225, 225, 235))
    return img


def save_jpg(img: Image.Image, path: str, max_bytes: int = 1_900_000) -> str:
    """유튜브 썸네일 한도(2MB) 안으로 저장한다."""
    q = 90
    while True:
        img.convert("RGB").save(path, "JPEG", quality=q, optimize=True)
        if os.path.getsize(path) <= max_bytes or q <= 60:
            return path
        q -= 8
