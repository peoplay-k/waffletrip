#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""피플로드 영상을 피플로드 유튜브(@peopleroad)에 올린다.

인스타 발행기(publish_instagram.py)와 같은 방식이다. 영상은 이미 waffletrip.com/video/
에 공개로 올라가 있으므로 거기서 받아 유튜브에 올린다. GitHub Actions 의 publish
잡에서 돈다(영상은 빌드 서버에만 있고 저장소에는 넣지 않는다).

    python3 tools/publish_youtube.py           # 무엇을 올릴지 보고만 한다
    python3 tools/publish_youtube.py --post    # 실제로 올린다

- 쇼츠: data/shorts_latest.json 의 오늘 숏폼(세로) → 유튜브 쇼츠. 같은 편은 두 번 안 올린다.
- 롱폼: video/peopleroad-week.json 의 주간 롱폼(가로) → 일반 영상. **7일에 한 번만**.
  롱폼은 매 실행마다 새로 굽히므로 매일 올리면 같은 주간 영상이 쌓인다.

★ 채널 확인: 토큰이 가리키는 채널이 @peopleroad(채널 ID UCkhVoG8C8OtKX60WpCpP99A, 2026-10-28
  사장님 확인 — "피플로드" 이름 채널이 둘이라 ID 로도 본다)
  이 아니면 **아무것도 올리지 않는다.** Kim 저장소의 브랜드 격리 규칙과 같은 취지다.

환경변수(GitHub 저장소 Secrets): WAFFLETRIP_YT_CLIENT_ID, WAFFLETRIP_YT_CLIENT_SECRET,
WAFFLETRIP_YT_REFRESH_TOKEN. 없으면 조용히 건너뛴다.

★ 2026-10-30 사장님 "와플트립 유튜브에도 같이" → 채널을 둘로 나눈다(사장님 선택 '둘 다 나눠서'):
  - 여행(쇼츠·주간 롱폼) → @peopleroad — 위 그대로.
  - 연예 '오늘의 방송'(롱폼 peopleroad-tv-YYYYMMDD.mp4 + 숏폼 -N.mp4) → @waffletrip(UCixhDwh_YbJqyB6SYiadRAA).
    그날 video/peopleroad-tv-YYYYMMDD.json 의 youtube 제목·설명·태그로 올린다. 하루 ENT_MAX_PER_DAY 편(기본 2 — 롱폼 1 + 숏폼 1).
    ★ OAuth 앱이 과미 유튜브(Kim 저장소)와 같아 하루 업로드 할당량(10,000)을 같이 쓴다 → 넉넉히 남기고, quotaExceeded 면 그날 멈춘다.
    인증: WAFFLETRIP_ENT_YT_REFRESH_TOKEN(+ 클라이언트는 WAFFLETRIP_ENT_YT_CLIENT_ID/SECRET, 없으면 여행 것과 같은 앱).
    없으면 조용히 건너뛴다. 채널 ID·핸들이 @waffletrip 이 아니면 아무것도 안 올린다.
    중복: 기록(data/youtube_posted.json, channel 'ent') + 그 채널 최근 업로드 제목 대조(못 읽으면 안 올림).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.brand import SITE_URL  # noqa: E402

KST = timezone(timedelta(hours=9))
POSTED = os.path.join("data", "youtube_posted.json")
LATEST = os.path.join("data", "shorts_latest.json")
LONGFORM_META_URL = f"{SITE_URL}/video/peopleroad-week.json"
LONGFORM_EVERY_DAYS = 7
HANDLE = os.environ.get("WAFFLETRIP_YT_HANDLE", "@peopleroad")
# 같은 이름 '피플로드' 채널이 유튜브에 둘 있다(@피플로드 는 남의 것). 핸들은 바뀔 수 있으니
# 바뀌지 않는 채널 ID 로도 확인한다.
CHANNEL_ID = os.environ.get("WAFFLETRIP_YT_CHANNEL_ID", "UCkhVoG8C8OtKX60WpCpP99A")
# ★ 2026-10-30 연예 채널
ENT_HANDLE = os.environ.get("WAFFLETRIP_ENT_YT_HANDLE", "@waffletrip")
ENT_CHANNEL_ID = os.environ.get("WAFFLETRIP_ENT_YT_CHANNEL_ID", "UCixhDwh_YbJqyB6SYiadRAA")
ENT_META_URL = f"{SITE_URL}/video/peopleroad-tv-{{ymd}}.json"
ENT_MAX_PER_DAY = int(os.environ.get("WAFFLETRIP_ENT_YT_MAX", "2") or 2)


class QuotaExceeded(RuntimeError):
    """유튜브 업로드 할당량을 다 썼다 — 그날은 더 올리지 않는다(과미와 같은 할당량)."""


