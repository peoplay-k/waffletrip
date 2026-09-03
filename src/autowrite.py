"""우리 데이터로 매일 기사 한 편을 만든다.

지면에 우리가 쓴 글이 0건이면 그건 신문이 아니라 모음집이다. 그렇다고
없는 사실을 지어낼 수는 없다. 그래서 **우리가 직접 만든 데이터만으로**
쓸 수 있는 기사를 자동 생성한다.

재료는 A등급 항목(환율·날씨)이다. 남의 것이 아니라 매일 아침 우리가
공개 API 에서 받아 정리한 값이고, 누구나 검증할 수 있다.

**지어내지 않는다.** 이 모듈은 이미 수집된 숫자를 표로 옮기고 문장을
붙일 뿐이다. 데이터가 없으면 기사를 만들지 않는다.
"""
from __future__ import annotations

import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone

from src.desks import DATA_DESK
from src.models import Item, make_id, title_hash

KST = timezone(timedelta(hours=9))

from src.models import REGION_NAMES  # 정본은 models.py

_WEATHER = re.compile(
    r"\S+\s+(?P<city>\S+)\s+(?P<sky>[^,]+),\s*최고\s*(?P<hi>-?\d+)°C"
    r"\s*·\s*최저\s*(?P<lo>-?\d+)°C(?:\s*·\s*강수확률\s*(?P<rain>\d+)%)?")
_FX = re.compile(r"기준\s+(?P<unit>[\d,]+)\s+(?P<cur>[A-Z]{3})\s*=\s*약\s*(?P<krw>[\d,.]+)원")


def _parse(items):
    """A등급 항목에서 지역별 날씨·환율을 뽑는다."""
    weather, fx = {}, {}
    for it in items:
        if getattr(it, "grade", "") != "A":
            continue
        s = getattr(it, "summary", "") or ""
        r = getattr(it, "region", "")
        m = _WEATHER.search(s)
        if m:
            weather[r] = m.groupdict()
            continue
        m = _FX.search(s)
        if m:
            fx[r] = m.groupdict()
    return weather, fx


def _load_history(data_dir: str, days: int = 8) -> dict:
    """지난 며칠치 환율을 읽는다. 비교 문장을 쓰기 위한 것."""
    out: dict[str, dict[str, float]] = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl")))[-days:]:
        day = os.path.basename(path)[:-6]
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("grade") != "A":
                continue
            m = _FX.search(d.get("summary", "") or "")
            if m:
                try:
                    out.setdefault(day, {})[d["region"]] = float(
                        m.group("krw").replace(",", ""))
                except ValueError:
                    pass
    return out


ROUNDUP_MIN = 3        # 이보다 적으면 브리핑을 만들지 않는다


def build_roundup(recent, region: str, day: str, days: int = 7) -> Item | None:
    """지역별 주간 브리핑.

    지난 이레 동안 그 지역에서 무엇이 있었는지 골라 묶는다. 사실은 각 매체의
    보도이고 **무엇을 고르고 어떻게 묶는지가 우리 몫**이다. 신문의 주간
    브리핑이 원래 그런 것이다.

    본문을 옮기지 않는다. 제목과 한 줄, 그리고 원문으로 가는 링크만 남긴다.
    소식이 세 건에 못 미치면 만들지 않는다 — 두 건짜리 '브리핑'은 브리핑이 아니다.
    """
    from datetime import date, timedelta as _td
    cutoff = (date.fromisoformat(day) - _td(days=days)).isoformat()

    picked = [i for i in recent
              if getattr(i, "region", "") == region
              and getattr(i, "grade", "") == "B"
              and (getattr(i, "published_at", "") or "")[:10] >= cutoff]
    if len(picked) < ROUNDUP_MIN:
        return None

    picked.sort(key=lambda i: i.published_at, reverse=True)
    picked = picked[:8]
    name = REGION_NAMES.get(region, region)
    now = datetime.now(KST).isoformat(timespec="seconds")
    head = f"이번 주 {name}에서 나온 소식 {len(picked)}건"

    lines = [
        f"> 지난 이레 동안 {name} 관련 보도 가운데 여행자에게 쓸모 있는 것을 "
        "골라 묶었습니다. 각 항목의 사실은 해당 매체의 보도이며, 제목을 누르면 "
        "저희가 정리한 쪽으로, 그 쪽에서 원문으로 갈 수 있습니다.\n",
    ]
    for n, it in enumerate(picked, 1):
        lines.append(f"### {n}. {it.title}")
        if it.summary:
            lines.append(f"\n{it.summary}\n")
        lines.append(f"*{it.source_name} · {it.published_at[:10]}*\n")

    lines.append("---\n")
    outlets = sorted({i.source_name for i in picked if i.source_name})
    lines.append(f"**이번 주 참고한 매체** · {' · '.join(outlets)}")
    lines.append(f"\n오늘 {name}의 날씨와 환율은 [{name} 지역면](/{region}/)에서 "
                 "매일 갱신됩니다.")

    return Item(
        id=make_id("", f"roundup|{region}|{day}", day),
        grade="C", region=region, section="news",
        title=head,
        summary=f"지난 이레 {name} 소식 {len(picked)}건을 골라 묶었습니다.",
        source_name="", source_url="",
        published_at=now, collected_at=now, status="published",
        title_hash=title_hash(head), body_md="\n".join(lines).strip(),
    )


