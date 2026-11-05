#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""오늘 쓸 기사거리를 묶어 낸다.

**남의 기사를 옮기는 것과 남의 기사를 바탕으로 쓰는 것은 다르다.**
사실에는 저작권이 없지만 남이 쓴 문장에는 있다. 그래서 이 도구는 문장을
넘기지 않고 **같은 사건을 쓴 매체들을 묶어서** 넘긴다. 다섯 곳이 같은 건을
쓰면 그건 실제로 일어난 일이고, 다섯 곳이 각각 무엇을 강조했는지가 곧
우리가 쓸 기사의 뼈대가 된다.

    python3 tools/story_material.py            # 오늘치
    python3 tools/story_material.py --days 2   # 이틀치에서 고른다
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import REGION_NAMES  # noqa: E402

KST = timezone(timedelta(hours=9))
OUT = os.path.join("data", "story_material.md")
STOP = {"있다", "했다", "한다", "된다", "위해", "통해", "대한", "오는", "이번",
        "지난", "올해", "내년", "관련", "기자", "제공", "사진", "여행", "관광"}


# 사건·사고는 싣지 않는다(편집원칙 3항). 다만 태풍·정전·도로 통제처럼
# 여행자의 일정에 영향을 주는 것은 남긴다. 기존 `relevance.is_crime_report`
# 는 우리말만 보므로 영문 지역지 기사를 그대로 통과시켰다 —
# 2026-09-16 실측: 몬태나 교통사고와 와이키키 폭행이 괌·하와이 거리로 올라왔다.
_INCIDENT = re.compile(
    r"\b(dead|killed|injur\w*|crash|stabb\w*|shot|shooting|arrest\w*|"
    r"assault|robber\w*|homicide|lacerations|drug use|suspect\w*|"
    r"police|missing|fire\b|body found)\b", re.I)
_INCIDENT_KO = re.compile(
    r"(추락|사망|숨져|숨진|부상자|체포|구속|피살|폭행|살해|실종|자위대|"
    r"미사일|교전|시신|마약|음주운전|성추행|절도|강도)")
_TRAVEL_IMPACT = re.compile(
    r"\b(hurricane|typhoon|storm|flight|airport|airline|power restored|"
    r"reopen\w*|closure|closed|advisory|evacuat\w*|tsunami|volcano)\b", re.I)
_TRAVEL_IMPACT_KO = re.compile(
    r"(태풍|정전|결항|지연|운항|노선|공항 폐쇄|도로 통제|입국|비자|여권|"
    r"재개|복구|주의보|대피)")


# 종합지 여행면을 구글뉴스 site: 검색으로 붙이면서(2026-10-30) '항공'·'관광' 한 마디로 걸린
# 부고·인사·증권·군사 기사가 재료에 섞였다 — 첫 실행 실측: "[부고] 대한항공 전무 모친상",
# "북한 무인항공기술발전 전시회", "원·달러 환율 … 항공 웃는다", "인천공항 바이오 화물".
# 제목에 이런 말이 있으면 여행 기사거리가 아니다. 지명 뒤의 '군'(함양군)은 건드리지 않는다.
_NOT_TRAVEL = re.compile(
    r"\[부고\]|부고|별세|모친상|부친상|빙모상|빙부상|승진|인사\]|\[인사|영업이익|주가|주주|공시|"
    r"실적 발표|채용|입찰|낙찰|북한|무인기|무인항공|항공우주|항공기술|항공화물|화물|방산|"
    r"전투기|미사일|군수|개인정보 유출|해킹|검찰|경찰|구속|기소|고발|혐의|청문회|국정감사|국감")


def is_not_travel(title: str) -> bool:
    return bool(_NOT_TRAVEL.search(title or ""))