class UploadUnknown(RuntimeError):
    """업로드 본체를 보낸 뒤 난 예외 — 영상이 만들어졌는지 모른다. 다시 올리지 않는다."""


# ── 기록 ────────────────────────────────────────────────────────────
def load_posted(path: str = POSTED) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("posted", [])
        return data
    except (OSError, ValueError):
        return {"posted": []}


def save_posted(state: dict, path: str = POSTED) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def already(state: dict, key: str) -> bool:
    return any(p.get("key") == key for p in state["posted"])


def last_longform_at(state: dict) -> datetime | None:
    times = [p.get("at") for p in state["posted"] if p.get("kind") == "longform" and p.get("at")]
    if not times:
        return None
    return max(datetime.fromisoformat(t) for t in times)


# ── 무엇을 올릴지 ─────────────────────────────────────────────────────
def _tags(caption: str) -> list[str]:
    return [t.lstrip("#") for t in re.findall(r"#[^\s#]+", caption)][:15]


def plan_short(state: dict, latest: dict | None) -> dict | None:
    if not latest or not latest.get("stem"):
        return None
    # @peopleroad 는 **여행** 채널이다. 연예 '오늘의 방송' 숏폼(peopleroad-tv-*)은 올리지 않는다.
    # 2026-10-28: 홀숫날 릴스용으로 연예 숏폼이 shorts_latest 에 들어가 여행 채널에 올라갔다.
    if latest["stem"].startswith("peopleroad-tv-") or latest.get("city") == "tv":
        return None
    key = f"short:{latest['stem']}"
    if already(state, key):
        return None
    caption = latest.get("caption") or ""
    first = caption.splitlines()[0].strip() if caption else f"{latest.get('name', '')} 이번 주 소식"
    body = caption.replace("전문은 waffletrip.com", f"전문은 {SITE_URL}")
    return {
        "key": key, "kind": "short",
        "url": f"{SITE_URL}/video/{latest['stem']}.mp4",
        "title": f"{first} #Shorts"[:100],
        "description": body[:4900],
        "tags": _tags(caption) or ["여행", "travel"],
    }


def plan_longform(state: dict, meta: dict | None, now: datetime) -> dict | None:
    if not meta or not meta.get("built_at"):
        return None
    if meta.get("kind") != "voiced":          # 목소리 없는 판은 올리지 않는다
        return None
    last = last_longform_at(state)
    if last and now - last < timedelta(days=LONGFORM_EVERY_DAYS):
        return None
    key = f"longform:{meta['built_at']}"
    if already(state, key):
        return None
    outlets = ", ".join(meta.get("outlets") or [])
    desc = (f"{meta.get('title', '이번 주 여행 뉴스')}\n\n"
            f"피플로드가 이번 주 여행 소식을 골라 정리했습니다. 전문은 {SITE_URL}\n"
            + (f"\n출처 · {outlets}\n" if outlets else "")
            + "\n#여행 #해외여행 #여행뉴스 #피플로드 #와플트립")
    return {
        "key": key, "kind": "longform",
        "url": f"{SITE_URL}/video/peopleroad-week.mp4",
        "title": f"{meta.get('title', '이번 주 여행 뉴스')} | 피플로드 주간 여행 뉴스"[:100],
        "description": desc[:4900],
        "tags": ["여행", "해외여행", "여행뉴스", "피플로드", "와플트립"],
    }


def ent_posted_today(state: dict, today: str) -> int:
    return sum(1 for p in state["posted"] if p.get("channel") == "ent" and str(p.get("at", "")).startswith(today))


def plan_ent(state: dict, meta: dict | None, now: datetime, limit: int | None = None) -> list[dict]:
    """연예 '오늘의 방송' 영상 → @waffletrip. 그날(KST) 만든 것만, 롱폼 먼저, 하루 limit 편까지."""
    limit = ENT_MAX_PER_DAY if limit is None else limit
    if not meta or meta.get("date") != now.date().isoformat():
        return []
    yt = meta.get("youtube") or {}
    base = (yt.get("title") or "").strip()
    if not base:
        return []
    left = limit - ent_posted_today(state, now.date().isoformat())
    vids = [v for v in meta.get("videos") or []
            if v.get("kind") == "voiced" and str(v.get("file", "")).endswith(".mp4")]
    vids.sort(key=lambda v: (bool(re.search(r"-\d{8}-\d+\.mp4$", v["file"])), v["file"]))   # 롱폼(가로) 먼저
    out = []
    for v in vids:
        if len(out) >= left:
            break
        stem = v["file"][:-4]
        key = f"ent:{stem}"
        if already(state, key):
            continue
        m = re.search(r"-\d{8}-(\d+)$", stem)        # 날짜 뒤 -N 이 숏폼(롱폼은 날짜로 끝난다)
        title = (f"{base[:84]} ({m.group(1)}) #Shorts" if m else base)[:100]
        out.append({"key": key, "kind": "ent_short" if m else "ent_longform", "channel": "ent",
                    "url": f"{SITE_URL}/video/{v['file']}", "title": title,
                    "description": (yt.get("description") or "")[:4900],
                    "tags": [str(t) for t in yt.get("tags") or [] if t][:15] or ["오늘의방송"]})
    return out