def build_daily(items, day: str, data_dir: str = "data") -> Item | None:
    """오늘의 데이터 기사. 재료가 없으면 만들지 않는다."""
    weather, fx = _parse(items)
    if not weather and not fx:
        return None

    now = datetime.now(KST).isoformat(timespec="seconds")
    order = [r for r in REGION_NAMES if r in weather or r in fx]

    # 제목은 오늘 가장 더운 곳으로 잡는다. 매일 달라지고 사실이다.
    hottest = max((int(w["hi"]), r) for r, w in weather.items()) if weather else None
    if hottest:
        head = f"{day[5:7]}월 {int(day[8:10])}일 여행 데이터 — {REGION_NAMES[hottest[1]]} {hottest[0]}°C"
    else:
        head = f"{day[5:7]}월 {int(day[8:10])}일 여행 데이터"

    lines = [
        "> 이 기사는 저희가 매일 아침 직접 수집한 값을 정리한 것입니다. "
        "환율은 공개 환율 API, 날씨는 Open-Meteo 예보를 씁니다. "
        "사람이 쓴 해설이 아니라 데이터 정리 기사입니다.\n",
    ]

    if weather:
        lines.append("## 오늘의 날씨\n")
        lines.append("| 지역 | 최고 | 최저 | 하늘 | 강수확률 |")
        lines.append("|---|---|---|---|---|")
        for r in order:
            w = weather.get(r)
            if not w:
                continue
            rain = f"{w['rain']}%" if w["rain"] else "—"
            lines.append(f"| {REGION_NAMES[r]} | {w['hi']}°C | {w['lo']}°C | "
                         f"{w['sky'].strip()} | {rain} |")
        lines.append("")

    if fx:
        lines.append("## 오늘의 환율\n")
        lines.append("| 지역 | 통화 | 원화 |")
        lines.append("|---|---|---|")
        for r in order:
            f = fx.get(r)
            if not f:
                continue
            lines.append(f"| {REGION_NAMES[r]} | {f['unit']} {f['cur']} | {f['krw']}원 |")
        lines.append("")
        lines.append("제주는 원화권이라 환율 항목이 없습니다.\n")

    # 어제와 비교. 이력이 없으면 이 문단을 아예 쓰지 않는다.
    history = _load_history(data_dir)
    days_sorted = sorted(history)
    if len(days_sorted) >= 2:
        today_fx = history.get(days_sorted[-1], {})
        prev_fx = history.get(days_sorted[-2], {})
        moves = []
        for r in order:
            a, b = today_fx.get(r), prev_fx.get(r)
            if a and b and abs(a - b) >= 0.5:
                arrow = "올랐고" if a > b else "내렸고"
                moves.append(f"{REGION_NAMES[r]} {abs(a-b):,.0f}원 {arrow}")
        if moves:
            lines.append("## 어제와 비교\n")
            lines.append(", ".join(moves).rstrip("고") + "습니다. "
                         f"({days_sorted[-2]} 대비)\n")

    body = "\n".join(lines).strip()
    summary = (f"{len(weather)}개 지역의 오늘 날씨와 환율입니다. "
               "매일 아침 자동으로 정리합니다.")

    return Item(
        id=make_id("", f"daily-data|{day}", day),
        grade="C", region="guam" if "guam" in order else (order[0] if order else "guam"),
        section="data", title=head, summary=summary,
        source_name=DATA_DESK, source_url="",
        published_at=now, collected_at=now, status="published",
        title_hash=title_hash(head), body_md=body,
    )
