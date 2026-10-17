#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘·내일 방송되는 회차의 재료를 모은다 — 연예 '방송' 부문(2026-10-16 신설).

사장님: "닷뉴스처럼 연예뉴스를 하고 싶다". 닷뉴스는 하루 12~16편, 거의 전부가
'오늘 방송' 회차 소개다(인간극장·유퀴즈·라디오스타·세계테마기행). 우리는 하루 5~8편.

재료는 **방송사가 언론에 배포한 보도자료**다. 예약 해설 에이전트가 이것을 읽고
우리 문장으로 다시 쓴다(docs/DAILY_COMMENTARY.md '방송' 절). 이 도구는 쓰지 않는다.

    python3 tools/tv_material.py              # data/tv_material.json · .md

출처 (2026-10-16 실측)
- EBS 보도자료 게시판 — robots 허용. 제목에 방송일시, '방송일자' 칸이 있다.
- MBC 보도자료 API(mbcinfo.imbc.com) — robots.txt 없음.
- SBS 보도자료 API(드라마·예능·교양) — robots Disallow. 사장님 결정: 하루 몇 번만.
- KBS 프로그램 '미리보기' 게시판 — robots Disallow. 같은 결정. 그날 편성된 프로그램만.
- 편성표(KBS·MBC·SBS JSON) — 방송 시각을 맞추는 데 쓴다.

