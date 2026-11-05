#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""공식 채널 인기 영상 — 조회수 1만 이상, 최근 일주일 (2026-11-05).

사장님: "기사들보다 유튜브나 릴스 보고 1만 이상 되는 영상 보고 그걸 기사화해서 올리는 거
어때?", "니가 모든 기사들 다 훑어보고 거기에 맞는 내용 가지고 와 … 다 해".

**공식 채널만** 받는다. 관광청·지자체·방송사·소속사·배급사가 직접 올린 영상은 보도자료와 같은
1차 출처다. 개인 크리에이터 영상(브이로그 등)은 그 사람이 취재·창작한 것이라 받지 않는다 —
출처를 지면에 안 쓰는 우리 원칙에서 남의 취재를 우리 것으로 싣게 된다. 인스타그램 릴스는
로그인 없이 볼 수 없고 자동 수집이 약관에 걸려 다루지 않는다.

키 없이 유튜브 검색 화면을 읽는다(tv_material.youtube_search 와 같은 길). 워크플로에 유튜브
API 키를 넘길 수 있게 되면 그쪽으로 바꾼다.

공식 채널 판정: (1) 방송사 채널 id 목록(tv_material.OFFICIAL_YT)에 있거나 (2) 유튜브 인증 배지가
있고 채널 이름이 아래 OFFICIAL_NAMES 가운데 하나를 담는다. 인증 배지만으로는 받지 않는다 —
인증받은 개인 크리에이터도 많다.
"""
from __future__ import annotations

import re
import sys

import httpx

from tv_material import OFFICIAL_YT, _days_ago, _unescape

MIN_VIEWS = 10_000
MAX_DAYS = 7

# 채널 이름에 이 말이 들어 있으면 공식 채널로 본다(인증 배지와 함께). 소문자·공백 없이 비교한다.
OFFICIAL_NAMES = {
    # 관광청·지자체
    "visitguam", "괌정부관광청", "mymarianas", "마리아나관광청", "gohawaii", "하와이관광청",
    "amazingthailand", "태국관광청", "tourismthailand", "visitjapan", "japannationaltourism",
    "일본정부관광국", "taiwantourism", "대만관광청", "vietnamtourism", "베트남관광",
    "sabahtourism", "visitlaos", "제주관광공사", "visitjeju", "한국관광공사", "visitkorea",
    "imagineyourkorea", "서울관광재단", "visitseoul", "visitbusan", "부산관광공사",
    # 방송사
    "kbs", "mbc", "sbs", "ebs", "jtbc", "tvn", "mnet", "tving", "wavve", "coupangplay",
    "netflixkorea", "디즈니플러스",
    # 소속사·레이블
    "hybelabels", "bighit", "jypentertainment", "smtown", "ygentertainment", "starship",
    "cubeentertainment", "fncentertainment", "wakeone", "kqentertainment", "ador",
    "pledis", "belift", "sourcemusic", "koz", "theblacklabel", "rbw", "woollim",
    "1thek", "stone music", "genie", "mubeat",
    # 배급·제작
    "cjenm", "롯데엔터테인먼트", "showbox", "쇼박스", "newmovie", "플러스엠", "plusm",
    "바른손", "에이스메이커", "메가박스", "cgv",
}

# 날마다 도는 기본 검색어 — 우리 지면(여행 11곳 + 문화)에 맞춘다.
BASE_QUERIES = [
    "괌정부관광청", "마리아나관광청 사이판", "하와이관광청", "태국관광청", "일본정부관광국",
    "대만관광청", "베트남 관광청", "제주관광공사", "한국관광공사 여행", "사바 코타키나발루 관광",
    "HYBE LABELS", "JYP Entertainment", "SMTOWN", "YG ENTERTAINMENT", "STARSHIP",
    "KBS 드라마 예고", "MBC 드라마 예고", "SBS 드라마 예고", "tvN 드라마 예고", "JTBC 드라마 예고",
    "영화 메인 예고편", "1theK",
]

_VIEWS = re.compile(r"조회수\s*([\d,.]+)\s*(만|천|억)?\s*회")


def views_of(text: str) -> int:
    """'조회수 12,345회' · '조회수 1.2만회' → 숫자. 못 읽으면 0."""
    m = _VIEWS.search(text or "")
    if not m:
        return 0
    n = float(m.group(1).replace(",", ""))
    return int(n * {"만": 10_000, "천": 1_000, "억": 100_000_000}.get(m.group(2) or "", 1))


def _norm(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").lower())


# 방송사 '뉴스' 채널은 받지 않는다 — 기자가 취재한 보도라 우리가 옮기면 남의 취재를 싣게 된다
# (2026-11-05 첫 실행에 SBS 뉴스 영상 4건이 끼었다). 예능·드라마·공식 예고·뮤직비디오만 받는다.
NEWS = re.compile(r"뉴스|news|ytn|연합", re.I)


def is_official(channel_id: str, channel: str, verified: bool) -> bool:
    if NEWS.search(channel or ""):
        return False
    if channel_id in OFFICIAL_YT:
        return True
    n = _norm(channel)
    return verified and any(_norm(k) in n for k in OFFICIAL_NAMES)


def parse_results(html: str) -> list[dict]:
    """검색 결과 화면 → [{id, title, channel_id, channel, verified, views, age_days}]"""
    out = []
    for m in re.finditer(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html):
        chunk = html[m.start():m.start() + 8000]
        nxt = chunk.find('"videoRenderer":', 20)
        if nxt > 0:
            chunk = chunk[:nxt]
        # 제목·채널 이름 안의 \" 에서 끊기지 않게 이스케이프된 따옴표까지 읽는다(2026-11-05 첫 실행:
        # tvN 예고 "[7화 예고] \"…\"" 가 "[7화 예고] \" 로 잘렸다)
        title = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+)"', chunk)
        owner = re.search(r'"ownerText":\{"runs":\[\{"text":"((?:[^"\\]|\\.)+)"', chunk)
        chan = re.search(r'"browseId":"(UC[\w-]+)"', chunk)
        age = re.search(r'"publishedTimeText":\{"simpleText":"([^"]+)"', chunk)
        vc = re.search(r'"viewCountText":\{"simpleText":"([^"]+)"', chunk)
        out.append({
            "id": m.group(1),
            "title": _unescape(title.group(1)) if title else "",
            "channel": _unescape(owner.group(1)) if owner else "",
            "channel_id": chan.group(1) if chan else "",
            "verified": "BADGE_STYLE_TYPE_VERIFIED" in chunk,
            "views": views_of(_unescape(vc.group(1)) if vc else ""),
            "age_days": _days_ago(age.group(1) if age else ""),
        })
    return out


def pick(results: list[dict], min_views: int = MIN_VIEWS, max_days: float = MAX_DAYS) -> list[dict]:
    return [r for r in results
            if r["views"] >= min_views and r["age_days"] <= max_days
            and is_official(r["channel_id"], r["channel"], r["verified"])]


def description(c: httpx.Client, video_id: str) -> str:
    """영상 설명 — 기사의 사실 재료. 못 읽으면 빈 문자열."""
    try:
        page = c.get(f"https://www.youtube.com/watch?v={video_id}",
                     headers={"Accept-Language": "ko-KR,ko"}).text
    except Exception:
        return ""
    m = re.search(r'"shortDescription":"(.*?)","', page)
    return _unescape(m.group(1)).replace("\\n", "\n") if m else ""


def collect(extra_queries: list[str] | None = None, limit: int = 15) -> dict:
    """공식 채널 인기 영상 목록. 실패는 errors 에 담고 빈 목록으로 돌아온다."""
    found: dict[str, dict] = {}
    errors: list[str] = []
    queries = list(dict.fromkeys(BASE_QUERIES + (extra_queries or [])))
    with httpx.Client(timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"}) as c:
        for q in queries:
            try:
                r = c.get("https://www.youtube.com/results",
                          params={"search_query": q, "sp": "CAI%3D"},
                          headers={"Accept-Language": "ko-KR,ko"})
                for v in pick(parse_results(r.text)):
                    found.setdefault(v["id"], {**v, "query": q})
            except Exception as e:  # noqa: BLE001
                errors.append(f"{q}: {e}")
        top = sorted(found.values(), key=lambda v: -v["views"])[:limit]
        for v in top:
            v["description"] = description(c, v["id"])[:600]
    return {"items": top, "errors": errors, "queries": len(queries)}


def to_markdown(data: dict) -> str:
    lines = ["# 공식 채널 인기 영상 — 조회수 1만 이상, 최근 일주일", "",
             "관광청·방송사·소속사·배급사 공식 유튜브만 모았다. 영상 제목·설명의 사실로 기사를 쓰고,",
             "본문 첫 문단 아래에 `@youtube <id>` 줄을 그대로 둔다. 설명에 없는 내용은 쓰지 않는다.",
             f"(검색어 {data.get('queries', 0)}개 · 고른 영상 {len(data.get('items', []))}개"
             + (f" · 실패 {len(data['errors'])}" if data.get("errors") else "") + ")", ""]
    for v in data.get("items", []):
        lines.append(f"## {v['title']}")
        lines.append(f"- 채널 {v['channel']} · 조회수 {v['views']:,}회 · {v['age_days']:.0f}일 전")
        lines.append(f"- `@youtube {v['id']}` · https://www.youtube.com/watch?v={v['id']}")
        desc = re.sub(r"\s+", " ", v.get("description") or "").strip()
        if desc:
            lines.append(f"  {desc[:500]}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    data = collect(sys.argv[1:])
    print(to_markdown(data))