# 여행업계면은 하루 100건이 넘게 들어온다(2026-10-15 129건). 지역면처럼 세 건만
# 보여주면 고를 거리가 없다. 그리고 업계 기사는 매체마다 결이 다르다 — 여행신문·
# 트래블데일리는 업계 취재가 중심이고, 투어코리아는 지자체 보도자료가 많이 섞인다.
# 2026-10-30 소스가 61 → 154개로 늘었다(사장님: "너가 기사를 다 찾아서 넣어야지"). 해설 기자가
# 하루 여행 20편을 쓰려면 지역마다 다섯, 업계는 열 묶음은 보여 줘야 고를 거리가 있다.
INDUSTRY_PICKS = 10
SOURCE_RANK = {"여행신문": 0, "트래블데일리": 0, "트래비": 0,
               "트래블바이크뉴스": 1, "여행스케치": 1, "투어코리아": 2}


def is_incident(title: str) -> bool:
    """사건·사고인가. 여행 일정에 영향을 주는 것은 사고여도 남긴다."""
    t = title or ""
    if _TRAVEL_IMPACT.search(t) or _TRAVEL_IMPACT_KO.search(t):
        return False
    return bool(_INCIDENT.search(t) or _INCIDENT_KO.search(t))


# 다른 매체의 단독 기사. 그 매체가 직접 취재해 처음 낸 것이라 사실만 가져와도
# 남의 취재를 우리 것처럼 싣게 된다. "단독 기사는(조·중·동) 안 된다"
# (2026-10-01 편집국장). 조·중·동만이 아니라 어느 매체의 단독이든 거른다.
_EXCLUSIVE = re.compile(r"[\[(<【〈「]\s*단독\s*[\])>】〉」]|^\s*단독\s*[:·]|^\s*exclusive\b",
                        re.IGNORECASE)


def is_exclusive(title: str) -> bool:
    return bool(_EXCLUSIVE.search(title or ""))


def is_korean_title(text: str) -> bool:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if "\uac00" <= c <= "\ud7a3") / len(letters) >= 0.4


def words(text: str) -> set[str]:
    t = re.sub(r"[^가-힣A-Za-z0-9 ]", " ", text or "")
    return {w for w in t.split() if len(w) > 1 and w not in STOP}


def load(days: int) -> list[dict]:
    files = sorted(glob.glob(os.path.join("data", "items", "*.jsonl")))[-days:]
    out, seen = [], set()
    for path in files:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["id"] in seen:
                    continue
                seen.add(row["id"])
                out.append(row)
    return out


def cluster(items: list[dict]) -> list[list[dict]]:
    """제목이 겹치는 것끼리 묶는다. 같은 사건을 여러 곳이 쓴 것이다."""
    groups: list[list[dict]] = []
    for item in items:
        w = words(item.get("title"))
        if not w:
            continue
        for g in groups:
            base = words(g[0].get("title"))
            overlap = len(w & base) / max(1, min(len(w), len(base)))
            if overlap >= 0.45:
                g.append(item)
                break
        else:
            groups.append([item])
    return groups


def already_written(items: list[dict]) -> set[str]:
    """우리가 이미 쓴 해설의 낱말. 같은 걸 또 쓰지 않게 대조한다."""
    out: set[str] = set()
    for row in items:
        if row.get("grade") == "C" and row["id"].startswith("c-"):
            out |= words(row.get("title"))
    return out


# 여행신문은 업계 소식이 가장 많은 전문지다. 클러스터·지역 상한을 거치면 하루 서너 건만 재료에
# 남아, 나머지는 해설 기자 눈에 띄지 않았다(2026-11-04 사장님: "기사 매일 여행신문쪽 50개
# 훑어보고 거기서 기사를 가지고와. 내가 준거만 체크하지 말고"). 그래서 최근 50건을 날짜·지역
# 가리지 않고 그대로 한 절에 늘어놓는다. 이미 근거로 쓴 기사에는 ✅ 를 단다.
TRAVELTIMES = "여행신문"
TRAVELTIMES_COUNT = 50


def used_sources(review_dir: str = os.path.join("content", "review")) -> set[str]:
    """원고 앞머리 sources: 에 이미 적힌 주소들."""
    out: set[str] = set()
    for path in glob.glob(os.path.join(review_dir, "*.md")):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        head = text.split("---", 2)[1] if text.startswith("---") else ""
        out |= set(re.findall(r"^\s*-\s*(https?://\S+)", head, re.M))
    return out


