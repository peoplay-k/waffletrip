#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""피플로드 숏폼을 @waffletrip06 릴스로 올린다.

영상은 이미 waffletrip.com 에 공개로 올라가 있어 **인스타가 직접 받아간다.**
파일을 업로드하지 않으므로 맥이 꺼져 있어도 클라우드에서 돈다.

    python3 tools/publish_instagram.py               # 확인만(발행 안 함)
    python3 tools/publish_instagram.py --post        # 실제 발행

환경변수: WAFFLETRIP_IG_USER_ID, WAFFLETRIP_IG_ACCESS_TOKEN
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HOST = "https://graph.instagram.com"
VER = "v21.0"
KST = timezone(timedelta(hours=9))
SITE = "https://waffletrip.com"
VIDEO_DIR = os.path.join("static", "video")
POSTED = os.path.join("data", "instagram_posted.json")


def api(method: str, path: str, params: dict) -> dict:
    url = f"{HOST}/{VER}/{path}"
    data = urllib.parse.urlencode(params).encode()
    req = (urllib.request.Request(url, data=data)
           if method == "POST" else
           urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"[중단] {method} {path} — {e.read().decode()[:400]}")


def load_posted() -> dict:
    if os.path.exists(POSTED):
        with open(POSTED, encoding="utf-8") as fh:
            return json.load(fh)
    return {"posted": [], "log": []}


LATEST = os.path.join("data", "shorts_latest.json")


def pick(state: dict) -> dict | None:
    """오늘 구운 숏폼. 같은 것을 두 번 올리지 않는다.

    `data/shorts_latest.json` 을 먼저 본다. 발행 잡은 저장소를 새로 받아오는데
    `static/video` 의 숏폼 메타는 gitignore 라 거기엔 없다 — 그래서 빌드가
    글자만 담은 이 파일을 커밋해 둔다. 없으면 로컬 폴더를 훑는다(손으로 돌릴 때).
    """
    done = set(state.get("posted", []))

    if os.path.exists(LATEST):
        with open(LATEST, encoding="utf-8") as fh:
            meta = json.load(fh)
        stem = meta.get("stem", "")
        if stem and stem not in done:
            meta["video_url"] = f"{SITE}/video/{stem}.mp4"
            return meta
        return None

    if not os.path.isdir(VIDEO_DIR):
        return None
    for name in sorted(os.listdir(VIDEO_DIR)):
        if not name.endswith("-silent.json"):
            continue
        stem = name[: -len(".json")]
        if stem in done:
            continue
        with open(os.path.join(VIDEO_DIR, name), encoding="utf-8") as fh:
            meta = json.load(fh)
        if not os.path.exists(os.path.join(VIDEO_DIR, stem + ".mp4")):
            continue
        meta["stem"] = stem
        meta["video_url"] = f"{SITE}/video/{stem}.mp4"
        return meta
    return None


def posted_today(state: dict) -> str:
    """오늘(한국 날짜) 이미 올렸으면 그 시각. 안 올렸으면 빈 문자열.

    처음에는 "마지막 발행에서 18시간"으로 막았는데, 그게 매일 정해진 시각에
    도는 일정과 어긋난다. 2026-09-16 실측: 전날 17:14 에 나갔더니 이튿날
    10:05 회차가 **1.1시간 모자라** 건너뛰었고 그날은 한 편도 안 나갔다.
    깃허브 크론은 몇 시간씩 밀리므로 간격으로 재면 이런 날이 계속 생긴다.

    "하루 한 편"은 날짜로 세는 것이 맞다. 예비 크론이 같은 날 또 깨도
    막히고, 날이 바뀌면 시각과 무관하게 나간다.
    """
    today = datetime.now(KST).strftime("%Y-%m-%d")
    for row in reversed(state.get("log") or []):
        if (row.get("at") or "").startswith(today):
            return row["at"]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true", help="실제로 발행한다")
    args = ap.parse_args()

    uid = os.environ.get("WAFFLETRIP_IG_USER_ID", "").strip()
    tok = os.environ.get("WAFFLETRIP_IG_ACCESS_TOKEN", "").strip()
    if not uid or not tok:
        print("[중단] WAFFLETRIP_IG_USER_ID / WAFFLETRIP_IG_ACCESS_TOKEN 이 없습니다.",
              file=sys.stderr)
        return 1

    # ★계정을 확인하고 나서 올린다. 토큰이 바뀌어 엉뚱한 계정으로 나가면
    # 되돌릴 수 없다(다른 브랜드에서 실제로 났던 사고다).
    me = api("GET", "me", {"fields": "id,username", "access_token": tok})
    if me.get("username") != "waffletrip06":
        print(f"[중단] 토큰이 가리키는 계정이 waffletrip06 이 아닙니다: {me}",
              file=sys.stderr)
        return 1
    print(f"계정 확인 · @{me['username']}")

    state = load_posted()
    already = posted_today(state)
    if already:
        print(f"오늘 이미 올렸습니다({already}) — 하루 1편. 건너뜁니다.")
        return 0

    nxt = pick(state)
    if not nxt:
        print("올릴 숏폼이 없습니다 — 큐가 비었습니다.")
        return 0

    print(f"다음 편 · {nxt['stem']} ({nxt.get('seconds')}초)")
    print(f"  {nxt['video_url']}")
    print("  ── 캡션 ──")
    for line in (nxt.get("caption") or "").splitlines():
        print(f"  {line}")

    if not args.post:
        print("\n확인만 했습니다. 실제로 올리려면 --post 를 붙이세요.")
        return 0

    # 인스타가 받아갈 주소가 실제로 살아 있는지 먼저 본다. 배포가 늦어
    # 어제 파일이 걸려 있거나 404 면 여기서 멈추는 편이 낫다.
    try:
        req = urllib.request.Request(nxt["video_url"], method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as r:
            size = int(r.headers.get("Content-Length") or 0)
        print(f"  영상 확인 · {size // 1024}KB")
    except Exception as e:
        print(f"[중단] 영상 주소를 못 읽었습니다: {e}", file=sys.stderr)
        return 1

    c = api("POST", f"{uid}/media", {
        "media_type": "REELS", "video_url": nxt["video_url"],
        "caption": nxt.get("caption") or "", "access_token": tok,
    })
    cid = c["id"]
    print(f"  container_id={cid}")

    for i in range(30):                    # 인스타가 영상을 받아 처리할 때까지
        st = api("GET", cid, {"fields": "status_code", "access_token": tok})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise SystemExit(f"[중단] 인스타 영상 처리 실패: {st}")
        print(f"  처리 중… ({i + 1}/30)")
        time.sleep(10)
    else:
        raise SystemExit("[중단] 영상 처리 시간 초과")

    r = api("POST", f"{uid}/media_publish", {"creation_id": cid, "access_token": tok})
    print(f"[발행 완료] media_id={r['id']}")

    state.setdefault("posted", []).append(nxt["stem"])
    state.setdefault("log", []).append({
        "file": nxt["stem"], "media_id": r["id"],
        "at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
    })
    os.makedirs(os.path.dirname(POSTED), exist_ok=True)
    with open(POSTED, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    print("[기록 완료]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
