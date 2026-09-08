#!/usr/bin/env python3
"""와플트립 롱폼(16:9)을 만든다. 사진 없이 지면처럼 보이는 카드로 채운다.

사진이 모자라 만든 방식이 아니라, 뉴스 롱폼이 원래 쓰는 방식이다. 우리가
가진 것은 **글과 숫자**이고 그것을 읽기 좋게 짜면 화면이 된다. 사진은
들어오는 대로 섞어 쓴다(--photos).

한 주치 브리핑을 지역별로 묶어 3~5분으로 낸다. 숏폼이 한 지역 한 편이라면
롱폼은 "이번 주 여행 뉴스" 한 편이다.

    python tools/make_longform.py --script-only     # 대본만 (크레딧 0)
    python tools/make_longform.py --voice-id <id>   # 나레이션까지
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from src.models import REGION_NAMES  # noqa: E402
from video_brief import _speakable, facts_from, load_items  # noqa: E402


def _sentence(text: str, limit: int) -> str:
    """**완결된 문장**만 돌려준다. 잘릴 것 같으면 빈 값이다.

    글자 수로 자르면 "…항공기 6대를." 처럼 말이 끊긴 채 낭독된다. 읽는
    사람이 없는 영상에서 그건 그냥 틀린 문장이다. 자를 바에는 쓰지 않는다.
    """
    first = re.split(r"(?<=[.!?。])\s+", (text or "").strip())[0]
    first = _speakable(first, limit + 40)
    if not first or len(first) > limit:
        return ""
    return first

W, H = 1920, 1080
# 한글 폰트. 맥에서 만들고 리눅스(CI)에서도 만든다. 리눅스 러너에는 애플
# 폰트가 없고, PIL 의 기본 폰트는 한글을 못 그려 화면이 네모로 찬다.
# 그래서 있는 것을 골라 쓴다 — 없으면 만들지 않고 왜 못 만드는지 말한다.
_FONT_CANDIDATES = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",                 # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",     # Debian/Ubuntu
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
)


def _find_font() -> str:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return ""


FONT = _find_font()
PAD = 132

# 사이트와 같은 색을 쓴다. 영상만 다른 색이면 같은 매체로 보이지 않는다.
INK = (14, 14, 15)
PAPER = (250, 250, 249)
CORAL = (240, 78, 55)
MUTED = (110, 110, 115)
LINE = (225, 225, 220)

# 한 편에 담을 지역. 한국인이 많이 가는 곳부터.
ORDER = ["japan", "vietnam", "thailand", "taiwan", "jeju",
         "guam", "saipan", "hawaii", "kota", "laos"]
PER_REGION = 2          # 지역마다 기사 두 건. 더 넣으면 지루해진다.
MAX_REGIONS = 6


def _f(size: int, weight: int = 0):
    """한글 폰트를 연다. 없으면 조용히 넘어가지 않고 멈춘다.

    기본 폰트로 물러나면 한글이 전부 네모로 그려진 화면이 만들어진다.
    깨진 화면을 만드는 것보다 만들지 않는 편이 낫다.
    """
    if not FONT:
        raise RuntimeError(
            "한글 폰트를 찾지 못했다. 화면을 만들지 않는다.\n"
            "  우분투: sudo apt-get install -y fonts-noto-cjk")
    try:
        return ImageFont.truetype(FONT, size, index=weight)
    except OSError as e:
        raise RuntimeError(f"폰트를 열지 못했다: {FONT} — {e}") from e


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # 제호는 늘 같은 자리에. 어느 장면을 캡처해도 매체를 알 수 있어야 한다.
    brand = _f(34)
    d.text((PAD, 64), "와플트립", font=brand, fill=INK)
    d.text((PAD + d.textlength("와플트립", font=brand), 64), ".",
           font=brand, fill=CORAL)
    d.line([(PAD, H - 96), (W - PAD, H - 96)], fill=LINE, width=2)
    d.text((PAD, H - 78), "waffletrip.com", font=_f(26), fill=MUTED)
    return img, d


def card_title(headline: str, sub: str) -> Image.Image:
    img, d = _base()
    big = _f(96)
    lines = _wrap(d, headline, big, W - PAD * 2)[:3]
    y = H // 2 - len(lines) * 62 - 40
    for line in lines:
        d.text((PAD, y), line, font=big, fill=INK)
        y += 124
    d.text((PAD, y + 24), sub, font=_f(40), fill=MUTED)
    d.line([(PAD, y + 8), (PAD + 120, y + 8)], fill=CORAL, width=6)
    return img


def card_section(name: str, count: int) -> Image.Image:
    img, d = _base()
    d.text((PAD, H // 2 - 130), "지역", font=_f(34), fill=CORAL)
    d.text((PAD, H // 2 - 80), name, font=_f(140), fill=INK)
    d.text((PAD, H // 2 + 96), f"이번 주 {count}건", font=_f(42), fill=MUTED)
    return img


def card_story(headline: str, summary: str, outlet: str, n: int,
               total: int) -> Image.Image:
    img, d = _base()
    d.text((PAD, 190), f"{n:02d} / {total:02d}", font=_f(32), fill=CORAL)
    head = _f(64)
    lines = _wrap(d, headline, head, W - PAD * 2)[:3]
    y = 260
    for line in lines:
        d.text((PAD, y), line, font=head, fill=INK)
        y += 86
    if summary:
        y += 26
        body = _f(40)
        for line in _wrap(d, summary, body, W - PAD * 2)[:4]:
            d.text((PAD, y), line, font=body, fill=MUTED)
            y += 58
    if outlet:
        d.text((PAD, H - 190), f"출처 · {outlet}", font=_f(32), fill=MUTED)
    return img


def card_data(rows: list[tuple[str, str]]) -> Image.Image:
    img, d = _base()
    d.text((PAD, 190), "오늘의 데이터", font=_f(34), fill=CORAL)
    d.text((PAD, 240), "환율과 날씨는 저희가 매일 직접 만듭니다",
           font=_f(40), fill=MUTED)
    y = 370
    for name, value in rows[:7]:
        d.text((PAD, y), name, font=_f(48), fill=INK)
        d.text((PAD + 300, y + 6), value, font=_f(42), fill=MUTED)
        d.line([(PAD, y + 74), (W - PAD, y + 74)], fill=LINE, width=2)
        y += 96
    return img


def build_script(items: list[dict]) -> list[dict]:
    """한 주치 브리핑에서 롱폼 대본을 짠다. 사실은 전부 기사에서 온다."""
    roundups = [i for i in items
                if i.get("grade") == "C"
                and (i.get("title") or "").startswith("이번 주 ")
                and (i.get("body_md") or "").strip()]
    by_region: dict[str, dict] = {}
    for item in roundups:
        # 지역면 브리핑을 쓴다. 도시 브리핑은 그 안에 이미 담겨 있다.
        name = item["title"].replace("이번 주 ", "").split("에서")[0]
        if name != REGION_NAMES.get(item.get("region", ""), ""):
            continue
        by_region.setdefault(item["region"], item)

    scenes: list[dict] = []
    today = max((i.get("published_at") or "")[:10] for i in items)
    scenes.append({
        "kind": "title",
        "narration": "안녕하세요, 와플트립입니다. 이번 주 여행 뉴스를 정리해 드립니다.",
        "headline": "이번 주 여행 뉴스",
        "sub": f"{today[:4]}년 {int(today[5:7])}월 {int(today[8:10])}일 · 와플트립",
    })

    facts_rows = []
    for region in ORDER:
        for item in items:
            if (item.get("grade") == "A" and item.get("region") == region
                    and "환율" in (item.get("title") or "")):
                value = (item.get("summary") or "").strip()
                # "2026-09-03 기준 100 JPY = 약 855원" 에서 날짜를 뗀다.
                # 화면에는 오늘 값만 걸리므로 날짜를 읽어줄 이유가 없다.
                value = re.sub(r"^\d{4}-\d{2}-\d{2}\s*기준\s*", "", value)
                if value:
                    facts_rows.append((REGION_NAMES.get(region, region), value))
                break
    if facts_rows:
        spoken = ", ".join(f"{n}은 {v}" for n, v in facts_rows[:3])
        scenes.append({
            "kind": "data", "rows": facts_rows,
            "narration": f"먼저 오늘의 환율입니다. {spoken}. "
                         "환율과 날씨는 저희가 매일 직접 만드는 값입니다.",
        })

    used = 0
    for region in ORDER:
        item = by_region.get(region)
        if not item or used >= MAX_REGIONS:
            continue
        name = REGION_NAMES.get(region, region)
        facts = [f for f in facts_from(item, focus=name)][:PER_REGION]
        if not facts:
            continue
        used += 1
        scenes.append({
            "kind": "section", "name": name, "count": len(facts),
            "narration": f"{name} 소식입니다.",
        })
        for n, fact in enumerate(facts, 1):
            # 요약이 한 문장으로 끝나면 그걸 읽고, 아니면 제목을 읽는다.
            # 제목은 원래 한 덩어리라 중간에서 끊기지 않는다.
            line = _sentence(fact["summary"], 100) or _speakable(
                fact["headline"], 100)
            if not line:
                continue
            cite = f"{fact['outlet']} 보도" if fact["outlet"] else "현지 보도"
            scenes.append({
                "kind": "story", "n": n, "total": len(facts),
                "headline": _speakable(fact["headline"], 60),
                "summary": _speakable(fact["summary"], 150),
                "outlet": fact["outlet"],
                "narration": f"{line}. {cite}입니다.",
            })

    scenes.append({
        "kind": "title",
        "headline": "매일 아침 8시",
        "sub": "waffletrip.com",
        "narration": "와플트립은 매일 아침 여덟 시에 새 기사를 올립니다. "
                     "waffletrip.com 에서 보실 수 있습니다.",
    })
    return scenes


def render(scene: dict) -> Image.Image:
    kind = scene["kind"]
    if kind == "title":
        return card_title(scene["headline"], scene["sub"])
    if kind == "section":
        return card_section(scene["name"], scene["count"])
    if kind == "data":
        return card_data(scene["rows"])
    return card_story(scene["headline"], scene.get("summary", ""),
                      scene.get("outlet", ""), scene["n"], scene["total"])


def main() -> int:
    ap = argparse.ArgumentParser(description="와플트립 롱폼")
    ap.add_argument("--script-only", action="store_true")
    ap.add_argument("--out", default="public/video")
    ap.add_argument("--frames", default="")
    args = ap.parse_args()

    scenes = build_script(load_items())
    chars = sum(len(s["narration"]) for s in scenes)
    print(f"장면 {len(scenes)}개 · 나레이션 {chars}자 · 예상 {chars // 6}초")
    for n, s in enumerate(scenes, 1):
        print(f"  [{n:02d}] {s['kind']:8} {s['narration'][:64]}")

    if args.frames:
        os.makedirs(args.frames, exist_ok=True)
        for n, s in enumerate(scenes):
            render(s).save(os.path.join(args.frames, f"s{n:02d}.png"))
        print(f"화면 {len(scenes)}장 → {args.frames}")

    with open(os.path.join(args.out if not args.script_only else ".",
                           "longform_script.json"), "w", encoding="utf-8") as fh:
        json.dump(scenes, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def assemble(frames_dir: str, audio_dir: str, out_path: str) -> str:
    """장면 그림과 나레이션을 이어 붙인다. 정지 화면이라 인코딩이 가볍다.

    장면마다 나레이션 길이에 맞춰 화면을 띄우고, 앞뒤로 숨 쉴 틈을 조금 준다.
    말이 끝나자마자 다음 장면으로 넘어가면 쫓기는 느낌이 든다.
    """
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tail = 0.55                     # 문장 끝에 두는 여백(초)
    clips = []
    work = os.path.dirname(out_path) or "."
    tmp = os.path.join(work, "_lf")
    os.makedirs(tmp, exist_ok=True)

    frames = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    for n, frame in enumerate(frames):
        wav = os.path.join(audio_dir, f"a{n:02d}.wav")
        if not os.path.exists(wav):
            continue
        probe = subprocess.run([ff, "-i", wav], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
        secs = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                + float(m.group(3))) if m else 4.0
        secs += tail
        clip = os.path.join(tmp, f"c{n:02d}.mp4")
        subprocess.run([
            ff, "-y", "-loglevel", "error",
            "-loop", "1", "-i", os.path.join(frames_dir, frame),
            "-i", wav,
            "-filter_complex",
            f"[1:a]apad=pad_dur={tail}[a];"
            f"[0:v]scale={W}:{H},format=yuv420p,fps=25[v]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-t", f"{secs:.2f}", clip,
        ], check=True)
        clips.append(clip)

    listing = os.path.join(tmp, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for clip in clips:
            fh.write(f"file '{os.path.abspath(clip)}'\n")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out_path], check=True)
    poster = out_path.rsplit(".", 1)[0] + ".jpg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "1", "-i", out_path,
                    "-frames:v", "1", "-q:v", "3", poster], check=True)
    return out_path