**사진은 가져오지 않는다.** 방송사들이 보도 스틸의 무단 게재를 금지한다(MBC "사전
동의 없이 무단 전재 및 게재를 할 수 없습니다", SBS·EBS 무단 전재 금지). 2026-10-16
사장님 결정으로 우리 디자인 카드를 쓴다 — 빌드가 그린다.

각 출처는 실패해도 다른 출처를 막지 않는다. 깃허브 러너는 미국 IP 라 한국 방송사
방화벽에 다르게 걸릴 수 있다 — 실패는 `errors` 에 남긴다.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OUT_JSON = os.path.join("data", "tv_material.json")
OUT_MD = os.path.join("data", "tv_material.md")
MAX_TEXT = 2400          # 재료 한 건에 남기는 본문 길이. 쓰는 쪽이 읽을 만큼만
KBS_PROGRAMS_MAX = 6     # KBS 미리보기는 하루 이만큼만 두드린다(robots Disallow)


# ── 공통 ──────────────────────────────────────────────────────────
def plain(fragment: str) -> str:
    """보도자료 HTML 을 글로. 문단은 살리고 글자 사이 태그는 붙인다.

    EBS 본문은 글자마다 <span> 으로 쪼개져 있어서 태그를 줄바꿈으로 바꾸면
    "정원 \\n619\\n명" 처럼 흩어진다. 문단 태그만 줄바꿈으로 둔다.
    """
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", fragment or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


def program_of(title: str) -> str:
    """'[SBS 골 때리는 그녀들] …' → '골 때리는 그녀들'."""
    m = re.match(r"\s*\[([^\]]+)\]", title or "")
    if not m:
        return ""
    name = re.sub(r"^(SBS|MBC|KBS\d?|EBS\d?|JTBC|tvN)\s+", "", m.group(1).strip())
    return name.strip()


_DAY = re.compile(r"(?:(\d{1,2})월\s*)?(\d{1,2})일\s*(?:\(([월화수목금토일])\))?")


def air_dates(text: str, today: datetime) -> set[str]:
    """본문에 나온 '오늘(16일)', '17일(토) 밤 9시', '10월 17일' 같은 방송일 후보.

    방송 후 리뷰("시청률 1위")와 예고를 가르는 데 쓴다. 예고에는 앞으로의 날짜가 있다.
    """
    out: set[str] = set()
    for m in re.finditer(r"오늘\s*\((\d{1,2})일\)", text):
        out.add(_date_of(today, None, int(m.group(1))))
    for m in re.finditer(r"(?:(\d{1,2})월\s*)?(\d{1,2})일\s*\(([월화수목금토일])\)", text):
        out.add(_date_of(today, m.group(1), int(m.group(2))))
    for m in re.finditer(r"(\d{1,2})월\s*(\d{1,2})일", text):
        out.add(_date_of(today, m.group(1), int(m.group(2))))
    # '16일 방송되는', '오는 16일 금요일 밤 11시 10분 방송' — 요일 괄호가 없는 꼴
    for m in re.finditer(r"(\d{1,2})일\s*[^\n.]{0,25}?방송", text):
        out.add(_date_of(today, None, int(m.group(1))))
    return {d for d in out if d}


def _date_of(today: datetime, month, day: int) -> str:
    mon = int(month) if month else today.month
    year = today.year
    # 12월에 쓴 1월 방송 예고
    if mon < today.month - 6:
        year += 1
    try:
        return datetime(year, mon, day).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": UA}, timeout=20, follow_redirects=True)


# ── 편성표 ────────────────────────────────────────────────────────
def schedules(c: httpx.Client, day: datetime, errors: list) -> list[dict]:
    """그날 본방. [{channel, title, time}] — 재방송은 뺀다."""
    ymd = day.strftime("%Y%m%d")
    rows: list[dict] = []
    try:
        r = c.get("https://static.api.kbs.co.kr/mediafactory/v1/schedule/weekly",
                  params={"rtype": "json", "local_station_code": "00",
                          "channel_code": "11,12", "program_planned_date_from": ymd,
                          "program_planned_date_to": ymd})
        for ch in r.json():
            name = {"11": "KBS1", "12": "KBS2"}.get(str(ch.get("channel_code")), "KBS")
            for s in ch.get("schedules") or []:
                if "재" in str(s.get("rerun_classification") or ""):
                    continue
                rows.append({"channel": name, "title": s.get("program_title") or "",
                             "time": str(s.get("service_start_time") or "")[:4],
                             "homepage": s.get("homepage_url") or "",
                             "episode": str(s.get("program_sequence_number") or ""),
                             "actors": str(s.get("program_actor") or "")})
    except Exception as e:
        errors.append(f"KBS 편성표: {e}")
    try:
        r = c.get("https://control.imbc.com/Schedule/TV",
                  params={"sDate": ymd, "sType": "TV"})
        for s in r.json():
            t = s.get("Title") or ""
            if "(재)" in t:
                continue
            rows.append({"channel": "MBC", "title": re.sub(r"\(\d+\)$", "", t).strip(),
                         "time": s.get("StartTime") or "", "homepage": s.get("HomepageURL") or "",
                         "episode": (re.search(r"\((\d+)\)$", t) or [None, ""])[1]})
    except Exception as e:
        errors.append(f"MBC 편성표: {e}")
    try:
        r = c.get(f"https://static.cloud.sbs.co.kr/schedule/{day:%Y/%m/%d}/SBS.json")
        for s in r.json():
            t = s.get("title") or ""
            if "재" in str(s.get("substitution_flag") or "") or "(재)" in t:
                continue
            ep = re.search(r"\((\d+)회\)", t)
            rows.append({"channel": "SBS", "title": re.sub(r"\s*\(\d+회\)", "", t).strip("[] "),
                         "time": (s.get("start_time") or "").replace(":", ""),
                         "homepage": (s.get("homepage_url") or "").strip(),
                         "episode": ep.group(1) if ep else ""})
    except Exception as e:
        errors.append(f"SBS 편성표: {e}")
    return rows


def find_slot(program: str, slots: list[dict]) -> dict | None:
    """프로그램 이름으로 편성 칸을 찾는다. 띄어쓰기·부호는 무시한다."""
    key = re.sub(r"[\s'‘’\"“”!?·:,.-]", "", program or "")
    if len(key) < 2:
        return None
    for s in slots:
        name = re.sub(r"[\s'‘’\"“”!?·:,.-]", "", s["title"])
        if key and (key in name or name in key) and len(name) >= 2:
            return s
    return None


# ── 보도자료 ──────────────────────────────────────────────────────
def ebs(c: httpx.Client, errors: list, limit: int = 15) -> list[dict]:
    base = "https://about.ebs.co.kr/board/bbs"
    q = {"boardTypeId": "1", "boardId": "31", "option": "respond", "uri": "/kor/pr/release"}
    out = []
    try:
        page = c.get(base, params={**q, "cmd": "list"}).text
        posts = re.findall(r"goView\((\d+)\)[^>]*>(.*?)</a>", page, re.S)[:limit]
    except Exception as e:
        errors.append(f"EBS 목록: {e}")
        return out
    for pid, raw_title in posts:
        title = re.sub(r"\s+", " ", plain(raw_title))
        try:
            view = c.get(base, params={**q, "cmd": "view", "postId": pid}).text
        except Exception as e:
            errors.append(f"EBS {pid}: {e}")
            continue
        i = view.find("view_cont")
        i = view.find(">", i) + 1 if i > 0 else 0
        body = plain(view[i:i + 60000]) if i > 0 else ""
        body = re.sub(r"\n(?=[^\n]{0,3}\n)", "", body)    # 글자 조각 줄을 붙인다
        prog = re.search(r"프로그램 정보\s*\n?\s*([^\n]+)", view_text := plain(view))
        if title.endswith(".."):
            # 목록 제목은 잘려 온다. 상세 페이지의 제목 줄(목록 제목 앞부분으로 시작)을 쓴다.
            head = title.rstrip(".")
            full = next((ln for ln in view_text.splitlines() if ln.startswith(head[:12])), "")
            title = full or title
        day = re.search(r"방송일자\s*\n?\s*(\d{4}-\d{2}-\d{2})", body)
        out.append({"source": "EBS 보도자료", "channel": "EBS",
                    "program": (prog.group(1).strip() if prog else program_of(title)),
                    "title": title, "air_date": day.group(1) if day else "",
                    "text": body, "url": f"{base}?boardTypeId=1&boardId=31&cmd=view&postId={pid}"})
    return out


def mbc(c: httpx.Client, errors: list, limit: int = 20) -> list[dict]:
    out, rows = [], None
    # 깃허브 러너(미국)에서 첫 요청이 20초를 넘겨 끊겼다(2026-10-16). 길게 한 번 더 본다.
    for wait in (20, 45):
        try:
            rows = c.get("https://mbcinfo.imbc.com/api/press/list",
                         params={"page": 1, "size": limit}, timeout=wait).json().get("list") or []
            break
        except Exception as e:
            last = e
    if rows is None:
        errors.append(f"MBC 목록: {last}")
        return out
    for row in rows:
        code = row.get("code")
        try:
            info = c.get("https://mbcinfo.imbc.com/api/press/info",
                         params={"intIdx": code}).json().get("info") or {}
            info = info.get("info") if isinstance(info.get("info"), dict) else info
        except Exception as e:
            errors.append(f"MBC {code}: {e}")
            continue
        title = (row.get("title") or "").strip()
        out.append({"source": "MBC 보도자료", "channel": "MBC", "program": program_of(title),
                    "title": title, "air_date": "", "posted": row.get("reg_dt") or "",
                    "text": plain(info.get("contents") or ""),
                    "url": f"https://with.mbc.co.kr/pr/press/view.html?idx={code}"})
    return out


SBS_BOARDS = {"sbspr_01": "드라마", "sbspr_02": "예능", "sbspr_03": "교양"}
# 웹 주소의 메뉴 번호(SBS PR 프로그램 메뉴 API 에서 확인, 2026-10-16). 기사 출처 링크로 쓴다.
SBS_MENU = {"sbspr_01": "65174", "sbspr_02": "65175", "sbspr_03": "65176"}


def sbs(c: httpx.Client, errors: list, limit: int = 15) -> list[dict]:
    out = []
    for code, kind in SBS_BOARDS.items():
        try:
            data = c.get("https://api.board.sbs.co.kr/bbs/V2.0/basic/board/lists",
                         params={"offset": 0, "limit": limit, "action_type": "json",
                                 "board_code": code}).json()
        except Exception as e:
            errors.append(f"SBS {kind}: {e}")
            continue
        for row in data.get("list") or []:
            title = (row.get("TITLE") or "").strip()
            out.append({"source": f"SBS 보도자료({kind})", "channel": "SBS",
                        "program": program_of(title), "title": title, "air_date": "",
                        "posted": row.get("REG_DATE") or "",
                        "text": plain(row.get("CONTENT") or ""),
                        "url": (f"https://programs.sbs.co.kr/special/sbspr/board/"
                                f"{SBS_MENU[code]}?cmd=view&board_no={row.get('NO')}")})
    return out


def kbs_previews(c: httpx.Client, slots: list[dict], errors: list) -> list[dict]:
    """그날 편성된 KBS 프로그램의 '미리보기' 게시판 최신 글.

    프로그램 주소(program.kbs.co.kr/1tv/culture/human)에서 source·sname·stype 을 뽑아
    프로그램 API 로 '미리보기' 게시판 번호를 찾는다. 하루 KBS_PROGRAMS_MAX 개까지만.
    """
    out, tried = [], 0
    # 저녁·밤 본방을 먼저 본다. 하루 몇 곳만 두드리는데 새벽 프로그램에 쓰면 아깝다.
    # 인간극장(07:50)은 닷뉴스가 매일 쓰는 대표 교양이라 함께 앞에 둔다.
    slots = sorted(slots, key=lambda s: (0 if s["time"] >= "1800" or "인간극장" in s["title"]
                                         else 1, s["time"]))
    for s in slots:
        if not s["channel"].startswith("KBS") or tried >= KBS_PROGRAMS_MAX:
            continue
        m = re.search(r"program\.kbs\.co\.kr/(\w+)/(\w+)/(\w+)", s.get("homepage") or "")
        if not m:
            continue
        tried += 1
        src, sname, stype = m.groups()
        try:
            page = c.get("https://pprogramapi.kbs.co.kr/api/v1/page",
                         params={"platform": "P", "source": src, "sname": sname,
                                 "stype": stype, "page_type": "main"}).json()
            menus = json.dumps(page, ensure_ascii=False)
            # 메뉴 주소에 게시판 번호가 들어 있다: board.html?…&bbs_loc=T2000-0030-04-838523,list,…
            bbs = re.search(r'"title":\s*"미리보기",\s*"url":\s*"[^"]*bbs_loc=([^,"]+)', menus)
            if not bbs:
                continue
            board = c.get("https://pbbsapi.kbs.co.kr/board/v1/list",
                          params={"bbs_id": bbs.group(1), "page": 1, "page_size": 2}).json()
        except Exception as e:
            errors.append(f"KBS {s['title']}: {e}")
            continue
        for post in (board.get("data") or [])[:1]:
            title = post.get("title") or ""
            out.append({"source": "KBS 미리보기", "channel": s["channel"],
                        "program": s["title"], "title": f"[{s['title']}] {title}",
                        "air_date": "", "text": plain(post.get("description") or ""),
                        "url": s.get("homepage") or ""})
    return out


# ── 유튜브 예고편 ─────────────────────────────────────────────────
#
# 사진 대신 방송사가 올린 그 회차 예고 영상을 기사에 띄운다(2026-10-16 사장님 결정).
# 유튜브 임베드는 유튜브 약관이 허용하는 방식이다. 남의 채널 영상은 쓰지 않는다 —
# 공식 채널 목록(2026-10-17 채널 검색으로 확인)에 있는 것만. 채널 피드는 15곳 중
# 10곳이 404·500 이라 못 쓰고, 프로그램명 검색 결과에서 공식 채널만 고른다.
OFFICIAL_YT = {
    "UCK1sVuXaDvJeNwl9noN5nOA": "KBS Entertain", "UChpjIaEgwtDZtmWEkzFulSA": "KBS Drama",
    "UCHlSeJxRIXZWMARC2oMwmcQ": "KBS 교양", "UC4LW3sOslC14Vn5bcoNUBkg": "KBS 다큐",
    "UC6wiUwl7dPhZOAM92lGgKPg": "KBS HUMAN", "UCmjNKt6kITwaZTqvWuaSPLg": "SBS Entertainment",
    "UC6erIDuvbOaAO-OT5rB2Xew": "SBS 스브스 Drama", "UCiBr0bK06imaMbLc8sAEz0A": "MBCentertainment",
    "UCBAEVMr0li9YYF8IwZHfusw": "MBC DRAMA", "UCFCtZJTuJhE18k8IXwmXTYQ": "EBSDocumentary",
    "UCl_tB4AqPkkxuYcJQHz6dMw": "EBSCulture", "UCbeZPOz8uaHstEIbkqBOnGg": "EBS 세계테마기행",
    "UCFL1sCAksD6_7JIZwwHcwjQ": "JTBC Entertainment", "UCkbJc8jMcTXwhtmN5VMwfXg": "JTBC Drama",
    "UCsRIHt5FkbGc6cQtCxt-ufA": "tvN D ENT", "UC9w-h_ciMmX64TcLRcb1xPg": "tvN DRAMA",
}
_AGE = re.compile(r"(\d+)\s*(분|시간|일|주|개월|년)\s*전")


def _days_ago(text: str) -> float:
    m = _AGE.search(text or "")
    if not m:
        return 999
    n, unit = int(m.group(1)), m.group(2)
    return {"분": n / 1440, "시간": n / 24, "일": n, "주": n * 7, "개월": n * 30, "년": n * 365}[unit]


def _unescape(raw: str) -> str:
    """유튜브 페이지 안 JSON 문자열의 \\uXXXX·\\" 를 푼다(한글은 그대로 둔다)."""
    raw = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), raw)
    return raw.replace('\\"', '"').replace("\\/", "/")


