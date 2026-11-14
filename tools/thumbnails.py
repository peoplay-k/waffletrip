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
import re

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


def short_hook(headline: str) -> str:
    """기사 제목에서 표지에 걸 앞 토막만. '…' 뒤 덧붙임과 따옴표를 뗀다.

    뉴스 제목을 통째로 얹으면 기계가 붙인 자막처럼 보인다. 사람이 만든 표지는
    한 토막만 크게 쓴다. 말은 바꾸지 않고 자르기만 한다(지어내지 않는다).
    """
    t = re.split(r"\s*(?:…|\.\.\.)\s*", (headline or "").strip())[0]
    t = re.sub(r"[‘’'\"“”]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def box_lines(img: Image.Image, xy, lines: list[str], f, bg, fg, angle: float = 0.0,
              pad=(26, 12)) -> int:
    """자막 상자처럼 줄마다 색 띠를 깔고 글씨를 얹는다. 살짝 기울여 손으로 붙인 느낌.

    줄 길이대로 띠 길이가 달라진다 — 틀에서 찍은 같은 크기 딱지와 다르다.
    그린 높이를 돌려준다.
    """
    d0 = ImageDraw.Draw(img)
    lh = int(f.size * 1.32)
    widths = [int(d0.textlength(t, font=f)) + pad[0] * 2 for t in lines]
    lw, lh_all = max(widths) + 40, lh * len(lines) + 40
    layer = Image.new("RGBA", (lw, lh_all), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y = 20
    for t, wd in zip(lines, widths):
        d.rectangle((20, y, 20 + wd, y + lh - 6), fill=bg + (255,))
        d.text((20 + pad[0], y + (lh - 6 - f.size) / 2 - f.size * 0.12), t, font=f, fill=fg)
        y += lh
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.paste(layer, (int(xy[0]) - 20, int(xy[1]) - 20), layer)
    return lh * len(lines)


def soft_shadow_text(img: Image.Image, xy, text: str, f, fill=WHITE, blur: int = 6):
    """테두리 대신 부드러운 그림자. 굵은 검은 테두리는 템플릿 티가 난다."""
    w, h = img.size
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).text((xy[0] + 3, xy[1] + 5), text, font=f, fill=255,
                                stroke_width=max(2, f.size // 18), stroke_fill=255)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", (w, h), BLACK), (0, 0), sh)
    ImageDraw.Draw(img).text(xy, text, font=f, fill=fill)


# 곳마다 띠 색을 달리한다. 날마다 같은 노랑이면 자동으로 찍어낸 티가 난다.
_ACCENTS = [(255, 214, 0), (255, 255, 255), (64, 224, 208), (255, 138, 101), (190, 242, 100)]


def accent_for(name: str):
    return _ACCENTS[sum(map(ord, name or "")) % len(_ACCENTS)]


def pick_variant(name: str, n: int = 3, now=None) -> int:
    """날·곳마다 배치를 바꾼다. 매일 같은 자리에 같은 상자가 뜨면 자동 생성 티가 난다."""
    from datetime import datetime, timedelta, timezone
    day = (now or datetime.now(timezone(timedelta(hours=9)))).toordinal()
    return (day + sum(map(ord, name or ""))) % n


def short_cover(name: str, count: int, hook: str = "", photo: str | None = None,
                seconds: int | None = None, period: str = "이번 주",
                variant: int | None = None) -> Image.Image:
    """사진을 크게 살리고, 지명 하나와 기사 한 토막만 자막 상자로 얹는다.

    배치는 세 가지를 돌린다.
      0 아래 왼쪽에 지명 상자(오른쪽으로 기울임) + 검은 자막 상자
      1 위쪽에 지명 상자(왼쪽으로 기울임), 아래에 흰 자막 상자
      2 상자 없는 큰 지명 글씨 + 그 위에 기울인 노랑 자막 상자
    """
    v = pick_variant(name) if variant is None else variant % 3
    top_bias = (0.35, 0.6, 0.45)[v]
    img = cover(photo, (SHORT_W, SHORT_H), top_bias)
    img = shade(img, "bottom", start=0.55, strength=170)
    if v == 1:
        img = shade(img, "top", start=0.70, strength=120)
    d = ImageDraw.Draw(img)
    soft_shadow_text(img, (SHORT_PAD, 120) if v != 1 else (SHORT_W - SHORT_PAD - 170, 120),
                     "피플로드", font(38))

    bottom = SHORT_H - SHORT_SAFE_BOTTOM - 10
    lines, hf = ([], None)
    text = short_hook(hook)
    if text:
        lines, hf = fit_lines(d, text, SHORT_W - SHORT_PAD * 2 - 60, 2, (68, 62, 56, 52))
    hook_h = int(hf.size * 1.32) * len(lines) if hf else 0
    name_f = font(200 if len(name) <= 3 else 160 if len(name) <= 5 else 120)
    small = f"{period} 소식 {count}가지"
    accent = accent_for(name)

    if v == 0:
        y_name = bottom - hook_h - (30 if lines else 0) - int(name_f.size * 1.32)
        soft_shadow_text(img, (SHORT_PAD + 6, y_name - 70), small, font(46))
        box_lines(img, (SHORT_PAD, y_name), [name], name_f, accent, BLACK, angle=2.0, pad=(30, 6))
        if lines:
            box_lines(img, (SHORT_PAD, bottom - hook_h), lines, hf, BLACK, WHITE, pad=(22, 10))
    elif v == 1:
        y_name = 300
        box_lines(img, (SHORT_PAD, y_name), [name], name_f, accent, BLACK, angle=-2.5, pad=(30, 6))
        soft_shadow_text(img, (SHORT_PAD + 10, y_name + int(name_f.size * 1.32) + 40), small, font(46))
        if lines:
            box_lines(img, (SHORT_PAD, bottom - hook_h), lines, hf, WHITE, BLACK, pad=(22, 10))
    else:
        y_name = bottom - int(name_f.size * 1.25)
        if lines:
            box_lines(img, (SHORT_PAD, y_name - hook_h - 40), lines, hf, YELLOW, BLACK,
                      angle=1.5, pad=(22, 10))
            soft_shadow_text(img, (SHORT_PAD + 6, y_name - hook_h - 120), small, font(46))
        else:
            soft_shadow_text(img, (SHORT_PAD + 6, y_name - 80), small, font(46))
        soft_shadow_text(img, (SHORT_PAD, y_name), name, name_f, blur=12)
    return img


# ── 여행 주간 롱폼 썸네일 (가로) ─────────────────────────────────────
def long_thumb(regions: list[str], count: int, photos: list[str], size=(1280, 720),
               title: str = "이번 주 여행 뉴스") -> Image.Image:
    """사진 한 장을 꽉 채우고, 제목을 자막 상자로. 다룬 곳은 한 줄 글씨로."""
    w, h = size
    s = w / 1280
    pics = [p for p in photos if p and os.path.exists(p)]
    img = shade(cover(pics[0] if pics else None, size, 0.45), "bottom", start=0.40, strength=200)
    soft_shadow_text(img, (int(48 * s), int(36 * s)), "피플로드", font(int(30 * s)))
    words = title.split()
    l1, l2 = (" ".join(words[:2]), " ".join(words[2:])) if len(words) >= 3 else (title, "")
    big = font(int(104 * s))
    x = int(56 * s)
    y = int(330 * s)
    box_lines(img, (x, y), [l1], big, WHITE, BLACK, angle=-1.5, pad=(int(24 * s), int(4 * s)))
    if l2:
        box_lines(img, (x + int(30 * s), y + int(150 * s)), [l2], big, YELLOW, BLACK,
                  angle=-1.5, pad=(int(24 * s), int(4 * s)))
    names = " · ".join(regions[:6])
    soft_shadow_text(img, (x, h - int(84 * s)), names, font(int(38 * s)))
    return img


# ── 연예 '오늘의 방송' 썸네일 (가로) ────────────────────────────────────
def ent_thumb(date_label: str, programs: list[str], count: int, photo_img: Image.Image | None = None,
              size=(1280, 720), credit: str = "") -> Image.Image:
    """'오늘의 방송' 자막 상자 + 오늘 나가는 프로그램 이름. 출연자 사진(자유 이용)이 있으면 크게."""
    w, h = size
    s = w / 1280
    progs = [p for p in programs if p]
    if photo_img is not None:
        img = ImageOps.fit(photo_img.convert("RGB"), size, Image.LANCZOS, centering=(0.6, 0.3))
        img = shade(img, "left", start=0.30, strength=215)
    else:
        img = Image.new("RGB", size, (26, 16, 40))
    d = ImageDraw.Draw(img)
    pad = int(56 * s)
    soft_shadow_text(img, (pad, int(36 * s)), "피플로드 연예", font(int(30 * s)))
    soft_shadow_text(img, (pad + int(6 * s), int(170 * s)), date_label, font(int(44 * s)))
    big = font(int(118 * s))
    box_lines(img, (pad, int(250 * s)), ["오늘의 방송"], big, YELLOW, BLACK, angle=-1.5,
              pad=(int(24 * s), int(4 * s)))
    lf = font(int(40 * s))
    y = int(450 * s)
    limit = int(w * 0.55) if photo_img is not None else int(w * 0.92)
    for p in progs[:4]:
        line = p
        while d.textlength(line, font=lf) > limit - pad and len(line) > 2:
            line = line[:-1]
        soft_shadow_text(img, (pad, y), line if line == p else line.rstrip() + "…", lf)
        y += int(58 * s)
    if photo_img is not None and credit:
        # 자유 이용 사진은 작성자·라이선스를 사진 곁에 밝혀야 쓸 수 있다(CC BY).
        cf2 = font(max(12, int(16 * s)))
        cap = credit
        while d.textlength(cap, font=cf2) > w * 0.45 and len(cap) > 8:
            cap = cap[:-2]
        if cap != credit:
            cap += "…"
        d.text((w - int(12 * s) - d.textlength(cap, font=cf2), h - int(30 * s)), cap, font=cf2,
               fill=(235, 235, 240), stroke_width=2, stroke_fill=(0, 0, 0))
    return img


def save_jpg(img: Image.Image, path: str, max_bytes: int = 1_900_000) -> str:
    """유튜브 썸네일 한도(2MB) 안으로 저장한다."""
    q = 90
    while True:
        img.convert("RGB").save(path, "JPEG", quality=q, optimize=True)
        if os.path.getsize(path) <= max_bytes or q <= 60:
            return path
        q -= 8
