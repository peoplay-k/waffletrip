#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자유 이용 인물 사진 — 위키데이터 대표 사진(P18)과 위키미디어 공용 라이선스 (2026-10-17).

방송사 보도 스틸은 무단 게재 금지라 못 쓴다. 대신 출연자 사진 가운데 CC·퍼블릭
도메인·공공누리로 풀린 것을 출처를 밝혀 쓴다(사장님 결정).

**동명이인을 막는 것이 핵심이다.** 이름만으로 사진을 찾으면 시인 김광규 사진이 배우
김광규 기사에 붙는다(2026-10-17 실측: 위키데이터에 둘 다 있고 둘 다 사진이 있다).
그래서 위키데이터 설명에 배우·가수·방송인 같은 직업이 있는 항목의 대표 사진만 쓴다.
라이선스가 확인되지 않으면 쓰지 않는다.

    python3 tools/free_photos.py 이서진 지석진
"""
from __future__ import annotations

import html
import re
import sys

import httpx

UA = {"User-Agent": "PeopleRoadBot/1.0 (https://waffletrip.com; editorial photo credits)"}
WD = "https://www.wikidata.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
JOBS = re.compile(r"배우|가수|방송인|개그맨|코미디언|아나운서|진행자|연예인|모델|래퍼|아이돌|"
                  r"actor|actress|singer|entertainer|comedian|presenter|television personality|"
                  r"announcer|rapper|idol", re.I)
FREE = re.compile(r"^(CC BY|CC0|Public domain|PD|KOGL|공공누리)", re.I)
THUMB = 960


def _desc(entity: dict) -> str:
    d = entity.get("descriptions") or {}
    return " ".join((d.get(k) or {}).get("value", "") for k in ("ko", "en"))


def person_image(c: httpx.Client, name: str) -> dict | None:
    """연예인으로 확인된 사람의 대표 사진 파일명. {qid, label, desc, file} 또는 None."""
    found = c.get(WD, params={"action": "wbsearchentities", "search": name, "language": "ko",
                              "uselang": "ko", "type": "item", "limit": 5, "format": "json"}).json()
    hits = [h for h in found.get("search") or [] if h.get("label") == name]
    if not hits:
        return None
    ents = c.get(WD, params={"action": "wbgetentities", "ids": "|".join(h["id"] for h in hits),
                             "props": "claims|descriptions", "languages": "ko|en",
                             "format": "json"}).json().get("entities") or {}
    for h in hits:                                   # 검색 순위대로
        e = ents.get(h["id"]) or {}
        claims = e.get("claims") or {}
        human = any(cl["mainsnak"].get("datavalue", {}).get("value", {}).get("id") == "Q5"
                    for cl in claims.get("P31") or [])
        if not human or not JOBS.search(_desc(e)) or not claims.get("P18"):
            continue
        return {"qid": h["id"], "label": name, "desc": _desc(e).strip(),
                "file": claims["P18"][0]["mainsnak"]["datavalue"]["value"]}
    return None


def file_credit(c: httpx.Client, filename: str) -> dict | None:
    """공용 파일의 썸네일 주소·라이선스·작성자. 자유 라이선스가 아니면 None."""
    r = c.get(COMMONS, params={"action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
                               "iiprop": "url|extmetadata", "iiurlwidth": THUMB,
                               "format": "json"}).json()
    page = next(iter((r.get("query") or {}).get("pages", {}).values()), {})
    info = (page.get("imageinfo") or [None])[0]
    if not info:
        return None
    meta = info.get("extmetadata") or {}
    lic = (meta.get("LicenseShortName") or {}).get("value", "")
    if not FREE.search(lic):
        return None
    artist = html.unescape(re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", ""))).strip()
    url = (info.get("thumburl") or info.get("url") or "").split("?", 1)[0]   # 추적 꼬리를 뗀다
    return {"url": url, "page": info.get("descriptionurl"),
            "license": lic, "artist": re.sub(r"\s+", " ", artist)[:60] or "작성자 미상"}


def photo_for(c: httpx.Client, name: str) -> dict | None:
    person = person_image(c, name)
    if not person:
        return None
    credit = file_credit(c, person["file"])
    if not credit or not (credit["url"] or "").startswith("https://upload.wikimedia.org/"):
        return None
    return {**person, **credit}


def markdown_line(p: dict) -> str:
    """기사 본문 한 줄. 캡션에 이름·작성자·라이선스·출처를 모두 적는다(CC BY 조건)."""
    return (f"![{p['label']} · 사진 {p['artist']} · {p['license']} · 위키미디어 공용]"
            f"({p['url']})")


def photos_for_names(names: list[str], limit: int = 40) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with httpx.Client(headers=UA, timeout=20, follow_redirects=True) as c:
        for name in names[:limit]:
            if name in out:
                continue
            try:
                p = photo_for(c, name)
            except Exception:
                p = None
            if p:
                out[name] = p
    return out


if __name__ == "__main__":
    for n, p in photos_for_names(sys.argv[1:]).items():
        print(n, "|", p["desc"], "|", p["license"], "|", p["artist"])
        print("   ", markdown_line(p))