def youtube_search(c: httpx.Client, query: str) -> list[dict]:
    """유튜브 검색 결과(최신순). [{id, title, channel_id, age_days}]"""
    r = c.get("https://www.youtube.com/results",
              params={"search_query": query, "sp": "CAI%3D"},
              headers={"Accept-Language": "ko-KR,ko"})
    out = []
    for m in re.finditer(r'"videoRenderer":\{"videoId":"([\w-]{11})"', r.text):
        chunk = r.text[m.start():m.start() + 6000]
        title = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', chunk)
        chan = re.search(r'"browseId":"(UC[\w-]+)"', chunk)
        age = re.search(r'"publishedTimeText":\{"simpleText":"([^"]+)"', chunk)
        out.append({"id": m.group(1),
                    "title": _unescape(title.group(1)) if title else "",
                    "channel_id": chan.group(1) if chan else "",
                    "age_days": _days_ago(age.group(1) if age else "")})
    return out


def _norm(text: str) -> str:
    return re.sub(r"[\s'‘’\"“”!?·:,.\-\[\]]", "", text or "")


_GENRE = re.compile(r"^(?:(?:일일|주말|월화|수목|금토|토일|아침|저녁)?\s*드라마|특집\s*다큐|특집|예능)\s*[-·:]?\s*")


