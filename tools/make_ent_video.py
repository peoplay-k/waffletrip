#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""연예 '오늘의 방송' 영상 — 롱폼(16:9) 한 편과 숏폼(9:16) 몇 편 (2026-10-16).

사장님: "이걸 가지고 나레이션 형식으로 유튜브 롱폼도 같이 제작하고 그걸 숏폼으로 해서
같이 제작하자". 재료는 그날 실린 **우리 '방송' 기사**(ent/tv)다. 나레이션은 기사 요약을
그대로 읽는다 — 요약은 우리가 쓴 문장이고, 영상에서 새 말을 지어내지 않는다.

목소리는 연예 전용 AI 남자 성우(narrate.ENT_VOICE_ID, 'MJ'). 여행 영상(뉴스 리포터)과
가른다. 사진은 쓰지 않는다 — 방송사 스틸은 무단 게재 금지라 우리 카드 화면으로 짠다.

    python tools/make_ent_video.py --script-only        대본만
    python tools/make_ent_video.py --frames DIR          화면까지
    python tools/make_ent_video.py --voiced --out static/video
    python tools/make_ent_video.py --silent --out static/video

나오는 것: peopleroad-tv-YYYYMMDD.mp4(롱폼), peopleroad-tv-YYYYMMDD-1.mp4 …(숏폼).
워크플로 파일은 이 저장소 토큰으로 못 고쳐서 make_longform.py 가 끝에 이것을 부른다.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from src.brand import DOMAIN  # noqa: E402

KST = timezone(timedelta(hours=9))
INK, PAPER, CORAL, MUTED, LINE = (14, 14, 15), (250, 250, 249), (240, 78, 55), (110, 110, 115), (225, 225, 220)
FONTS = ("/System/Library/Fonts/AppleSDGothicNeo.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
MIN_ITEMS = 2          # 한 편짜리는 '오늘의 방송'이 아니다
MAX_LONG = 8
MAX_SHORTS = 2         # 숏폼은 하루 두 편까지 — 2026-10-16 크레딧이 바닥나 셋에서 줄였다
TAIL = 0.6             # 말끝에 두는 숨(초)
READ_CPS, READ_FLOOR, READ_LEAD = 8.5, 3.0, 1.4


def _font(size: int):
    for path in FONTS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    raise RuntimeError("한글 글꼴이 없다 — 깨진 화면을 만들지 않는다")


def _wrap(d, text: str, font, width: int, max_lines: int) -> list[str]:
    """낱말 단위로 줄을 나누고, 낱말이 너무 길면 글자 단위로 자른다."""
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip("…") + "…"
    return lines


# ── 재료 ──────────────────────────────────────────────────────────
_BOX = re.compile(r"^>\s*채널\s*·\s*([^|]+)\|\s*프로그램\s*·\s*([^|\n]+)(?:\|\s*회차\s*·\s*(.+))?$", re.M)
_WHEN = re.compile(r"^>\s*방송\s*·\s*(.+)$", re.M)
_TIME = re.compile(r"(오전|오후|밤|저녁|새벽)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?")


def info_of(item: dict) -> dict:
    """본문 맨 위 '방송 정보' 상자에서 채널·프로그램·회차·시각을 읽는다."""
    body = item.get("body_md") or ""
    box, when = _BOX.search(body), _WHEN.search(body)
    tm = _TIME.search(when.group(1)) if when else None
    hour = 0
    if tm:
        hour = int(tm.group(2)) % 12 + (12 if tm.group(1) in ("오후", "밤", "저녁") else 0)
        hour = hour * 100 + int(tm.group(3) or 0)
    return {"channel": box.group(1).strip() if box else "",
            "program": box.group(2).strip() if box else "",
            "episode": (box.group(3) or "").strip() if box else "",
            "when": tm.group(0) if tm else "", "sort": hour or 9999}


def load_today(data_dir: str = "data", today: str = "") -> list[dict]:
    today = today or datetime.now(KST).strftime("%Y-%m-%d")
    rows, seen = [], set()
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl"))):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if (r.get("channel") == "ent" and r.get("category") == "tv"
                        and r.get("grade") == "C" and r["id"] not in seen
                        and (r.get("published_at") or "")[:10] == today):
                    seen.add(r["id"])
                    rows.append(r)
    for r in rows:
        r["info"] = info_of(r)
    rows.sort(key=lambda r: r["info"]["sort"])
    return rows


