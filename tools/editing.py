#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""장면 이어 붙이기(디졸브)와 배경음 깔기 — 쇼츠·주간 롱폼·오늘의 방송이 함께 쓴다.

2026-11-14 사장님: "디졸브 전환이랑 배경음 둘 다 넣어줘".
- 장면이 뚝 끊겨 넘어가면 자동 슬라이드처럼 보인다. 장면 사이를 짧게 겹쳐 넘긴다.
  나레이션 끝에는 이미 0.5초 남짓 숨(무음)을 붙여 두어서, 소리도 함께 겹쳐도
  말이 겹치지 않는다.
- 배경음은 assets/music/ 에 넣어 둔 음원에서 고른다(합성 음악은 기본으로 끈다).
  말할 때는 자동으로 작아지고(사이드체인 더킹) 말이 쉬면 조금 올라온다.

어느 단계든 실패하면 예전 방식(그냥 이어 붙이기·배경음 없음)으로 떨어진다 —
영상이 아예 안 나가는 것보다 낫다.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

FADE = 0.35             # 장면 사이 겹침(초)


def duration(ff: str, path: str) -> float:
    probe = subprocess.run([ff, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def _concat(ff: str, clips: list[str], out: str) -> None:
    work = tempfile.mkdtemp(prefix="join-")
    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for c in clips:
            fh.write(f"file '{os.path.abspath(c)}'\n")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out], check=True)


def join(ff: str, clips: list[str], out: str, audio: bool, fade: float = FADE,
         crf: str = "23") -> None:
    """장면 클립을 디졸브로 잇는다. 클립은 같은 크기·프레임률이어야 한다."""
    if len(clips) < 2:
        _concat(ff, clips, out)
        return
    try:
        durs = [duration(ff, c) for c in clips]
        if min(durs) <= fade * 2:
            raise ValueError("너무 짧은 장면")
        args = [ff, "-y", "-loglevel", "error"]
        for c in clips:
            args += ["-i", c]
        parts, v, a, offset = [], "[0:v]", "[0:a]", 0.0
        for i in range(1, len(clips)):
            offset += durs[i - 1] - fade
            parts.append(f"{v}[{i}:v]xfade=transition=fade:duration={fade}:offset={offset:.3f}[v{i}]")
            v = f"[v{i}]"
            if audio:
                parts.append(f"{a}[{i}:a]acrossfade=d={fade}:c1=tri:c2=tri[a{i}]")
                a = f"[a{i}]"
        args += ["-filter_complex", ";".join(parts), "-map", v]
        if audio:
            args += ["-map", a, "-c:a", "aac", "-b:a", "160k"]
        args += ["-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", out]
        subprocess.run(args, check=True)
    except Exception as e:      # noqa: BLE001 — 실패하면 그냥 이어 붙인다
        print(f"디졸브 실패 — 그냥 잇는다: {type(e).__name__}: {e}", file=sys.stderr)
        _concat(ff, clips, out)


MUSIC_DIR = os.path.join("assets", "music")
MUSIC_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac")


def music_tracks(kind: str = "", root: str = MUSIC_DIR) -> list[str]:
    """쓸 수 있는 음원. `assets/music/<kind>/` 가 있으면 거기서, 없으면 `assets/music/` 전체에서.

    2026-11-14 사장님: "음악이 너무 별로야… NAS 에 음악 있어, 거기에 맞는 음악 넣어서 하자".
    직접 합성한 음악은 그만 쓰고, 사장님이 넣어 둔 음원만 쓴다.
    """
    def scan(d: str, deep: bool) -> list[str]:
        out = []
        for base, _dirs, files in os.walk(d):
            for f in files:
                if f.lower().endswith(MUSIC_EXTS):
                    out.append(os.path.join(base, f))
            if not deep:
                break
        return sorted(out)
    if kind and os.path.isdir(os.path.join(root, kind)):
        got = scan(os.path.join(root, kind), True)
        if got:
            return got
    return scan(root, True) if os.path.isdir(root) else []


def add_bgm(ff: str, video: str, seed: int, kind: str = "", db: float = -27.0) -> bool:
    """나레이션이 든 영상에 배경음을 깐다(제자리에서 바꾼다). 성공하면 True.

    - 음원 크기가 제각각이라 먼저 크기를 고르게 맞춘다(loudnorm).
    - 말할 때는 자동으로 작아진다(사이드체인 더킹), 처음·끝은 스르르.
    - 곡이 영상보다 짧으면 이어 돌리고, 곡 안의 시작 지점을 영상마다 바꾼다.
    - 음원이 하나도 없으면 깔지 않는다. 합성 음악은 PEOPLEROAD_SYNTH_BGM=1 일 때만.
    """
    tracks = music_tracks(kind, MUSIC_DIR)
    work = tempfile.mkdtemp(prefix="bgm-")
    try:
        secs = duration(ff, video)
        if secs <= 0:
            return False
        if tracks:
            track = tracks[seed % len(tracks)]
            tdur = duration(ff, track)
            offset = (seed * 7.3) % max(1.0, tdur - min(secs, tdur) - 1) if tdur > 30 else 0.0
            src = ["-stream_loop", "-1", "-ss", f"{offset:.2f}", "-i", track]
            print(f"  배경음: {os.path.basename(track)} ({offset:.0f}초부터)")
        elif os.environ.get("PEOPLEROAD_SYNTH_BGM") == "1":
            from bgm import write_wav
            src = ["-i", write_wav(os.path.join(work, "bgm.wav"), secs + 1, seed)]
        else:
            print(f"  배경음 없음 — {MUSIC_DIR}/ 에 음원을 넣으면 깐다")
            return False
        out = os.path.join(work, "out.mp4")
        fade_out = max(0.0, secs - 2.5)
        flt = (f"[1:a]aresample=44100,aformat=channel_layouts=stereo,"
               f"loudnorm=I=-16:TP=-2:LRA=11,volume={db}dB,"
               f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out:.2f}:d=2.5[bg];"
               "[0:a]aresample=44100,aformat=channel_layouts=stereo,asplit=2[voice][key];"
               "[bg][key]sidechaincompress=threshold=0.02:ratio=5:attack=40:release=700[duck];"
               "[voice][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", video, *src,
                        "-filter_complex", flt, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", f"{secs:.3f}",
                        "-movflags", "+faststart", out], check=True)
        shutil.move(out, video)
        return True
    except Exception as e:      # noqa: BLE001
        print(f"배경음 실패 — 나레이션만 둔다: {type(e).__name__}: {e}", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def seed_of(name: str) -> int:
    """영상 이름(날짜 포함)으로 곡을 정한다 — 같은 날 다시 구워도 같은 곡."""
    return sum((i + 1) * ord(c) for i, c in enumerate(name)) % 100003
