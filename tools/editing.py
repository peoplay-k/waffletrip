#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""장면 이어 붙이기(디졸브)와 배경음 깔기 — 쇼츠·주간 롱폼·오늘의 방송이 함께 쓴다.

2026-11-14 사장님: "디졸브 전환이랑 배경음 둘 다 넣어줘".
- 장면이 뚝 끊겨 넘어가면 자동 슬라이드처럼 보인다. 장면 사이를 짧게 겹쳐 넘긴다.
  나레이션 끝에는 이미 0.5초 남짓 숨(무음)을 붙여 두어서, 소리도 함께 겹쳐도
  말이 겹치지 않는다.
- 배경음은 bgm.py 가 직접 합성한다. 말할 때는 자동으로 작아지고(사이드체인 더킹)
  말이 쉬면 조금 올라온다.

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
BGM_DB = -21            # 배경음 기본 크기(말이 없을 때)


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


def add_bgm(ff: str, video: str, seed: int, db: float = BGM_DB) -> bool:
    """나레이션이 든 영상에 배경음을 깐다(제자리에서 바꾼다). 성공하면 True."""
    from bgm import write_wav
    work = tempfile.mkdtemp(prefix="bgm-")
    try:
        secs = duration(ff, video)
        if secs <= 0:
            return False
        wav = write_wav(os.path.join(work, "bgm.wav"), secs + 1, seed)
        out = os.path.join(work, "out.mp4")
        vol = 10 ** (db / 20)
        flt = (f"[1:a]volume={vol:.4f}[bg];"
               "[0:a]aformat=channel_layouts=stereo,asplit=2[voice][key];"
               "[bg][key]sidechaincompress=threshold=0.03:ratio=6:attack=30:release=600[duck];"
               "[voice][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]")
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", video, "-i", wav,
                        "-filter_complex", flt, "-map", "0:v", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
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