def _sentences(text: str, n: int) -> str:
    parts = re.split(r"(?<=[.!?다])\s+", (text or "").strip())
    return " ".join(p for p in parts[:n] if p).strip()


def _spoken(text: str) -> str:
    """읽을 때 걸리는 기호를 정리한다. 따옴표·괄호는 소리 내 읽지 않는다."""
    t = re.sub(r"[‘’'\"“”「」『』]", "", text or "")
    t = re.sub(r"\s*\([^)]*\)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def script_long(items: list[dict], today: str) -> list[dict]:
    d = datetime.fromisoformat(today)
    scenes = [{"kind": "open", "count": len(items), "date": f"{d.month}월 {d.day}일",
               "narration": f"{d.month}월 {d.day}일, 오늘의 방송을 피플로드가 미리 봤습니다. "
                            f"모두 {len(items)}편입니다."}]
    for n, it in enumerate(items, 1):
        info = it["info"]
        scenes.append({"kind": "story", "n": n, "total": len(items), "info": info,
                       "title": it["title"], "summary": _sentences(it.get("summary"), 2),
                       # 요약에 이미 채널·시각이 들어 있다 — 앞에 또 붙이면 두 번 읽는다.
                       "narration": _spoken(_sentences(it.get("summary"), 2))})
    scenes.append({"kind": "close",
                   "narration": "더 자세한 이야기는 피플로드 연예면에서 보실 수 있습니다. 내일도 미리 보겠습니다."})
    return scenes


def script_short(item: dict) -> list[dict]:
    info = item["info"]
    head = f"오늘 {info['when']} {info['channel']}".replace("  ", " ").strip()
    summ = re.split(r"(?<=[.!?다])\s+", (item.get("summary") or "").strip())
    scenes = [{"kind": "s_open", "info": info, "title": item["title"],
               "narration": _spoken(f"{head}, {info['program']}.")}]
    for s in [x for x in summ if x][:2]:
        scenes.append({"kind": "s_line", "info": info, "line": s, "narration": _spoken(s)})
    scenes.append({"kind": "s_close", "narration": "피플로드 연예였습니다."})
    return scenes


# ── 화면 ──────────────────────────────────────────────────────────
def _brand(d, x, y, size):
    f = _font(size)
    d.text((x, y), "피플로드", font=f, fill=INK)
    d.text((x + d.textlength("피플로드", font=f), y), ".", font=f, fill=CORAL)
    d.text((x + d.textlength("피플로드.", font=f) + 16, y + size * 0.25), "연예 · 오늘의 방송",
           font=_font(int(size * 0.6)), fill=MUTED)


def render_long(sc: dict) -> Image.Image:
    W, H, P = 1920, 1080, 132
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    _brand(d, P, 64, 34)
    d.line([(P, H - 96), (W - P, H - 96)], fill=LINE, width=2)
    d.text((P, H - 78), DOMAIN, font=_font(26), fill=MUTED)
    if sc["kind"] == "open":
        d.text((P, 360), sc["date"], font=_font(48), fill=CORAL)
        d.text((P, 430), "오늘의 방송", font=_font(150), fill=INK)
        d.text((P, 640), f"피플로드가 미리 본 {sc['count']}편", font=_font(48), fill=MUTED)
    elif sc["kind"] == "story":
        info = sc["info"]
        d.text((P, 190), f"{sc['n']:02d} / {sc['total']:02d}", font=_font(32), fill=CORAL)
        tag = " · ".join(x for x in (info["channel"], info["when"], info["episode"]) if x)
        d.text((P, 240), tag, font=_font(40), fill=MUTED)
        y = 320
        for line in _wrap(d, sc["title"], _font(68), W - P * 2, 3):
            d.text((P, y), line, font=_font(68), fill=INK)
            y += 92
        y += 30
        for line in _wrap(d, sc["summary"], _font(40), W - P * 2, 4):
            d.text((P, y), line, font=_font(40), fill=MUTED)
            y += 58
    else:
        d.text((P, 420), "자세한 이야기는", font=_font(56), fill=MUTED)
        d.text((P, 500), f"{DOMAIN}/ent/tv", font=_font(96), fill=INK)
        d.line([(P, 640), (P + 160, 640)], fill=CORAL, width=8)
    return im


def render_short(sc: dict) -> Image.Image:
    W, H, P = 1080, 1920, 84
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    _brand(d, P, 120, 40)
    info = sc.get("info") or {}
    if sc["kind"] == "s_open":
        d.text((P, 520), "오늘 방송", font=_font(48), fill=CORAL)
        d.text((P, 590), " · ".join(x for x in (info.get("channel"), info.get("when")) if x),
               font=_font(56), fill=MUTED)
        y = 700
        for line in _wrap(d, sc["title"], _font(84), W - P * 2, 5):
            d.text((P, y), line, font=_font(84), fill=INK)
            y += 112
    elif sc["kind"] == "s_line":
        d.text((P, 520), info.get("program", ""), font=_font(48), fill=CORAL)
        y = 620
        for line in _wrap(d, sc["line"], _font(72), W - P * 2, 7):
            d.text((P, y), line, font=_font(72), fill=INK)
            y += 100
    else:
        d.text((P, 760), "피플로드 연예", font=_font(96), fill=INK)
        d.text((P, 900), f"{DOMAIN}/ent/tv", font=_font(48), fill=MUTED)
        d.line([(P, 1000), (P + 160, 1000)], fill=CORAL, width=8)
    # 세 플랫폼 모두 아래쪽을 UI 로 덮는다 — 글자는 위에만 둔다.
    return im


# ── 굽기 ──────────────────────────────────────────────────────────
def _ff():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _secs_of(ff: str, mp3: str) -> float:
    probe = subprocess.run([ff, "-i", mp3], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
    return (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 4.0


def bake(scenes: list[dict], render, size: tuple[int, int], out: str, voiced: bool) -> float:
    """장면들을 영상 하나로. voiced 면 MJ 목소리, 아니면 읽는 속도로 무음."""
    import tempfile
    ff = _ff()
    work = tempfile.mkdtemp(prefix="peopleroad-tv-")
    clips, total = [], 0.0
    for n, sc in enumerate(scenes):
        frame = os.path.join(work, f"f{n:02d}.png")
        render(sc).save(frame)
        clip = os.path.join(work, f"c{n:02d}.mp4")
        vf = f"scale={size[0]}:{size[1]},format=yuv420p,fps=25"
        if voiced:
            from narrate import ENT_VOICE_ID, speak
            mp3 = os.path.join(work, f"a{n:02d}.mp3")
            speak(sc["narration"], mp3, voice_id=ENT_VOICE_ID)
            secs = _secs_of(ff, mp3) + TAIL
            subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", frame, "-i", mp3,
                            "-filter_complex", f"[1:a]apad=pad_dur={TAIL},aresample=44100[a];[0:v]{vf}[v]",
                            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "22", "-c:a", "aac", "-b:a", "128k", "-t", f"{secs:.2f}", clip],
                           check=True)
        else:
            secs = max(READ_FLOOR, len(sc["narration"]) / READ_CPS + READ_LEAD)
            subprocess.run([ff, "-y", "-loglevel", "error", "-loop", "1", "-i", frame,
                            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                            "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "22",
                            "-c:a", "aac", "-shortest", "-t", f"{secs:.2f}", clip], check=True)
        clips.append(clip)
        total += secs
    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        fh.writelines(f"file '{os.path.abspath(c)}'\n" for c in clips)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "1", "-i", out,
                    "-frames:v", "1", "-q:v", "3", out.rsplit(".", 1)[0] + ".jpg"], check=True)
    return round(total, 1)