def core_name(program: str) -> str:
    """'주말드라마 사랑이 온다' → '사랑이 온다'. 편성표 머리말을 뗀다."""
    return _GENRE.sub("", (program or "").strip()).strip() or program


def _marks(air_date: str, episode: str) -> list[str]:
    mon, day = int(air_date[5:7]), int(air_date[8:10])
    out = [f"{mon}월{day}일", f"{mon}/{day}"]
    if episode:
        out += [f"{episode}화", f"{episode}회"]
    return out


def pick_preview(results: list[dict], program: str, air_date: str, episode: str,
                 confirm=None) -> dict | None:
    """그 회차 예고편 하나. 엉뚱한 영상을 붙이느니 안 붙인다.

    조건: 공식 채널 · 열흘 안 · 제목에 그 방송일('10월 16일')이나 회차('39화')가 있다.
    그리고 제목에 프로그램명이 있거나, 없으면 confirm(영상 id) 이 영상 설명에서
    프로그램명을 확인해 줘야 한다 — SBS '미운 우리 새끼'는 제목이 "[10월 18일 예고] …" 뿐이다.
    """
    if not program or not air_date:
        return None
    key = _norm(core_name(program))
    marks = [_norm(m) for m in _marks(air_date, episode)]
    for v in results:
        t = _norm(v["title"])
        if v["channel_id"] not in OFFICIAL_YT or v["age_days"] > 10:
            continue
        if not any(m in t for m in marks):
            continue
        if key in t or (confirm and confirm(v["id"], key)):
            return {**v, "channel": OFFICIAL_YT[v["channel_id"]]}
    return None


