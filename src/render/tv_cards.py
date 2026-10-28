"""연예 '방송' 기사의 대표 이미지 — 우리가 그린 카드.

방송사들이 보도 스틸의 무단 게재를 금지한다(2026-10-16 실측: MBC "사전 동의 없이
무단 전재 및 게재를 할 수 없습니다", SBS·EBS 무단 전재 금지). 사장님 결정으로 사진
대신 기사 제목을 얹은 피플로드 카드를 쓴다. 허락을 받으면 그때 스틸로 바꾼다.

빌드 때 그린다. 저장소에 쌓지 않는다 — 하루 8장씩 쌓이면 공개 저장소가 무거워진다.
같은 기사는 늘 같은 카드가 나오므로(제목·날짜만 쓴다) 다시 그려도 달라지지 않는다.
"""
from __future__ import annotations

import os
import re

from src.brand import DOMAIN, SITE_NAME, SITE_NAME_EN

W, H = 1200, 630
INK = (14, 14, 15)
PAPER = (255, 255, 255)
CORAL = (240, 78, 55)
MUTED = (110, 110, 115)
LINE = (234, 234, 231)

FONTS = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKkr-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
)


def _font(size: int):
    from PIL import ImageFont
    for path in FONTS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return None                          # 한글 글꼴이 없으면 카드를 그리지 않는다


def _wrap(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    """글자 단위로 줄을 나눈다. 한국어 제목은 띄어쓰기가 적어 낱말 단위로 못 자른다.
    넘치면 마지막 줄 끝을 '…' 로 줄인다."""
    lines, cur, used = [], "", 0
    for ch in text:
        if draw.textlength(cur + ch, font=font) > width and cur:
            lines.append(cur.rstrip())
            used += len(cur)
            cur = ch.lstrip()
            if len(lines) == max_lines:
                break
        else:
            cur += ch
    else:
        if cur:
            lines.append(cur)
            used += len(cur)
    if used < len(text) and lines:
        lines[-1] = lines[-1][:-1] + "…"
    return lines[:max_lines]


def card_name(item) -> str:
    return re.sub(r"[^0-9A-Za-z_-]", "", str(item.id))[:60] or "card"


def draw_card(title: str, date: str, path: str, kicker: str = "오늘 방송") -> bool:
    """카드 한 장. 글꼴이 없으면 False — 사진 없는 기사로 나간다."""
    from PIL import Image, ImageDraw
    big = _font(64)
    if big is None:
        return False
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 10), fill=INK)
    d.text((80, 70), f"{SITE_NAME} 문화 · 방송·드라마", font=_font(34), fill=MUTED)
    d.ellipse((80, 140, 104, 164), fill=CORAL)
    d.text((118, 128), kicker, font=_font(34), fill=CORAL)
    y = 210
    for line in _wrap(d, title, big, W - 160, 3):
        d.text((80, y), line, font=big, fill=INK)
        y += 86
    d.line((80, 500, W - 80, 500), fill=LINE, width=2)
    d.text((84, 530), date, font=_font(28), fill=INK)
    d.text((W - 84 - d.textlength(f"{SITE_NAME_EN} · {DOMAIN}", font=_font(26)), 532),
           f"{SITE_NAME_EN} · {DOMAIN}", font=_font(26), fill=MUTED)
    d.rectangle((0, H - 10, W, H), fill=CORAL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, "JPEG", quality=86, optimize=True)
    return True


def attach_tv_cards(items, out_dir: str) -> int:
    """사진 없는 방송 기사에 카드를 그려 붙인다. 붙인 개수.

    /img/tv/<id>.jpg 와 공유용 /og/tv/<id>.jpg 를 같은 그림으로 둔다 — 공유 카드
    경로 규칙(photos.og_path)을 그대로 타게 하려는 것이다.
    """
    made = 0
    for item in items:
        if (getattr(item, "channel", "") != "ent" or getattr(item, "category", "") != "tv"
                or item.photo):
            continue
        name = card_name(item)
        day = (item.published_at or "")[:10].replace("-", ".")
        web = f"/img/tv/{name}.jpg"
        dst = os.path.join(out_dir, "img", "tv", f"{name}.jpg")
        # 방송·드라마 부문에는 회차 예고 말고 드라마 소식도 들어온다(2026-10-28).
        # '오늘 방송'은 방송 정보 상자가 있는 회차 예고에만 붙인다.
        kicker = "오늘 방송" if "방송 정보" in (item.body_md or "") else "방송·드라마"
        if not draw_card(item.title, day, dst, kicker):
            continue
        og = os.path.join(out_dir, "og", "tv", f"{name}.jpg")
        os.makedirs(os.path.dirname(og), exist_ok=True)
        with open(dst, "rb") as src, open(og, "wb") as out:
            out.write(src.read())
        item.photo = web
        made += 1
    return made