def _ent_creds() -> tuple[str, str, str] | None:
    ref = os.environ.get("WAFFLETRIP_ENT_YT_REFRESH_TOKEN", "")
    cid = os.environ.get("WAFFLETRIP_ENT_YT_CLIENT_ID", "") or os.environ.get("WAFFLETRIP_YT_CLIENT_ID", "")
    sec = os.environ.get("WAFFLETRIP_ENT_YT_CLIENT_SECRET", "") or os.environ.get("WAFFLETRIP_YT_CLIENT_SECRET", "")
    return (cid, sec, ref) if cid and sec and ref else None


def recent_titles(token: str, channel_id: str, n: int = 25) -> set[str] | None:
    """그 채널의 최근 업로드 제목 — 기록이 빠져도 같은 영상을 다시 올리지 않게. 못 읽으면 None(올리지 않는다)."""
    try:
        req = urllib.request.Request(
            f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            items = json.load(r).get("items") or []
        up = ((items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads") if items else None
        if not up:
            return set() if items else None
        req = urllib.request.Request(
            f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults={n}&playlistId={up}",
            headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return {((i.get("snippet") or {}).get("title") or "").strip() for i in json.load(r).get("items") or []}
    except (urllib.error.URLError, ValueError, OSError, KeyError, IndexError):
        return None


def post_ent(state: dict, plans: list[dict]) -> None:
    """연예 채널(@waffletrip)에 올린다. 무슨 일이 있어도 예외를 밖으로 내지 않는다(여행 쪽 기록 저장을 막지 않게)."""
    creds = _ent_creds()
    if not creds:
        print("유튜브(연예 @waffletrip): WAFFLETRIP_ENT_YT_* 시크릿이 없어 건너뛴다.")
        return
    try:
        token = access_token(*creds)
        handle, title = channel_handle(token, ENT_CHANNEL_ID)
    except Exception as e:  # noqa: BLE001
        print(f"유튜브(연예): 인증 실패 — 건너뛴다: {type(e).__name__}")
        return
    if not handle_ok(handle, ENT_HANDLE):
        print(f"[중단] 연예 토큰의 채널이 {ENT_HANDLE} 가 아니다 — {handle or '(핸들 없음)'} {title}. 연예 영상은 올리지 않는다.")
        return
    seen = recent_titles(token, ENT_CHANNEL_ID)
    if seen is None:
        print("유튜브(연예): 채널 최근 업로드를 못 읽어 중복을 확인할 수 없다 — 올리지 않는다.")
        return
    for p in plans:
        if p["title"].strip() in seen:
            print(f"  · 이미 채널에 같은 제목이 있다 — 건너뜀: {p['title']}")
            state["posted"].append({"key": p["key"], "kind": p["kind"], "channel": "ent", "title": p["title"],
                                    "at": datetime.now(KST).isoformat(timespec="seconds"), "video_id": "already_on_channel"})
            save_posted(state)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.mp4")
            try:
                urllib.request.urlretrieve(p["url"], path)
            except (urllib.error.URLError, OSError) as e:
                print(f"  ✗ 영상을 못 받음({type(e).__name__}) — 건너뜀: {p['url']}")
                continue
            entry = {"key": p["key"], "kind": p["kind"], "channel": "ent", "title": p["title"],
                     "at": datetime.now(KST).isoformat(timespec="seconds")}
            try:
                entry["video_id"] = upload(token, path, p)
                print(f"  ✓ 연예 올림 https://youtu.be/{entry['video_id']}")
            except QuotaExceeded:
                print("  ⏸ 유튜브 업로드 할당량을 다 썼다(과미와 같은 할당량) — 오늘 연예 업로드는 멈춘다.")
                return
            except UploadUnknown as e:
                entry["video_id"] = "unknown"
                entry["error"] = str(e)[:200]
                print(f"  ? 결과 불명 — 채널에서 직접 확인 전까지 다시 올리지 않는다: {e}")
            except Exception as e:  # noqa: BLE001 — 본체 전 오류: 안 만들어졌다
                print(f"  ✗ 연예 업로드 실패({type(e).__name__}) — 다음 실행에 다시")
                continue
            state["posted"].append(entry)
            save_posted(state)


# ── 유튜브 API ──────────────────────────────────────────────────────
def _creds() -> tuple[str, str, str] | None:
    cid = os.environ.get("WAFFLETRIP_YT_CLIENT_ID", "")
    sec = os.environ.get("WAFFLETRIP_YT_CLIENT_SECRET", "")
    ref = os.environ.get("WAFFLETRIP_YT_REFRESH_TOKEN", "")
    return (cid, sec, ref) if cid and sec and ref else None


def access_token(cid: str, sec: str, ref: str) -> str:
    body = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "refresh_token": ref,
                                   "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body, timeout=60) as r:
        return json.load(r)["access_token"]


def channel_handle(token: str, want_id: str | None = None) -> tuple[str, str]:
    want_id = want_id or CHANNEL_ID
    req = urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.load(r).get("items") or []
    if not items:
        return "", ""
    if items[0].get("id") != want_id:
        return "", f"(다른 채널 {items[0].get('id')})"
    sn = items[0].get("snippet") or {}
    return (sn.get("customUrl") or "").strip(), sn.get("title", "")


def handle_ok(handle: str, want: str = HANDLE) -> bool:
    norm = lambda h: h.strip().lower().lstrip("@")
    return bool(handle) and norm(handle) == norm(want)


def upload(token: str, path: str, plan: dict) -> str:
    meta = {"snippet": {"title": plan["title"], "description": plan["description"],
                        "tags": plan["tags"], "categoryId": "19", "defaultLanguage": "ko"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
    size = os.path.getsize(path)
    req = urllib.request.Request(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        data=json.dumps(meta).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            session = r.headers["Location"]
    except urllib.error.HTTPError as e:           # 본체를 보내기 전 — 안 만들어졌다
        body = e.read().decode("utf-8", "replace") if hasattr(e, "read") else ""
        if e.code == 403 and "quota" in body.lower():
            raise QuotaExceeded(body[:200]) from e
        raise
    try:
        with open(path, "rb") as fh:
            put = urllib.request.Request(session, data=fh.read(), method="PUT",
                                         headers={"Content-Type": "video/mp4"})
            with urllib.request.urlopen(put, timeout=600) as r:
                return json.load(r)["id"]
    except Exception as e:  # 본체를 보낸 뒤 — 결과 불명
        raise UploadUnknown(str(e)) from e


def _fetch_json(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except (urllib.error.URLError, ValueError, OSError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args(argv)

    state = load_posted()
    latest = None
    if os.path.exists(LATEST):
        with open(LATEST, encoding="utf-8") as fh:
            latest = json.load(fh)
    now = datetime.now(KST)
    plans = [p for p in (plan_short(state, latest),
                         plan_longform(state, _fetch_json(LONGFORM_META_URL), now)) if p]
    ent_plans = plan_ent(state, _fetch_json(ENT_META_URL.format(ymd=now.strftime("%Y%m%d"))), now)
    if not plans and not ent_plans:
        print("유튜브: 새로 올릴 영상이 없다.")
        return 0
    for p in plans:
        print(f"유튜브 후보 [{p['kind']}] {p['title']}\n  {p['url']}")
    for p in ent_plans:
        print(f"유튜브 연예 후보(@waffletrip) [{p['kind']}] {p['title']}\n  {p['url']}")
    if not args.post:
        print("확인만 했다(--post 를 주면 올린다).")
        return 0
    rc = 0
    if plans:
        rc = post_travel(state, plans)
    if ent_plans:
        post_ent(state, ent_plans)
    return rc


def post_travel(state: dict, plans: list[dict]) -> int:
    creds = _creds()
    if not creds:
        print("유튜브: WAFFLETRIP_YT_* 시크릿이 없어 건너뛴다.")
        return 0

    token = access_token(*creds)
    handle, title = channel_handle(token)
    if not handle_ok(handle):
        print(f"[중단] 토큰의 채널이 {HANDLE} 가 아니다 — {handle or '(핸들 없음)'} {title}. 아무것도 올리지 않는다.")
        return 1

    for p in plans:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "v.mp4")
            urllib.request.urlretrieve(p["url"], path)
            entry = {"key": p["key"], "kind": p["kind"], "title": p["title"],
                     "at": datetime.now(KST).isoformat(timespec="seconds")}
            try:
                entry["video_id"] = upload(token, path, p)
                print(f"  ✓ 올림 https://youtu.be/{entry['video_id']}")
            except QuotaExceeded:
                print("  ⏸ 유튜브 업로드 할당량을 다 썼다 — 오늘은 더 올리지 않는다.")
                return 0
            except UploadUnknown as e:
                entry["video_id"] = "unknown"
                entry["error"] = str(e)[:200]
                print(f"  ? 결과 불명 — 채널에서 직접 확인 전까지 다시 올리지 않는다: {e}")
            state["posted"].append(entry)
            save_posted(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
