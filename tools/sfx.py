#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""효과음을 직접 합성한다 — 휙(장면 전환), 톡(상자가 튀어오를 때), 타닥(타이핑).

2026-11-15 사장님: "효과음도 좀 넣고 먼가 휙휙 나오고 정말 전문성 있게". 남의 효과음 팩은
출처·라이선스를 매번 따져야 해서, 짧은 소리라 직접 만든다(잡음 스윕·사인 블립).
소리는 작게 — 나레이션을 가리지 않는 '양념'이다.
"""
from __future__ import annotations

import random
import wave

import numpy as np

SR = 44100


def _svf_bandpass(x: np.ndarray, f0: np.ndarray, q: float = 0.7) -> np.ndarray:
    """시간에 따라 중심 주파수가 바뀌는 밴드패스(상태 변수 필터)."""
    low = band = 0.0
    out = np.empty_like(x)
    damp = 1.0 / q
    for i in range(len(x)):
        f = 2.0 * np.sin(np.pi * min(f0[i], SR / 6) / SR)
        high = x[i] - low - damp * band
        band += f * high
        low += f * band
        out[i] = band
    return out


def whoosh(dur: float = 0.42, lo: float = 300, hi: float = 3800, seed: int = 0) -> np.ndarray:
    """'휙' — 잡음이 낮은 데서 높은 데로 쓸려 올라갔다 사라진다. 왼쪽→오른쪽으로 지나간다."""
    rnd = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    f0 = lo * (hi / lo) ** (np.sin(np.pi * t * 0.9) ** 1.2)
    x = _svf_bandpass(rnd.standard_normal(n) * 0.5, f0, 0.9)
    env = np.sin(np.pi * t) ** 1.6 * (1 - 0.35 * t)
    mono = x * env
    mono /= np.max(np.abs(mono)) or 1
    pan = 0.15 + 0.7 * t
    return np.stack([mono * (1 - pan) * 1.3, mono * pan * 1.3], axis=1) * 0.7


def pop(freq: float = 520, dur: float = 0.12) -> np.ndarray:
    """'톡' — 높은 데서 떨어지는 짧은 블립 + 아주 짧은 클릭."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1.6 - 0.6 * np.minimum(1, t / 0.05))
    phase = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(phase) * np.exp(-t / 0.035)
    click = np.zeros(n)
    k = int(0.003 * SR)
    click[:k] = np.random.default_rng(1).standard_normal(k) * np.linspace(1, 0, k) * 0.4
    mono = (tone + click) * 0.8
    return np.stack([mono, mono], axis=1)


def tick(seed: int = 0) -> np.ndarray:
    """'타닥' — 자판 한 번. 짧은 고음 잡음."""
    rnd = random.Random(seed)
    n = int(0.022 * SR)
    noise = np.random.default_rng(seed).standard_normal(n)
    hp = np.diff(noise, prepend=0)                     # 낮은 소리를 덜어 딱딱하게
    env = np.exp(-np.arange(n) / (0.004 * SR))
    mono = hp * env * (0.25 + 0.1 * rnd.random())
    pan = 0.4 + 0.2 * rnd.random()
    return np.stack([mono * (1 - pan) * 2, mono * pan * 2], axis=1)


SOUNDS = {"whoosh": whoosh, "pop": pop, "tick": tick}
GAIN = {"whoosh": 0.55, "pop": 0.45, "tick": 0.5, "swish": 0.35}


def track(events: list[tuple[float, str]], seconds: float) -> np.ndarray:
    """(시각, 종류) 목록을 한 줄의 스테레오 소리로."""
    out = np.zeros((int(seconds * SR) + SR, 2))
    for k, (t, kind) in enumerate(sorted(events)):
        if kind == "whoosh":
            snd = whoosh(seed=k)
            t = t - 0.21          # 소리의 한가운데가 전환 순간에 오게
        elif kind == "swish":
            snd = whoosh(dur=0.26, lo=900, hi=5200, seed=k)
        elif kind == "pop":
            snd = pop(480 + 80 * (k % 3))
        else:
            snd = tick(k)
        i = max(0, int(t * SR))
        j = min(len(out), i + len(snd))
        if j > i:
            out[i:j] += snd[: j - i] * GAIN.get(kind, 0.4)
    return np.clip(out[: int(seconds * SR)], -1, 1)


def write_wav(path: str, events: list[tuple[float, str]], seconds: float) -> str:
    data = (track(events, seconds) * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path
