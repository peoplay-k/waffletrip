#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""말에 맞춰 나오는 자막 — 쇼츠에서 쓴다.

2026-11-14 사장님: "나레이션을 넣고 거기에 맞게 자막이 나오는 형식으로 하는 게 좋을 것 같아.
지금 너무 영상이 허접해." 그전에는 장면마다 문장 전체를 한 화면에 깔아 두었다 —
말과 글이 따로 놀고 화면이 신문 지면처럼 빽빽했다.

이제는 나레이션을 짧은 토막(한두 줄, 열댓 자)으로 나눠, 그 토막을 **말하는 순간**에
화면 가운데 아래에 크게 띄운다. 시각은 일레븐랩스가 돌려준 글자별 시각(narrate.speak 의
.align.json)에서 읽고, 없으면 글자 수에 비례해 어림한다.

자막 글씨는 지어내지 않는다 — 나레이션 문장을 그대로 자를 뿐이다.
"""
from __future__ import annotations

import json
import os
import re

from PIL import Image, ImageDraw, ImageFilter

from thumbnails import BLACK, WHITE, YELLOW, font

MAX_CHARS = 15          # 한 토막 글자 수(빈칸 포함). 폰에서 한눈에 읽히는 길이
CAP_SIZE = 82           # 자막 글자 크기(1080 폭 기준)
LEAD = 0.06             # 말보다 아주 조금 먼저 띄운다 — 눈이 귀보다 느리다


# ── 토막 나누기 ─────────────────────────────────────────────────────
def chunks(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """낱말 단위로 max_chars 안에서 묶는다. 쉼표·마침표 뒤에서는 끊는다."""
    words = _keep_quotes((text or "").split())
    out, cur = [], ""
    for w in words:
        nxt = f"{cur} {w}".strip()
        if cur and len(nxt) > max_chars:
            out.append(cur)
            cur = w
        else:
            cur = nxt
        if re.search(r"[.!?]$", cur) or (re.search(r"[,…]$", cur) and len(cur) >= max_chars * 0.5):
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    # 마지막 토막이 한두 글자면 앞에 붙인다(혼자 뜨면 어색하다)
    if len(out) >= 2 and len(out[-1]) <= 3:
        out[-2] = f"{out[-2]} {out[-1]}"
        out.pop()
    return [c.rstrip(".") for c in out]


def _keep_quotes(words: list[str]) -> list[str]:
    """따옴표로 묶인 이름('사랑이 온다')은 한 덩어리로 — 자막이 제목 한가운데서 끊기지 않게."""
    out, buf = [], []
    for w in words:
        if buf:
            buf.append(w)
            if re.search(r"['’\"”]", w):
                out.append(" ".join(buf))
                buf = []
            continue
        opens = len(re.findall(r"['‘\"“]", w))
        if opens % 2 == 1 and not re.search(r"['’\"”][^'’\"”]*$", w[1:] if w[:1] in "'‘\"“" else w):
            buf = [w]
        else:
            out.append(w)
    if buf:
        out.append(" ".join(buf))
    return out


# ── 시각 ───────────────────────────────────────────────────────────
def load_align(mp3: str) -> dict | None:
    path = mp3.rsplit(".", 1)[0] + ".align.json"
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def timings(text: str, parts: list[str], speech_secs: float,
            align: dict | None = None, scene_secs: float | None = None) -> list[tuple[float, float]]:
    """토막마다 (보이기 시작, 사라질 때). 토막 사이에 빈 화면이 생기지 않게 다음 토막까지 둔다."""
    scene_secs = scene_secs or speech_secs
    starts: list[float] = []
    chars = (align or {}).get("characters") or []
    st = (align or {}).get("character_start_times_seconds") or []
    if chars and len(chars) == len(st):
        joined = "".join(chars)
        pos = 0
        for p in parts:
            first = p.replace(" ", "")[:1]
            i = joined.find(first, pos) if first else -1
            if i < 0:
                starts = []
                break
            starts.append(float(st[i]))
            pos = i + max(1, len(p) - 1)
    if not starts:
        # 어림: 글자 수에 비례(빈칸은 덜 친다)
        weights = [len(p.replace(" ", "")) + 0.3 * p.count(" ") + 1 for p in parts]
        total = sum(weights) or 1
        t, starts = 0.0, []
        for w in weights:
            starts.append(t)
            t += speech_secs * w / total
    out = []
    for k, s in enumerate(starts):
        a = 0.0 if k == 0 else max(0.0, s - LEAD)
        b = (starts[k + 1] - LEAD) if k + 1 < len(starts) else scene_secs
        out.append((round(a, 3), round(max(b, a + 0.2), 3)))
    return out


# ── 그리기 ──────────────────────────────────────────────────────────
def _wrap2(d, text: str, f, max_w: int) -> list[str]:
    if d.textlength(text, font=f) <= max_w:
        return [text]
    words = text.split()
    best = [text]
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if d.textlength(a, font=f) <= max_w and d.textlength(b, font=f) <= max_w:
            if len(best) == 1 or abs(len(a) - len(b)) < abs(len(best[0]) - len(best[1])):
                best = [a, b]
    return best


def render(text: str, width: int = 1080, size: int = CAP_SIZE, pad: int = 70) -> Image.Image:
    """투명 바탕 자막 그림. 흰 굵은 글씨 + 검은 테두리 + 그림자. 숫자가 든 낱말은 노랑."""
    f = font(size)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    max_w = width - pad * 2
    lines = _wrap2(probe, text, f, max_w)
    while any(probe.textlength(ln, font=f) > max_w for ln in lines) and f.size > 50:
        f = font(f.size - 6)
        lines = _wrap2(probe, text, f, max_w)
    lh = int(f.size * 1.28)
    h = lh * len(lines) + 40
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    d = ImageDraw.Draw(img)
    stroke = max(5, f.size // 11)
    for k, line in enumerate(lines):
        y = 14 + k * lh
        x = (width - d.textlength(line, font=f)) / 2
        sd.text((x + 4, y + 7), line, font=f, fill=(0, 0, 0, 170), stroke_width=stroke,
                stroke_fill=(0, 0, 0, 170))
        cx = x
        for i, word in enumerate(line.split(" ")):
            piece = word if i == 0 else " " + word
            col = YELLOW if re.search(r"\d", word) else WHITE
            d.text((cx, y), piece, font=f, fill=col, stroke_width=stroke, stroke_fill=BLACK)
            cx += d.textlength(piece, font=f)
    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    return Image.alpha_composite(shadow, img)


def scene_captions(text: str, speech_secs: float, scene_secs: float, work: str, tag: str,
                   align: dict | None = None, width: int = 1080, max_chars: int = MAX_CHARS,
                   size: int = CAP_SIZE) -> list[tuple[str, float, float]]:
    """자막 그림 파일과 보일 구간 목록. 가로 영상은 width·max_chars·size 를 키워 부른다."""
    parts = chunks(text, max_chars)
    if not parts:
        return []
    times = timings(text, parts, speech_secs, align, scene_secs)
    out = []
    for k, (p, (a, b)) in enumerate(zip(parts, times)):
        path = os.path.join(work, f"cap_{tag}_{k:02d}.png")
        render(p, width, size, pad=70 if width <= 1080 else 160).save(path)
        out.append((path, a, b))
    return out


def overlay_filter(base: str, caps: list[tuple[str, float, float]], first_input: int,
                   y_center: int) -> tuple[str, str]:
    """[base] 위에 자막들을 차례로 얹는 필터. (필터 문자열, 마지막 출력 이름)."""
    parts, cur = [], base
    for k, (_p, a, b) in enumerate(caps):
        nxt = f"[cv{k}]"
        # 뜰 때 0.12초 동안 스르르 — 툭 튀어나오면 기계 같다
        parts.append(f"[{first_input + k}:v]format=rgba,fade=t=in:st={a:.3f}:d=0.12:alpha=1[cf{k}]")
        parts.append(f"{cur}[cf{k}]overlay=x=(W-w)/2:y={y_center}-h/2:"
                     f"enable='between(t,{a:.3f},{b:.3f})'{nxt}")
        cur = nxt
    return ";".join(parts), cur


def talk_clip(ff: str, frame: str, caps: list[tuple[str, float, float]], secs: float, vf: str,
              out: str, y_center: int, mp3: str | None = None, tail: float = 0.6, fps: int = 25,
              silence: bool = False, crf: str = "22") -> str:
    """바탕 그림(줌) + 자막 + 나레이션으로 장면 클립 하나. silence 면 무음 트랙을 단다."""
    import subprocess
    args = [ff, "-y", "-loglevel", "error", "-i", frame]
    for path, _a, _b in caps:
        args += ["-loop", "1", "-framerate", str(fps), "-t", f"{secs:.2f}", "-i", path]
    flt = f"[0:v]{vf}[bg]"
    over, last = overlay_filter("[bg]", caps, 1, y_center)
    if over:
        flt += ";" + over
    ai = len(caps) + 1
    amap = []
    if mp3:
        args += ["-i", mp3]
        flt += f";[{ai}:a]apad=pad_dur={tail},aresample=44100[a]"
        amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    elif silence:
        args += ["-f", "lavfi", "-t", f"{secs:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        flt += f";[{ai}:a]anull[a]"
        amap = ["-map", "[a]", "-c:a", "aac", "-b:a", "128k"]
    args += ["-filter_complex", flt, "-map", last, *amap,
             "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p",
             "-t", f"{secs:.2f}", out]
    subprocess.run(args, check=True)
    return out
