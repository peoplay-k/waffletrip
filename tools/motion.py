#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""정지 화면에 느린 줌을 거는 ffmpeg 필터 — 쇼츠·주간 롱폼·오늘의 방송이 함께 쓴다.

사진이나 카드가 멈춘 채 넘어가면 슬라이드쇼 — 자동으로 만든 티가 가장 많이 난다
(2026-11-14 사장님 "사람이 만든 것처럼"). 장면마다 다가가기·물러나기를 번갈아 건다.
첫 장면(n=0)은 1배에서 시작하므로 첫 화면이 표지와 똑같다.

입력은 **그림 한 장**(-loop 없이)이어야 한다. zoompan 이 그 한 장에서 d 프레임을 뽑는다.
2배로 키운 뒤 줌을 걸어야 소수점 좌표 반올림으로 화면이 떨리지 않는다.
"""
from __future__ import annotations


def motion_filter(n: int, secs: float, w: int, h: int, fps: int = 30,
                  zoom: float = 0.07, upscale: float = 2.0) -> str:
    frames = max(1, int(round(secs * fps)) + 2)
    step = zoom / frames
    if n % 2 == 0:
        z = f"min(1+{step:.7f}*on,{1 + zoom:.4f})"
    else:
        z = f"max({1 + zoom:.4f}-{step:.7f}*on,1)"
    uw, uh = int(w * upscale) // 2 * 2, int(h * upscale) // 2 * 2
    return (f"scale={uw}:{uh},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps},format=yuv420p")