def _confirmer(c: httpx.Client):
    def check(video_id: str, key: str) -> bool:
        try:
            page = c.get(f"https://www.youtube.com/watch?v={video_id}",
                         headers={"Accept-Language": "ko-KR,ko"}).text
        except Exception:
            return False
        desc = re.search(r'"shortDescription":"(.*?)","', page)
        kw = re.search(r'"keywords":\[(.*?)\]', page)
        text = _unescape((desc.group(1) if desc else "") + (kw.group(1) if kw else ""))
        return key in _norm(text)
    return check


def attach_previews(c: httpx.Client, rows: list[dict], errors: list) -> None:
    for it in rows:
        if not it.get("program"):
            continue
        try:
            found = youtube_search(c, f"{core_name(it['program'])} 예고")
        except Exception as e:
            errors.append(f"유튜브 {it['program']}: {e}")
            continue
        pv = pick_preview(found, it["program"], it["air_date"], it.get("episode", ""),
                          confirm=_confirmer(c))
        if pv:
            it["youtube"] = {"id": pv["id"], "title": pv["title"], "channel": pv["channel"]}


# ── 출연자 자유 이용 사진 ─────────────────────────────────────────
_NAME = re.compile(r"(?<![가-힣])[가-힣]{2,4}(?![가-힣])")
_STOP = {"방송", "오늘", "예고", "공개", "출연", "프로그램", "이번", "가족", "사람", "시청자",
         "제작진", "주인공", "드라마", "예능", "다큐", "특집", "마지막", "첫방송", "최초"}


