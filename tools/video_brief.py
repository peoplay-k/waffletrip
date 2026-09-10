#!/usr/bin/env python3
"""와플트립 기사에서 그날의 영상 소재를 골라 대본 초안을 만든다.

**우리가 만든 것만 영상으로 만든다.** 인용 기사(B등급)는 남의 취재다.
그것을 우리 영상으로 재포장하면 남의 노동을 가져다 쓰는 것이 되고, 사진도
쓸 수 없다. 그래서 재료는 우리가 고르고 묶은 브리핑(C)과 우리가 만든
데이터(A)뿐이다.

브리핑 안의 개별 사실은 각 매체의 보도다. 대본에서 **출처를 말로 밝힌다** —
"여행신문 보도에 따르면". 무엇을 골랐고 어떻게 묶었는지가 우리 몫이고,
그 사실을 숨기지 않는 것이 큐레이션이 표절과 갈리는 지점이다.

대본은 초안이다. 숫자와 표현은 사람이 확인하고 내보낸다 — 검수는
자동화하지 않는다. 뉴스 채널은 정확도가 유일한 자산이라 근거 약한 한 편이
열흘치 신뢰를 깎는다.

    python tools/video_brief.py            # 오늘 소재 3편
    python tools/video_brief.py --count 5
    python tools/video_brief.py --json     # 파이프라인에 넘길 때
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cities import CITY_NAMES  # noqa: E402
from src.relevance import is_spam
from src.models import REGION_NAMES  # noqa: E402

# 한국인이 실제로 많이 가는 곳부터. 검색 수요가 곧 조회수다.
PRIORITY = ["tokyo", "osaka", "fukuoka", "sapporo", "okinawa", "bangkok",
            "taipei", "danang", "nhatrang", "japan", "vietnam", "thailand",
            "taiwan", "jeju", "guam", "saipan", "hawaii", "kota", "laos"]

SCENES = 6
CHARS_PER_SCENE = 42     # 한 장면 나레이션 길이. 6장면이면 35~50초가 된다.


def load_items(data_dir: str = "data") -> list[dict]:
    items, seen = [], set()
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["id"] not in seen:
                    seen.add(row["id"])
                    items.append(row)
    return items


def _topic_key(item: dict) -> str:
    """이 기사가 어느 목적지 이야기인가. 우선순위를 매기는 데 쓴다."""
    title = item.get("title") or ""
    for slug, name in CITY_NAMES.items():
        if f"이번 주 {name}에서" in title:
            return slug
    return item.get("region") or ""


def pick(items: list[dict], count: int = 3) -> list[dict]:
    """오늘 만들 소재. 목적지가 겹치지 않게 고른다.

    같은 날 도쿄 영상 둘을 올리면 서로 노출을 잠식한다. 목적지 하나에
    하루 한 편이다.
    """
    pool = [i for i in items
            if i.get("grade") == "C" and (i.get("body_md") or "").strip()]
    pool.sort(key=lambda i: i.get("published_at") or "", reverse=True)

    order = {slug: n for n, slug in enumerate(PRIORITY)}
    picked: list[dict] = []
    used: set[str] = set()
    for item in sorted(pool, key=lambda i: order.get(_topic_key(i), 99)):
        key = _topic_key(item)
        if key in used:
            continue
        used.add(key)
        picked.append(item)
        if len(picked) >= count:
            break
    return picked


_CITE = re.compile(r"^\*([^·*]+)·")
# 기사 앞머리의 매체·기자 표기. "[디스커버리뉴스=정기환 기자]" 를 읽어주면
# 대본이 우스워진다. 출처는 따로 말로 밝히므로 문장에서는 걷어낸다.
_DESK = re.compile(r"^\s*[\[\(【][^\]\)】]{0,40}[\]\)】]\s*")
_REPORTER = re.compile(r"[가-힣]{2,4}\s*기자\s*=?\s*")
# 통신사 전문(電文) 앞머리. "DNO - 9월 11일부터…" 처럼 지국 약어가 붙어 온다.
# 낭독하면 무슨 말인지 알 수 없다.
_WIRE = re.compile(r"^\s*[A-Z]{2,6}\s*[-–—]\s*")


def _speakable(text: str, limit: int) -> str:
    """읽을 수 있는 한 문장으로 다듬는다.

    글자 수로 자르면 "The Shop N.Y. 라운지" 처럼 말이 끊긴다. 문장 부호에서
    끊고, 그래도 길면 마지막 어절 경계에서 끊는다.
    """
    text = _DESK.sub("", (text or "").strip())
    text = _REPORTER.sub("", text)
    text = _WIRE.sub("", text).strip(" =·-—")
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?。])\s+", text)
    out = parts[0]
    for nxt in parts[1:]:
        if len(out) + len(nxt) + 1 > limit:
            break
        out = f"{out} {nxt}"
    if len(out) > limit:
        cut = out[:limit].rsplit(" ", 1)[0]
        out = cut if len(cut) >= limit * 0.6 else out[:limit]
    return out.rstrip(" ,·…").rstrip(".") or ""


def facts_from(item: dict, focus: str = "") -> list[dict]:
    """브리핑 본문에서 (사실, 출처) 쌍을 뽑는다. 지어내지 않는다.

    focus 가 있으면 **제목에 그 이름이 든 것을 앞으로** 보낸다. 브리핑은
    본문 어딘가에 도시가 스쳐도 담기므로, 도쿄 브리핑에 "뉴욕·도쿄 안
    부럽다… 서울 도심 호텔" 같은 서울 기사가 들어와 있었다. 영상은 한
    목적지를 말하는 것이라 그런 항목을 뒤로 미룬다.
    """
    body = item.get("body_md") or ""
    out: list[dict] = []
    blocks = re.split(r"^### ", body, flags=re.M)[1:]
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        headline = re.sub(r"^\d+\.\s*", "", lines[0])
        outlet, summary = "", ""
        for line in lines[1:]:
            if line.startswith("*") and "·" in line:
                m = _CITE.match(line)
                if m:
                    outlet = m.group(1).strip()
            elif not summary and not line.startswith(("*", "-", "#", ">")):
                summary = line
        # 신문에서 걸러낸 것은 영상에서도 걸러야 한다. 브리핑 본문은 스팸
        # 게이트가 생기기 전에 쓰인 것도 있어서, 2026-09-10 실측에서 다낭
        # 무음 영상 4번 장면에 카지노 홍보 글이 그대로 들어갔다
        # ("다낭카지노호텔 발표 능력을 통한 반성" · Histoire pour tous).
        # 영상은 되돌리기가 더 어렵다 — 여기서 한 번 더 막는다.
        if is_spam(f"{headline} {summary}", outlet):
            continue
        out.append({"headline": headline, "summary": summary, "outlet": outlet})
    if focus:
        # 제목에 그 이름이 없으면 **뺀다**. 뒤로 미루기만 했더니 "뉴욕·도쿄 안
        # 부럽다… 서울 도심 호텔" 같은 서울 기사가 도쿄 영상에 그대로 들어왔다.
        # 재료가 모자라면 장면을 줄인다 — 엉뚱한 사실을 채워 넣지 않는다.
        kept = [f for f in out if focus in f["headline"]]
        return kept or out[:1]
    return out


def script_for(item: dict) -> dict:
    """대본 초안. 장면마다 나레이션 한 줄과 화면에 띄울 글자 한 줄."""
    title = item.get("title") or ""
    name = title.replace("이번 주 ", "").split("에서")[0]
    facts = facts_from(item, focus=name)
    region_name = REGION_NAMES.get(item.get("region", ""), item.get("region", ""))

    scenes = [{
        "n": 1,
        "narration": f"{name} 가시는 분들, 이번 주 이것만 보세요.",
        "caption": f"{name} 이번 주",
        "screen": f"{name}\n이번 주 소식",
        "note": "첫 3초. 숫자나 단언으로 시작한다.",
    }]
    for n, fact in enumerate(facts[:SCENES - 2], start=2):
        cite = f"{fact['outlet']} 보도" if fact["outlet"] else "현지 보도"
        line = _speakable(fact["summary"] or fact["headline"], CHARS_PER_SCENE)
        if not line:
            continue
        off = "" if name in fact["headline"] else f"  ⚠ 제목에 '{name}' 없음"
        scenes.append({
            "n": n,
            "narration": f"{line}. {cite}입니다.",
            "caption": _speakable(fact["headline"], 26),
            # 화면 자막은 더 길게 잡는다. 26자에서 끊었더니 "…최대 150달러"
            # 처럼 말이 잘린 채 화면에 남았다. 네 줄까지 접힌다.
            "screen": _speakable(fact["headline"], 46),
            "note": f"출처 {fact['outlet'] or '미상'} — 말로 밝힐 것{off}",
        })
    scenes.append({
        "n": len(scenes) + 1,
        "narration": f"{name} 소식은 와플트립에서 매일 정리합니다.",
        "caption": "waffletrip.com",
        "screen": "매일 아침 8시\nwaffletrip.com",
        "note": "마무리 CTA. 채널 핸들은 개설 뒤 확정.",
    })
    return {
        "source_title": title,
        "region": region_name,
        "url": f"https://waffletrip.com/{item.get('region')}/",
        "scenes": scenes,
        "outlets": sorted({f["outlet"] for f in facts if f["outlet"]}),
        "seconds": round(sum(len(s["narration"]) for s in scenes) / 6.5),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="와플트립 영상 소재와 대본 초안")
    ap.add_argument("--count", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    picked = pick(load_items(args.data_dir), args.count)
    if not picked:
        print("영상으로 만들 자체 생산 기사가 없다. 오늘은 만들지 않는다.",
              file=sys.stderr)
        return 1

    scripts = [script_for(i) for i in picked]
    if args.json:
        print(json.dumps(scripts, ensure_ascii=False, indent=2))
        return 0

    for n, s in enumerate(scripts, 1):
        print(f"\n{'=' * 58}\n영상 {n} · {s['region']} · 약 {s['seconds']}초")
        print(f"소재: {s['source_title']}")
        print(f"인용 매체: {', '.join(s['outlets']) or '없음'}")
        print("-" * 58)
        for sc in s["scenes"]:
            print(f"  [{sc['n']}] {sc['narration']}")
            print(f"      자막: {sc['caption']}")
            print(f"      메모: {sc['note']}")
    print(f"\n{'=' * 58}")
    print("대본은 초안이다. 숫자와 표현을 사람이 확인한 뒤 제작한다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