def latest_from(outlet: str, n: int, days: int = 21) -> list[dict]:
    """한 매체의 최근 n건 — 지역·클러스터와 상관없이, 최신순."""
    rows = [r for r in load(days) if (r.get("source_name") or "").strip() == outlet
            and r.get("grade") == "B" and not is_exclusive(r.get("title") or "")]
    rows.sort(key=lambda r: r.get("published_at") or "", reverse=True)
    return rows[:n]


def traveltimes_section(rows: list[dict], used: set[str]) -> list[str]:
    if not rows:
        return []
    fresh = sum(1 for r in rows if r.get("source_url") not in used)
    lines = [f"## 여행신문 최근 {len(rows)}건 — 하나씩 훑는다 (안 쓴 것 {fresh}건)", "",
             "매일 이 목록을 끝까지 본다. ✅ 는 이미 근거로 쓴 기사다. 여행신문 기자가 직접 취재한",
             "분석·인터뷰·현장기는 쓰지 않는다 — 기관·기업 발표, 공개 통계, 신상품·취항 소식을 고른다.", ""]
    for r in rows:
        mark = "✅ " if r.get("source_url") in used else ""
        day = (r.get("published_at") or "")[:10]
        summ = re.sub(r"\s+", " ", (r.get("summary") or "")).strip()
        lines.append(f"- {mark}[{day}·{REGION_NAMES.get(r.get('region', ''), r.get('region', ''))}] {r['title']}")
        if summ:
            lines.append(f"  {summ[:200]}")
        lines.append(f"  {r.get('source_url', '')}")
    lines.append("")
    return lines


# 연예 화제 기사에 붙일 자유 이용 사진(2026-11-05 사장님: "연예기사는 인터넷에서 활용할 수 있는
# 이미지들 체크하고 올리자. 글만 있으니 너무 별로야"). 방송 재료와 같은 길 — 위키데이터가
# 연예인·그룹으로 확인한 항목의 대표 사진 가운데 CC·퍼블릭 도메인만, 캡션에 작성자·라이선스를 단다.
# 제목의 낱말을 넉넉히 넘기고, 사람·그룹인지는 위키데이터가 가린다.
_ENT_NAME = re.compile(r"(?<![가-힣A-Za-z])(?:[가-힣]{2,5}|[A-Za-z][A-Za-z0-9&]{1,14})(?![가-힣A-Za-z])")
_ENT_STOP = {"화제", "공개", "컴백", "개봉", "첫방", "방송", "돌파", "기록", "포스터", "박스오피스",
             "드라마", "영화", "예능", "앨범", "미니", "싱글", "차트", "오늘", "발매", "단독", "포토",
             "관객", "매출", "시청률", "최고", "역대", "출연", "주연", "감독", "새", "신곡", "콘서트",
             # 사람 이름과 같은 꼴의 기사 말. "차트 강타!" 의 강타가 가수 강타로 잡혔다(2026-11-05)
             "강타", "석권", "점령", "등극", "돌풍", "대세", "국민", "역주행", "정상", "합류"}
ENT_PHOTO_NAMES = 40


def ent_names(title: str) -> list[str]:
    """연예 기사 제목에서 사람·그룹일 만한 이름. 따옴표 안(작품·곡 이름)은 뺀다."""
    t = re.sub(r"\[[^\]]*\]", " ", title or "")
    t = re.sub(r"[‘'\"“][^’'\"”]*[’'\"”]", " ", t)
    out: list[str] = []
    for w in _ENT_NAME.findall(t):
        w = re.sub(r"(은|는|이|가|의|와|과|도|를|을)$", "", w) if re.fullmatch(r"[가-힣]{3,6}", w) else w
        if len(w) >= 2 and w not in _ENT_STOP and w not in out:
            out.append(w)
    return out[:4]