def cast_names(item: dict, slots: list[dict]) -> list[str]:
    """출연자일 만한 이름. 위키데이터가 연예인인지 확인하므로 여기선 넉넉히 뽑는다.

    보도자료 제목(이름이 가장 자주 나온다) → 본문의 '출연' 줄 → KBS 편성표 출연자 순.
    """
    names: list[str] = []
    title = re.sub(r"^\[[^\]]*\]", "", item.get("title") or "")
    names += [n for n in _NAME.findall(re.sub(r"[×Xx·,]", " ", title))]
    for m in re.finditer(r"출연\s*[:·]?\s*([^\n]{2,80})", item.get("text") or ""):
        names += _NAME.findall(m.group(1))
    slot = find_slot(item.get("program", ""), slots)
    if slot and slot.get("actors"):
        names += _NAME.findall(slot["actors"])
    seen, out = set(), []
    for n in names:
        if n not in seen and n not in _STOP:
            seen.add(n)
            out.append(n)
    return out[:6]


def attach_photos(rows: list[dict], slots: list[dict], errors: list) -> None:
    try:
        import free_photos
    except Exception as e:
        errors.append(f"사진 모듈: {e}")
        return
    wanted = {it["id"] if "id" in it else it["url"]: cast_names(it, slots) for it in rows}
    every = [n for names in wanted.values() for n in names]
    try:
        found = free_photos.photos_for_names(every)
    except Exception as e:
        errors.append(f"자유 이용 사진: {e}")
        return
    for it in rows:
        key = it["id"] if "id" in it else it["url"]
        it["photos"] = [{"name": n, "line": free_photos.markdown_line(found[n])}
                        for n in wanted[key] if n in found][:3]


