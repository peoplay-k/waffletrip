#!/usr/bin/env python3
"""와플트립 숏폼을 만든다. 유료 도구를 쓰지 않는다.

- 나레이션: macOS 내장 음성(`say`). AI 음성 크레딧을 쓰지 않는다.
- 화면: 우리가 직접 찍은 사진 + 자막. 남의 영상·이미지는 0컷이다.
- 조립: ffmpeg(파이썬 패키지에 딸려 온 바이너리). 설치비도 사용료도 없다.

**사진은 한 번 쓰면 끝이다.** 영상에 쓴 사진은 사용 이력에 남겨 기사에
다시 나가지 않게 한다. 같은 사진이 여러 곳에 반복되면 유사문서로 처리돼
검색에서 양쪽 다 손해를 본다.

    python tools/make_video.py --region guam
    python tools/make_video.py --region guam --voice Yuna --out public/video
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402
import imageio_ffmpeg  # noqa: E402

from src.photos import USED, load_manifest, web_path  # noqa: E402
from video_brief import load_items, script_for  # noqa: E402

W, H = 1080, 1920          # 9:16 세로. 릴스·쇼츠·틱톡이 모두 이 비율이다.
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
FPS = 30
PAD = 72
SAFE_BOTTOM = 380          # 세 플랫폼 모두 아래쪽에 UI 를 덮어 씌운다.


def _font(size: int):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    """어절 단위로 접는다. 한글은 글자 중간에서 끊으면 읽기 어렵다."""
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


def compose(photo: str | None, caption: str, index: int, total: int) -> Image.Image:
    """한 장면. 사진을 꽉 채우고 아래를 어둡게 깔아 자막을 얹는다."""
    canvas = Image.new("RGB", (W, H), (14, 14, 15))
    if photo and os.path.exists(photo):
        src = Image.open(photo).convert("RGB")
        scale = max(W / src.width, H / src.height)
        src = src.resize((round(src.width * scale), round(src.height * scale)),
                         Image.LANCZOS)
        canvas.paste(src, ((W - src.width) // 2, (H - src.height) // 2))

    # 아래 절반을 어둡게 두 단으로 깐다. 사진 위 흰 글씨는 그냥 두면 안 읽힌다.
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for n in range(H // 2, H):
        ratio = (n - H // 2) / (H / 2)
        sd.line([(0, n), (W, n)], fill=(0, 0, 0, int(20 + 205 * ratio ** 1.4)))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), shade).convert("RGB")

    draw = ImageDraw.Draw(canvas)
    body = _font(62)
    lines: list[str] = []
    for chunk in caption.split("\n"):
        lines += _wrap(draw, chunk, body, W - PAD * 2)
    lines = lines[:4]
    y = H - SAFE_BOTTOM - len(lines) * 84
    for line in lines:
        draw.text((PAD, y), line, font=body, fill=(255, 255, 255))
        y += 84

    # 제호와 장면 번호. 어느 매체인지 화면에서 바로 보여야 한다.
    brand = _font(40)
    draw.text((PAD, 84), "와플트립", font=brand, fill=(255, 255, 255))
    dot_x = PAD + draw.textlength("와플트립", font=brand)
    draw.text((dot_x, 84), ".", font=brand, fill=(240, 78, 55))
    small = _font(30)
    tag = f"{index}/{total}"
    draw.text((W - PAD - draw.textlength(tag, font=small), 92), tag,
              font=small, fill=(200, 200, 200))
    return canvas


def narrate(text: str, voice: str, path: str) -> float:
    """macOS 내장 음성으로 읽어 파일로 남기고 길이를 돌려준다."""
    aiff = path + ".aiff"
    subprocess.run(["say", "-v", voice, "-o", aiff, text], check=True)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", aiff,
                    "-ar", "48000", "-ac", "1", path], check=True)
    out = subprocess.run(
        [ff, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out.stderr)
    os.remove(aiff)
    if not m:
        return 4.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def photos_for(region: str, count: int) -> list[str]:
    """그 지역의 **아직 쓰지 않은** 사진. 모자라면 모자란 대로 돌려준다."""
    manifest = load_manifest()
    used = json.load(open(USED, encoding="utf-8")) if os.path.exists(USED) else {}
    free = [p for p in manifest.get(region, [])
            if web_path(p["file"]) not in used]
    return [p["file"] for p in free[:count]]


def mark_used(files: list[str], video_id: str) -> None:
    """영상에 쓴 사진을 사용 이력에 남긴다. 기사에 다시 나가면 안 된다."""
    used = json.load(open(USED, encoding="utf-8")) if os.path.exists(USED) else {}
    for f in files:
        used.setdefault(web_path(f), f"video:{video_id}")
    os.makedirs(os.path.dirname(USED), exist_ok=True)
    with open(USED, "w", encoding="utf-8") as fh:
        json.dump(used, fh, ensure_ascii=False, indent=0)


def build(region: str, voice: str, out_dir: str, keep_photos: bool) -> str:
    items = load_items()
    pool = [i for i in items
            if i.get("grade") == "C" and (i.get("body_md") or "").strip()
            and i.get("region") == region]
    if not pool:
        raise SystemExit(f"{region} 에 영상으로 만들 자체 생산 기사가 없다.")
    pool.sort(key=lambda i: i.get("published_at") or "", reverse=True)
    script = script_for(pool[0])
    scenes = script["scenes"]

    shots = photos_for(region, len(scenes))
    if not shots:
        raise SystemExit(f"{region} 에 아직 쓰지 않은 사진이 없다. "
                         "사진 없이 영상을 만들지 않는다.")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    work = tempfile.mkdtemp(prefix="waffle-video-")
    parts, audios = [], []
    total = len(scenes)
    for n, scene in enumerate(scenes):
        photo = shots[n % len(shots)]
        frame = os.path.join(work, f"f{n:02d}.png")
        compose(photo, scene.get("screen") or scene["caption"],
                n + 1, total).save(frame)
        wav = os.path.join(work, f"a{n:02d}.wav")
        seconds = max(2.4, narrate(scene["narration"], voice, wav) + 0.35)
        clip = os.path.join(work, f"c{n:02d}.mp4")
        # 느린 줌. 정지 사진만 이어 붙이면 슬라이드쇼로 보인다.
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-loop", "1", "-i", frame,
            "-i", wav,
            "-filter_complex",
            f"[0:v]scale={W*2}:-2,zoompan=z='min(zoom+0.0012,1.12)'"
            f":d={int(seconds*FPS)}:s={W}x{H}:fps={FPS},format=yuv420p[v]",
            "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
            "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-shortest", clip,
        ], check=True)
        parts.append(clip)
        audios.append(wav)

    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for clip in parts:
            fh.write(f"file '{clip}'\n")
    os.makedirs(out_dir, exist_ok=True)
    name = f"{region}-{script['source_title'][:0] or ''}week.mp4".replace(" ", "")
    out = os.path.join(out_dir, name)
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out], check=True)

    if not keep_photos:
        mark_used(shots, name)
    meta = out.rsplit(".", 1)[0] + ".json"
    with open(meta, "w", encoding="utf-8") as fh:
        json.dump({"title": script["source_title"], "region": region,
                   "seconds": script["seconds"], "photos": shots,
                   "outlets": script["outlets"]}, fh, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="와플트립 숏폼 (무료 도구만)")
    ap.add_argument("--region", default="guam")
    ap.add_argument("--voice", default="Yuna")
    ap.add_argument("--out", default="public/video")
    ap.add_argument("--keep-photos", action="store_true",
                    help="사진을 사용 이력에 남기지 않는다(시험용)")
    args = ap.parse_args()
    path = build(args.region, args.voice, args.out, args.keep_photos)
    size = os.path.getsize(path) / 1e6
    print(f"만들었다: {path} ({size:.1f}MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