def ent_photo_lines(groups: list[list[dict]], finder=None) -> dict[int, list[str]]:
    """묶음 번호 → 붙일 사진 줄(최대 2). 찾기 실패는 조용히 비운다 — 재료는 사진 없이도 나간다."""
    wanted = {i: ent_names(g[0].get("title") or "") for i, g in enumerate(groups)}
    every = list(dict.fromkeys(n for names in wanted.values() for n in names))[:ENT_PHOTO_NAMES]
    if not every:
        return {}
    try:
        if finder is None:
            import free_photos
            found = free_photos.photos_for_names(every, limit=ENT_PHOTO_NAMES)
            line = free_photos.markdown_line
        else:
            found, line = finder(every)
    except Exception as e:  # noqa: BLE001
        print(f"연예 사진 찾기 실패: {e}", file=sys.stderr)
        return {}
    return {i: [f"- 사진(자유 이용, {n}): `{line(found[n])}`" for n in names if n in found][:2]
            for i, names in wanted.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2)
    ap.add_argument("--per-region", type=int, default=5)
    args = ap.parse_args()

    items = load(args.days)
    mine = already_written(items)
    by_region: dict[str, list[dict]] = defaultdict(list)
    ent_rows: list[dict] = []
    for row in items:
        title = row.get("title") or ""
        if row.get("grade") != "B" or not title:
            continue
        if is_incident(title):
            continue                      # 사건·사고는 싣지 않는다
        if is_exclusive(title):
            continue                      # 남의 단독 기사는 재료로 쓰지 않는다
        if is_not_travel(title):
            continue                      # 부고·인사·주가·군사 — 여행 기사거리가 아니다
        if row.get("channel") == "ent":
            ent_rows.append(row)          # 연예는 지역이 없다. 따로 묶는다
            continue
        by_region[row.get("region", "")].append(row)

    today = datetime.now(KST).strftime("%Y-%m-%d")
    lines = [f"# 오늘 쓸 기사거리 ({today})", "",
             "여러 매체가 같은 건을 쓴 것부터 놓았다. **문장을 옮기지 말고**",
             "사실만 가져다 우리 문장으로 쓴다. 인용한 매체는 본문에 밝힌다.", ""]
    total = 0
    for region in REGION_NAMES:
        rows = by_region.get(region) or []
        if not rows:
            continue
        groups = cluster(rows)
        # 고르는 순서 — 우리말 제목 먼저, 그다음 여러 곳이 쓴 것, 그다음 최신.
        #
        # 우리말 제목을 앞에 두는 이유: 한국 여행 매체가 그 목적지를 다뤘다는
        # 것 자체가 우리 독자와 맞닿았다는 뜻이다. 영문 지역지는 그 지역
        # 주민을 위한 기사가 대부분이라 재료로서 값이 떨어진다.
        #
        # 최신순은 날짜 문자열을 거꾸로 정렬해서 낸다. 예전에는 `-hash(날짜)` 를
        # 키로 써서 사실상 무작위였다(2026-10-15 — 업계면 맨 앞에 충남지사 동정).
        groups.sort(key=lambda g: max((i.get("published_at") or "") for i in g),
                    reverse=True)
        groups.sort(key=lambda g: (
            0 if any(is_korean_title(i.get("title")) for i in g) else 1,
            0 if any((i.get("summary") or "").strip() for i in g) else 1,  # 요약 없는 것(원문 미해결)은 뒤로
            -len(g),
            min(SOURCE_RANK.get(i.get("source_name", ""), 1) for i in g)))
        # 이미 우리가 쓴 것과 겹치면 뺀다. 같은 걸 또 쓰는 것이 가장 나쁘다.
        groups = [g for g in groups
                  if not (len(g) == 1 and len(words(g[0]["title"]) & mine) >= 3)]
        # 영문 단독 기사는 재료로 쓰지 않는다. 여러 곳이 쓴 것이면 남긴다.
        groups = [g for g in groups
                  if len(g) > 1 or any(is_korean_title(i.get("title")) for i in g)]
        limit = INDUSTRY_PICKS if region == "industry" else args.per_region
        picked = groups[:limit]
        if not picked:
            continue
        lines.append(f"## {REGION_NAMES[region]}")
        lines.append("")
        for g in picked:
            total += 1
            outlets = sorted({(i.get("source_name") or "").strip()
                              for i in g if i.get("source_name")})
            lines.append(f"### {g[0]['title']}")
            lines.append(f"- 매체 {len(outlets)}곳 · {' · '.join(outlets) or '미상'}"
                         f"{'  ← 여러 곳이 썼다' if len(g) > 1 else ''}")
            for i in g[:4]:
                summ = re.sub(r"\s+", " ", (i.get("summary") or "")).strip()
                lines.append(f"  - {i.get('source_name', '?')}: {summ[:160]}")
                if i.get("source_url"):
                    lines.append(f"    {i['source_url']}")
            lines.append("")
    tt = traveltimes_section(latest_from(TRAVELTIMES, TRAVELTIMES_COUNT), used_sources())
    lines += tt
    total += sum(1 for x in tt if x.startswith("- "))
    # 연예 거리. 지역이 없으므로 한 절에 모은다. 여기 있는 것은 **편집실에서 사람이
    # 쓴다** — 예약 해설 에이전트는 연예 기사를 쓰지 않는다(DAILY_COMMENTARY.md).
    # 가십은 edit 단계에서 이미 걸렀지만, 보도자료성 발표만 재료로 삼는다.
    if ent_rows:
        groups = cluster(ent_rows)
        groups.sort(key=lambda g: max((i.get("published_at") or "") for i in g),
                    reverse=True)
        # 매체 수 — 편집 단계가 같은 사건을 대표 1건 + related 로 이미 묶어 두므로 그것까지 센다.
        def outlets_of(g):
            return sum(1 + len(i.get("related") or []) for i in g)
        groups.sort(key=lambda g: -outlets_of(g))
        picked = groups[:args.per_region * 2]
        photos = ent_photo_lines(picked) if picked else {}
        if picked:
            lines.append("## 연예 — 매체 수가 많은 순, 🔥 화제부터")
            asked = sum(len(ent_names(g[0].get("title") or "")) for g in picked)
            got = sum(len(v) for v in photos.values())
            lines.append(f"(자유 이용 사진: 이름 후보 {asked}개 확인, 사진 줄 {got}개)")
            lines.append("")
            for gi, g in enumerate(picked):
                total += 1
                outlets = sorted({(i.get("source_name") or "").strip()
                                  for i in g if i.get("source_name")})
                cat = g[0].get("category") or "startrip"
                # 세 곳 이상이 쓴 연예 소식은 그날의 화제다 — 해설 기자가 회차마다 먼저 본다
                # (2026-11-01 사장님: "지금 제일 연예에서 핫한 기사들도 올리고 잇지?").
                hot = f"🔥 화제(매체 {outlets_of(g)}곳) " if outlets_of(g) >= 3 else ""
                lines.append(f"### {hot}[{cat}] {g[0]['title']}")
                lines.append(f"- 매체 {len(outlets)}곳 · {' · '.join(outlets) or '미상'}"
                             f"{'  ← 여러 곳이 썼다' if len(g) > 1 else ''}")
                lines += photos.get(gi, [])
                for i in g[:4]:
                    summ = re.sub(r"\s+", " ", (i.get("summary") or "")).strip()
                    lines.append(f"  - {i.get('source_name', '?')}: {summ[:160]}")
                    if i.get("source_url"):
                        lines.append(f"    {i['source_url']}")
                lines.append("")
    lines.append(f"---\n거리 {total}건. 쓸 만한 것만 고른다 — 억지로 채우지 않는다.")

    # 연예 '방송' 재료(오늘·내일 방송 회차의 보도자료). 워크플로가 커밋하는 파일이
    # 이것뿐이라 여기에 덧붙인다 — 워크플로 파일은 이 저장소 토큰으로 못 고친다.
    # 수집이 실패해도 기사거리는 그대로 나가야 한다.
    try:
        import tv_material
        tv = tv_material.collect()
        lines += ["", "", tv_material.to_markdown(tv).replace("# 방송 재료", "# 방송 재료 —", 1)]
        print(f"방송 재료 {len(tv['items'])}건 {tv['counts']}"
              + (f" · 실패 {len(tv['errors'])}" if tv["errors"] else ""))
    except Exception as e:  # noqa: BLE001 — 어떤 실패도 기사거리를 막지 않는다
        lines += ["", f"(방송 재료 수집 실패: {e})"]
        print(f"방송 재료 수집 실패: {e}", file=sys.stderr)

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"기사거리 {total}건 → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
