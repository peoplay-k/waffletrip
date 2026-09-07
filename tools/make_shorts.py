#!/usr/bin/env python3
"""와플트립 쇼츠(9:16)를 만든다. 롱폼과 다른 물건이다.

롱폼은 한 주치를 훑는 3분짜리이고, 쇼츠는 **한 도시 한 편**의 40초짜리다.
같은 재료를 잘라 쓰는 것이 아니라 구성을 따로 짠다 — 쇼츠는 첫 3초에
붙잡지 못하면 끝나고, 한 화면에 한 문장만 들어간다.

화면은 롱폼과 같은 지면 카드를 세로로 짠 것이다. 사진이 있으면 섞어 쓴다.
나레이션 파일은 이 도구가 만들지 않는다 — 대본을 내보내면 사람이 음성을
생성해 넣고 조립한다(크레딧이 드는 일을 자동으로 태우지 않는다).

    python3 tools/make_shorts.py --city tokyo --script      대본만
    python3 tools/make_shorts.py --city tokyo --frames DIR  화면까지
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw

from src.cities import CITY_NAMES, CITY_REGION
from src.models import REGION_NAMES
from make_longform import _f, _sentence, _wrap, CORAL, INK, LINE, MUTED, PAPER
from video_brief import _speakable, facts_from, load_items

W, H = 1080, 1920
PAD = 84
SAFE_BOTTOM = 420       # 세 플랫폼 모두 아래를 UI 로 덮는다
MAX_FACTS = 4


def _base():
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    brand = _f(38)
    d.text((PAD, 96), "와플트립", font=brand, fill=INK)
    d.text((PAD + d.textlength("와플트립", font=brand), 96), ".",
           font=brand, fill=CORAL)
    return img, d


def card_open(name: str, count: int) -> Image.Image:
    img, d = _base()
    d.text((PAD, H // 2 - 300), "이번 주", font=_f(44), fill=CORAL)
    big = _f(150)
    d.text((PAD, H // 2 - 230), name, font=big, fill=INK)
    d.line([(PAD, H // 2 - 30), (PAD + 160, H // 2 - 30)], fill=CORAL, width=8)
    d.text((PAD, H // 2 + 10), f"소식 {count}건", font=_f(56), fill=MUTED)
    d.text((PAD, H - SAFE_BOTTOM), "40초면 다 봅니다", font=_f(40), fill=MUTED)
    return img


def card_fact(n: int, total: int, headline: str, outlet: str) -> Image.Image:
    img, d = _base()
    d.text((PAD, 260), f"{n:02d} / {total:02d}", font=_f(40), fill=CORAL)
    head = _f(76)
    lines = _wrap(d, headline, head, W - PAD * 2)[:6]
    y = 340
    for line in lines:
        d.text((PAD, y), line, font=head, fill=INK)
        y += 104
    if outlet:
        d.text((PAD, H - SAFE_BOTTOM), f"출처 · {outlet}", font=_f(38), fill=MUTED)
    return img


def card_close() -> Image.Image:
    img, d = _base()
    d.text((PAD, H // 2 - 200), "매일 아침 8시", font=_f(96), fill=INK)
    d.line([(PAD, H // 2 - 60), (PAD + 160, H // 2 - 60)], fill=CORAL, width=8)
    d.text((PAD, H // 2 - 10), "waffletrip.com", font=_f(64), fill=CORAL)
    d.text((PAD, H // 2 + 110), "여행 뉴스를 정리해 올립니다", font=_f(44), fill=MUTED)
    return img


def build(city: str) -> list[dict]:
    if city not in CITY_NAMES:
        raise SystemExit(f"모르는 도시 '{city}'. {', '.join(CITY_NAMES)}")
    name = CITY_NAMES[city]
    region = CITY_REGION[city]
    items = load_items()
    pool = [i for i in items
            if i.get("grade") == "C"
            and (i.get("title") or "") == f"이번 주 {name}에서 나온 소식"
            or (i.get("grade") == "C"
                and (i.get("title") or "").startswith(f"이번 주 {name}에서"))]
    if not pool:
        raise SystemExit(f"{name} 브리핑이 없다. 기사가 더 쌓여야 한다.")
    pool.sort(key=lambda i: i.get("published_at") or "", reverse=True)
    facts = facts_from(pool[0], focus=name)[:MAX_FACTS]
    if not facts:
        raise SystemExit(f"{name} 브리핑에 쓸 사실이 없다.")

    scenes = [{
        "kind": "open", "name": name, "count": len(facts),
        "narration": f"{name} 가시는 분들, 이번 주 소식 {len(facts)}건입니다.",
    }]
    for n, fact in enumerate(facts, 1):
        # 쇼츠는 한 화면에 한 문장이다. 요약이 길면 제목만 읽는다.
        line = _sentence(fact["summary"], 70) or _speakable(fact["headline"], 70)
        if not line:
            continue
        cite = f"{fact['outlet']} 보도" if fact["outlet"] else "현지 보도"
        scenes.append({
            "kind": "fact", "n": n, "total": len(facts),
            "headline": _speakable(fact["headline"], 46),
            "outlet": fact["outlet"],
            "narration": f"{line}. {cite}입니다.",
        })
    scenes.append({
        "kind": "close",
        "narration": "와플트립은 매일 아침 여덟 시에 여행 뉴스를 정리해 올립니다.",
    })
    return scenes


def render(scene: dict) -> Image.Image:
    if scene["kind"] == "open":
        return card_open(scene["name"], scene["count"])
    if scene["kind"] == "close":
        return card_close()
    return card_fact(scene["n"], scene["total"], scene["headline"],
                     scene.get("outlet", ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="와플트립 쇼츠")
    ap.add_argument("--city", default="tokyo")
    ap.add_argument("--frames", default="")
    ap.add_argument("--script", action="store_true")
    args = ap.parse_args()

    scenes = build(args.city)
    chars = sum(len(s["narration"]) for s in scenes)
    print(f"장면 {len(scenes)}개 · {chars}자 · 예상 {chars // 6}초")
    for n, s in enumerate(scenes, 1):
        print(f"  [{n}] {s['narration']}")
    if args.frames:
        os.makedirs(args.frames, exist_ok=True)
        for n, s in enumerate(scenes):
            render(s).save(os.path.join(args.frames, f"s{n:02d}.png"))
        print(f"화면 {len(scenes)}장 → {args.frames}")
    with open("shorts_script.json", "w", encoding="utf-8") as fh:
        json.dump(scenes, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