def youtube_meta(items: list[dict], today: str) -> dict:
    """유튜브에 그대로 붙일 제목·설명. 업로드기가 생기면 이것을 읽는다."""
    d = datetime.fromisoformat(today)
    progs = [it["info"]["program"] or it["title"] for it in items]
    lines = [f"{d.month}월 {d.day}일 오늘 방송되는 프로그램을 피플로드가 미리 정리했습니다.", ""]
    for it in items:
        i = it["info"]
        lines.append(f"· {i['channel']} {i['program']} {i['when']}".strip())
    lines += ["", f"기사 전문 https://{DOMAIN}/ent/tv/",
              "방송사 보도자료를 바탕으로 피플로드가 정리했습니다. 나레이션은 AI 음성입니다."]
    return {"title": f"[오늘의 방송] {d.month}/{d.day} " + " · ".join(progs[:3])[:80],
            "description": "\n".join(lines),
            "tags": ["오늘의방송", "방송예고", "피플로드"] + [p.replace(" ", "") for p in progs[:5]]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="연예 오늘의 방송 영상")
    ap.add_argument("--out", default="public/video")
    ap.add_argument("--frames", default="")
    ap.add_argument("--script-only", action="store_true")
    ap.add_argument("--voiced", action="store_true")
    ap.add_argument("--silent", action="store_true")
    ap.add_argument("--today", default="")
    args = ap.parse_args(argv)

    today = args.today or datetime.now(KST).strftime("%Y-%m-%d")
    items = load_today(today=today)[:MAX_LONG]
    if len(items) < MIN_ITEMS:
        print(f"오늘의 방송 영상: 방송 기사가 {len(items)}편뿐이라 만들지 않는다.")
        return 0
    long_sc = script_long(items, today)
    shorts = [script_short(it) for it in items[:MAX_SHORTS]]
    print(f"오늘의 방송 {len(items)}편 · 롱폼 장면 {len(long_sc)} · 숏폼 {len(shorts)}편 "
          f"· 나레이션 {sum(len(s['narration']) for s in long_sc)}자")
    for s in long_sc:
        print(f"  {s['narration'][:80]}")
    if args.frames:
        os.makedirs(args.frames, exist_ok=True)
        for n, s in enumerate(long_sc):
            render_long(s).save(os.path.join(args.frames, f"tv_long_{n:02d}.png"))
        for k, sc in enumerate(shorts, 1):
            for n, s in enumerate(sc):
                render_short(s).save(os.path.join(args.frames, f"tv_short{k}_{n:02d}.png"))
    if args.script_only or not (args.voiced or args.silent):
        return 0

    stem = f"peopleroad-tv-{today.replace('-', '')}"
    voiced = args.voiced
    made = []
    jobs = [(long_sc, render_long, (1920, 1080), os.path.join(args.out, f"{stem}.mp4"))]
    jobs += [(sc, render_short, (1080, 1920), os.path.join(args.out, f"{stem}-{k}.mp4"))
             for k, sc in enumerate(shorts, 1)]
    # 오늘 이미 목소리로 구워 사이트에 올린 것은 다시 사지 않는다(크레딧, 2026-10-16).
    live = {}
    if args.voiced:
        from narrate import fetch_live, live_meta
        live = {v["file"]: v for v in ((live_meta(stem) or {}).get("videos") or [])
                if v.get("kind") == "voiced"}
    for scenes, render, size, out in jobs:
        name = os.path.basename(out)
        if name in live and fetch_live(name, args.out):
            made.append(live[name])
            print(f"  → {out} 오늘 구운 나레이션판을 다시 쓴다")
            continue
        try:
            secs = bake(scenes, render, size, out, voiced)
        except BaseException as e:       # 키 없음·API 오류(SystemExit)도 잡아 무음으로
            if not voiced:
                raise
            print(f"나레이션 실패 — 무음으로 만든다: {type(e).__name__}: {e}", file=sys.stderr)
            voiced = False
            secs = bake(scenes, render, size, out, False)
        made.append({"file": os.path.basename(out), "seconds": secs,
                     "kind": "voiced" if voiced else "silent"})
        print(f"  → {out} {secs}초 ({'나레이션' if voiced else '무음'})")
    meta = {"date": today, "videos": made, "youtube": youtube_meta(items, today),
            "articles": [it["id"] for it in items]}
    with open(os.path.join(args.out, f"{stem}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
