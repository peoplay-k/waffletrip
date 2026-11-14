#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""배경음을 직접 합성한다 — 남의 음원을 쓰지 않으므로 저작권 걱정이 없다.

2026-11-14 사장님: "디졸브 전환이랑 배경음 둘 다 넣어줘". 저작권 없는 음원을 받아
쓰는 방법도 있지만 출처·라이선스를 매번 밝혀야 하고 유튜브 Content ID 오탐이 난다.
그래서 화음 진행(Ⅰ–Ⅵm–Ⅳ–Ⅴ)을 부드러운 패드와 가벼운 아르페지오로 직접 만든다.
영상마다 조(key)와 빠르기를 seed 로 바꿔 날마다 같은 곡이 되지 않게 한다.

나레이션 밑에 깔리는 소리라 작고 둥글게 만든다. 크기는 섞을 때(editing.add_bgm) 정한다.
"""
from __future__ import annotations

import random
import wave

import numpy as np

SR = 44100
# 장조 Ⅰ–Ⅵm–Ⅳ–Ⅴ 를 반음 단위로(근음 기준). 셋째 화음은 근음+3/4, +7.
PROGRESSIONS = [
    [(0, "M"), (9, "m"), (5, "M"), (7, "M")],      # Ⅰ Ⅵm Ⅳ Ⅴ
    [(0, "M"), (7, "M"), (9, "m"), (5, "M")],      # Ⅰ Ⅴ Ⅵm Ⅳ
    [(5, "M"), (7, "M"), (4, "m"), (9, "m")],      # Ⅳ Ⅴ Ⅲm Ⅵm
]


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tone(freq: float, n: int, bright: float = 0.25) -> np.ndarray:
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t)
            + bright * np.sin(2 * np.pi * 2 * freq * t)
            + bright * 0.4 * np.sin(2 * np.pi * 3 * freq * t))


def synth(seconds: float, seed: int = 0) -> np.ndarray:
    """seconds 길이의 스테레오(float, -1~1) 배경음."""
    rnd = random.Random(seed)
    key = 48 + rnd.choice([0, 2, 3, 5, 7, 8, 10])          # C3 근처 여러 조
    bpm = rnd.choice([72, 76, 80, 84])
    prog = rnd.choice(PROGRESSIONS)
    beat = 60.0 / bpm
    bar = beat * 4
    total = int(seconds * SR) + SR
    left = np.zeros(total)
    right = np.zeros(total)

    n_bars = int(seconds / bar) + 2
    for b in range(n_bars):
        root, quality = prog[b % len(prog)]
        third = 3 if quality == "m" else 4
        notes = [key + root, key + root + third, key + root + 7]
        start = int(b * bar * SR)
        length = int(bar * SR * 1.25)                       # 다음 마디와 살짝 겹쳐 이어지게
        if start >= total:
            break
        length = min(length, total - start)
        env = np.ones(length)
        a, r = int(0.6 * SR), int(0.9 * SR)
        env[:a] = np.linspace(0, 1, a)[:length] if a <= length else np.linspace(0, 1, length)
        if r < length:
            env[-r:] *= np.linspace(1, 0, r)
        pad = sum(_tone(_hz(m + 12), length, 0.15) for m in notes) / 3
        bass = _tone(_hz(key + root - 12), length, 0.1) * 0.6
        left[start:start + length] += (pad * 0.55 + bass * 0.5) * env
        right[start:start + length] += (pad * 0.55 + bass * 0.5) * env * 0.97

        # 가벼운 아르페지오(8분음표) — 소리가 멈춰 있지 않게
        pattern = [0, 1, 2, 1, 2, 1, 0, 2]
        for k, idx in enumerate(pattern):
            s = start + int(k * beat / 2 * SR)
            ln = int(beat * 1.6 * SR)
            if s >= total:
                break
            ln = min(ln, total - s)
            decay = np.exp(-np.arange(ln) / (0.35 * SR))
            note = _tone(_hz(notes[idx] + 24), ln, 0.3) * decay * 0.22
            pan = 0.35 + 0.3 * (idx / 2)
            left[s:s + ln] += note * (1 - pan)
            right[s:s + ln] += note * pan

    out = np.stack([left, right], axis=1)[: int(seconds * SR)]
    # 처음·끝을 부드럽게
    f = min(int(2.0 * SR), len(out) // 4)
    if f:
        out[:f] *= np.linspace(0, 1, f)[:, None]
        out[-f:] *= np.linspace(1, 0, f)[:, None]
    peak = np.max(np.abs(out)) or 1.0
    return out / peak * 0.8


def write_wav(path: str, seconds: float, seed: int = 0) -> str:
    data = (synth(seconds, seed) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path
