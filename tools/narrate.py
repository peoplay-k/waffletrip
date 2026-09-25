#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""장면 나레이션을 일레븐랩스로 만든다.

사장님 계정이 직접 붙어 있어 **크레딧이 들지 않는다**(Creator 플랜, 월 30만 자).
숏폼 한 편이 200자 안팎, 롱폼이 1,500자 안팎이라 둘 다 매일 돌려도 한도의
1/6 쯤 쓴다.

목소리는 **브랜드 자산**이다. 온리·유나 목소리를 피플로드에 쓰면 브랜드가
섞인다(docs 의 voice-per-brand 규칙). 피플로드은 아래 하나로 고정한다.

    python3 tools/narrate.py --text "읽을 문장" --out a.mp3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.elevenlabs.io/v1/text-to-speech"

# "뉴스 리포터" 여자 톤 — 신문 매체에 맞는다. 바꾸려면 여기만 고친다.
VOICE_ID = os.environ.get("WAFFLETRIP_VOICE_ID", "3AoqIoDy7aCSniSEoQRO")
VOICE_NAME = "뉴스 리포터"
MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75,
            "style": 0.0, "use_speaker_boost": True}


def speak(text: str, out_path: str) -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("[중단] ELEVENLABS_API_KEY 가 없습니다.")
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": SETTINGS}).encode()
    req = urllib.request.Request(
        f"{API}/{VOICE_ID}", data=body,
        headers={"xi-api-key": key, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            audio = r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[중단] 일레븐랩스 {e.code} — {e.read().decode()[:300]}")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(audio)
    return out_path


def remaining() -> tuple[int, int]:
    """남은 글자 수. 한도에 가까우면 만들지 않는 편이 낫다."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/user/subscription",
        headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    return d.get("character_count", 0), d.get("character_limit", 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    used, limit = remaining()
    print(f"목소리 {VOICE_NAME} · 이번 달 {used:,}/{limit:,}자")
    print(" →", speak(args.text, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
