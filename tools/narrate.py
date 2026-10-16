#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""장면 나레이션을 일레븐랩스로 만든다.

사장님 계정이 직접 붙어 있어 **크레딧이 들지 않는다**(Creator 플랜, 월 30만 자).
숏폼 한 편이 200자 안팎, 롱폼이 1,500자 안팎이라 둘 다 매일 돌려도 한도의
1/6 쯤 쓴다.

목소리는 **브랜드 자산**이다. 온리·유나 목소리를 피플로드에 쓰면 브랜드가
섞인다(docs 의 voice-per-brand 규칙). 피플로드는 아래 하나로 고정한다.

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
# 연예 영상 목소리 — 여행과 갈라 둔다(2026-10-16 사장님: "AI 남자 성우로").
# 일레븐랩스 공유 목소리 'MJ - Calm, Clear, Versatile'. 한국어 남성, 롱폼 해설용.
ENT_VOICE_ID = os.environ.get("PEOPLEROAD_ENT_VOICE_ID", "l6fNdLYgoqjfTIPUeFc9")
ENT_VOICE_NAME = "MJ"
MODEL = "eleven_multilingual_v2"
SETTINGS = {"stability": 0.5, "similarity_boost": 0.75,
            "style": 0.0, "use_speaker_boost": True}


def speak(text: str, out_path: str, voice_id: str | None = None) -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise SystemExit("[중단] ELEVENLABS_API_KEY 가 없습니다.")
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": SETTINGS}).encode()
    req = urllib.request.Request(
        f"{API}/{voice_id or VOICE_ID}", data=body,
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


# ── 같은 날 다시 굽지 않기 ─────────────────────────────────────────
#
# 2026-10-16 크레딧이 바닥났다(월 29만 자). 발행은 하루에 두세 번 돈다 — 아침 예약,
# 해설이 올라온 뒤, 사람이 손으로 돌린 것. 돌 때마다 같은 영상에 나레이션을 새로
# 샀다. 오늘 이미 목소리를 얹어 사이트에 올린 영상이 있으면 그것을 내려받아 쓴다.
def _site_video() -> str:
    # 부를 때 읽는다 — 테스트가 사이트에 나가지 않게 바꿔 끼운다.
    return os.environ.get("PEOPLEROAD_VIDEO_BASE", "https://waffletrip.com/video")


def _get(url: str, timeout: int = 60) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "peopleroad-build"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def live_meta(stem: str) -> dict | None:
    raw = _get(f"{_site_video()}/{stem}.json", 20)
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


def fetch_live(name: str, out_dir: str) -> bool:
    """사이트에 걸린 mp4 와 포스터 jpg 를 out_dir 로 받는다. 둘 다 받아야 True."""
    stem = name.rsplit(".", 1)[0]
    got = {}
    for ext in ("mp4", "jpg"):
        data = _get(f"{_site_video()}/{stem}.{ext}")
        if not data:
            return False
        got[ext] = data
    os.makedirs(out_dir, exist_ok=True)
    for ext, data in got.items():
        with open(os.path.join(out_dir, f"{stem}.{ext}"), "wb") as fh:
            fh.write(data)
    return True


def reuse_today(stem: str, out_dir: str, today: str) -> bool:
    """오늘 목소리로 구운 같은 영상이 사이트에 있으면 받아 쓴다(메타 json 도 함께).

    판단 기준: 메타의 kind 가 voiced 이고, built_at 이 오늘이거나 이름에 오늘 날짜가 있다.
    """
    meta = live_meta(stem)
    if not meta or meta.get("kind") != "voiced":
        return False
    built = str(meta.get("built_at") or "")
    if not (built.startswith(today) or today.replace("-", "") in stem):
        return False
    if not fetch_live(stem + ".mp4", out_dir):
        return False
    with open(os.path.join(out_dir, f"{stem}.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return True


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