# ── 모으기 ────────────────────────────────────────────────────────
def collect(now: datetime | None = None) -> dict:
    now = now or datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    errors: list[str] = []
    with client() as c:
        slots = schedules(c, now, errors)
        slots_tomorrow = schedules(c, now + timedelta(days=1), errors)
        items = ebs(c, errors) + mbc(c, errors) + sbs(c, errors) + kbs_previews(c, slots, errors)

    picked = []
    for it in items:
        text = it["text"]
        dates = air_dates(it["title"] + "\n" + text[:600], now)
        if it.get("air_date"):
            dates.add(it["air_date"])
        when = today if today in dates else tomorrow if tomorrow in dates else ""
        if not when:
            continue                       # 지난 방송 리뷰·시청률 자랑은 재료가 아니다
        slot = find_slot(it["program"], slots if when == today else slots_tomorrow)
        it.update({"air_date": when,
                   "air_time": slot["time"] if slot else "",
                   "episode": slot.get("episode", "") if slot else "",
                   "text": text[:MAX_TEXT]})
        picked.append(it)

    # 같은 프로그램은 한 건만 — 본문이 긴 것(정보가 많은 것)을 남긴다.
    best: dict[tuple, dict] = {}
    for it in picked:
        key = (it["channel"][:3], re.sub(r"\s", "", it["program"] or it["title"]))
        if key not in best or len(it["text"]) > len(best[key]["text"]):
            best[key] = it
    rows = sorted(best.values(), key=lambda i: (i["air_date"], i["air_time"] or "9999"))
    with client() as c:
        attach_previews(c, rows, errors)
    attach_photos(rows, slots + slots_tomorrow, errors)
    return {"built_at": now.isoformat(timespec="seconds"), "today": today,
            "items": rows, "errors": errors,
            "counts": {"편성(오늘)": len(slots), "보도자료": len(items), "재료": len(rows)}}


def to_markdown(data: dict) -> str:
    lines = [f"# 방송 재료 ({data['today']})", "",
             "방송사 보도자료다. **문장을 옮기지 말고** 사실만 가져다 우리 문장으로 쓴다.",
             "사진은 쓰지 않는다 — 빌드가 프로그램 카드를 그린다.", ""]
    for it in data["items"]:
        when = it["air_date"][5:].replace("-", "/")
        tm = f" {it['air_time'][:2]}:{it['air_time'][2:]}" if it.get("air_time") else ""
        ep = f" · {it['episode']}회" if it.get("episode") else ""
        lines += [f"## {it['channel']} {it['program'] or '?'}{ep} — {when}{tm} 방송",
                  f"- 출처: {it['source']} · {it['url']}",
                  f"- 보도자료 제목: {it['title']}"]
        if it.get("youtube"):
            y = it["youtube"]
            lines.append(f"- 유튜브 예고(공식 {y['channel']}): `@youtube {y['id']}` — {y['title']}")
        for ph in it.get("photos") or []:
            lines.append(f"- 사진(자유 이용, 출연자 {ph['name']}): `{ph['line']}`")
        lines += ["", it["text"], ""]
    if data["errors"]:
        lines += ["---", "수집 실패: " + " / ".join(data["errors"])]
    return "\n".join(lines)


def main() -> int:
    data = collect()
    os.makedirs("data", exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    with open(OUT_MD, "w", encoding="utf-8") as fh:
        fh.write(to_markdown(data))
    print(f"방송 재료 {len(data['items'])}건 → {OUT_MD} {data['counts']}")
    for e in data["errors"]:
        print(f"  실패: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
