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
    python3 tools/make_shorts.py --city tokyo --silent      무음 자막 영상

**무음 자막(--silent)** 은 나레이션을 사지 않고 내는 판이다. 목소리가 없으므로
화면이 정보를 전부 져야 한다 — 읽어줄 문장을 그대로 카드에 얹고, 길이는
말하는 속도가 아니라 **읽는 속도**로 잡는다. 트렌드 음원을 얹는 포맷이라
소리가 없는 편이 오히려 맞는다. 크레딧이 들지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw

from src.cities import CITY_NAMES, CITY_REGION
from src.models import REGION_NAMES
from make_longform import _f, _sentence, _wrap, CORAL, INK, LINE, MUTED, PAPER
from video_brief import _speakable, facts_from, load_items

# 통신사 리드에서 앞머리를 뗀 뒤 남는 날짜 조각("1일 …", "9월 3일 …")
_LEDE_DATE = re.compile(r"^(\d{1,2}월\s*)?\d{1,2}일\s+")

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


def card_open(name: str, count: int, seconds: int = 40) -> Image.Image:
    img, d = _base()
    d.text((PAD, H // 2 - 300), "이번 주", font=_f(44), fill=CORAL)
    big = _f(150)
    d.text((PAD, H // 2 - 230), name, font=big, fill=INK)
    d.line([(PAD, H // 2 - 30), (PAD + 160, H // 2 - 30)], fill=CORAL, width=8)
    d.text((PAD, H // 2 + 10), f"소식 {count}건", font=_f(56), fill=MUTED)
    # 화면에 적는 숫자는 사실이어야 한다. 무음판은 길이가 대본마다 달라진다.
    d.text((PAD, H - SAFE_BOTTOM), f"{seconds}초면 다 봅니다", font=_f(40), fill=MUTED)
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
        summary = _sentence(fact["summary"], 70)
        # 통신사 리드는 "[서울=뉴시스] 홍길동 기자 = 1일 태국 방콕에…" 꼴이라,
        # 앞머리를 떼고 나면 날짜 조각으로 시작한다. 화면에 "1일 태국 방콕에
        # 위치한…" 이 걸리면 읽는 사람은 무슨 1일인지 알 수 없다. 날짜를
        # 잘라내는 대신 **제목으로 바꾼다** — "1일 왕복 2회" 같은 것을
        # 잘못 자르지 않으려면 이쪽이 안전하다.
        if _LEDE_DATE.match(summary or ""):
            summary = ""
        line = summary or _speakable(fact["headline"], 70)
        if not line:
            continue
        cite = f"{fact['outlet']} 보도" if fact["outlet"] else "현지 보도"
        scenes.append({
            "kind": "fact", "n": n, "total": len(facts),
            "headline": _speakable(fact["headline"], 46),
            "outlet": fact["outlet"],
            # 나레이션은 출처를 소리로 읽어야 하지만, 무음판은 카드 아래에
            # "출처 · vietnam.vn" 이 이미 있다. 자막에까지 넣으면 한 화면에
            # 같은 말이 두 번 나온다(2026-09-10 프레임 검수).
            "line": line.rstrip(". "),
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


# ── 무음 자막 ────────────────────────────────────────────────────────
# 목소리가 없으면 화면이 정보를 전부 져야 한다. 나레이션으로 읽어줄 문장을
# 그대로 얹는다. 짧게 줄이면 무음 영상은 아무 말도 하지 않는 영상이 된다.
KST = timezone(timedelta(hours=9))
FPS = 30
READ_CPS = 8.5          # 초당 읽는 글자. 폰으로 편하게 읽히는 속도
READ_FLOOR = 2.8        # 아무리 짧아도 이만큼은 둔다
READ_LEAD = 1.3         # 눈이 화면에 적응하는 시간


def read_seconds(text: str) -> float:
    """이 문장을 읽는 데 걸리는 시간. 말하는 속도가 아니다."""
    return round(max(READ_FLOOR, len(text or "") / READ_CPS + READ_LEAD), 2)


def card_caption(n: int, total: int, caption: str, outlet: str) -> Image.Image:
    """무음판 사실 카드. 제목이 아니라 **읽어줄 문장**을 얹는다."""
    img, d = _base()
    d.text((PAD, 250), f"{n:02d} / {total:02d}", font=_f(40), fill=CORAL)
    body = _f(64)
    lines = _wrap(d, caption, body, W - PAD * 2)[:9]
    y = 330
    for line in lines:
        d.text((PAD, y), line, font=body, fill=INK)
        y += 92
    if outlet:
        d.text((PAD, H - SAFE_BOTTOM), f"출처 · {outlet}", font=_f(38), fill=MUTED)
    return img


def silent_text(scene: dict) -> str:
    """무음판 화면에 얹을 글. 사실 장면은 출처 꼬리를 뗀 문장만 쓴다."""
    if scene["kind"] == "fact":
        return scene.get("line") or scene["narration"]
    return scene["narration"]


def render_silent(scene: dict, seconds: int = 40) -> Image.Image:
    if scene["kind"] == "open":
        return card_open(scene["name"], scene["count"], seconds)
    if scene["kind"] == "close":
        return card_close()
    return card_caption(scene["n"], scene["total"],
                        silent_text(scene), scene.get("outlet", ""))


# 말이 끊긴 제목은 캡션에 쓰지 않는다. 원문이 잘려 들어오는 일이 있다 —
# 실측: "다낭 관광의 브랜드 이미지를 향상시키기 위해" 가 그대로 나갈 뻔했다.
# 영상 자막은 화면 안에서 맥락이 잡히지만, 캡션은 그 줄 하나만 읽힌다.
_DANGLING = ("위해", "위한", "통해", "대한", "따라", "하여", "으로", "로써",
             "에서", "관련", "맞아", "앞두고", "두고", "중인", "면서")


def _dangling(head: str) -> bool:
    return head.endswith(_DANGLING)


def outlets_of(scenes: list[dict]) -> list[str]:
    """인용한 매체. 사실은 각 매체의 보도이고 우리가 한 것은 고르고 묶은 일이다."""
    out, seen = [], set()
    for sc in scenes:
        o = (sc.get("outlet") or "").strip()
        if o and o not in seen:
            seen.add(o)
            out.append(o)
    return out


# 해시태그는 **큰 것부터** 단다. 팔로워가 적은 계정은 도달이 거의 전부
# 탐색 탭에서 오는데, 니치 태그만 달면 노출 면적 자체가 사라진다.
# (실측: 니치만 달았을 때 도달 197 → 83)
BIG_TAGS = ["#여행", "#해외여행", "#여행스타그램", "#여행에미치다", "#travel"]


def caption_for(city: str, scenes: list[dict]) -> str:
    """지면에 실은 사실만 옮긴다. 영상에 없는 말은 캡션에도 쓰지 않는다."""
    name = CITY_NAMES[city]
    heads = [h for h in ((sc.get("headline") or "").strip()
                         for sc in scenes if sc.get("kind") == "fact")
             if h and not _dangling(h)]
    # 건수는 **실제로 적은 줄 수**와 같아야 한다. 걸러낸 것까지 세면
    # 캡션이 사실과 어긋난다.
    lines = [f"{name} 이번 주 소식 {len(heads)}건", ""]
    lines += [f"· {h}" for h in heads]
    outlets = outlets_of(scenes)
    lines += ["", f"인용 · {' · '.join(outlets)}" if outlets else "",
              "전문은 waffletrip.com", ""]
    tags = [f"#{name}", f"#{name}여행", f"#{name}자유여행"] + BIG_TAGS
    lines.append(" ".join(tags))
    return "\n".join(x for x in lines if x is not None).strip()


def build_silent(city: str, out_dir: str) -> str:
    """무음 자막 쇼츠를 만든다. 오디오 트랙이 아예 없다."""
    import subprocess
    import tempfile
    import imageio_ffmpeg

    scenes = build(city)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    work = tempfile.mkdtemp(prefix="waffle-shorts-")
    # 여는 카드에 전체 길이를 적으므로 길이를 먼저 다 잰다.
    durations = [read_seconds(silent_text(sc)) for sc in scenes]
    total_sec = sum(durations)
    parts = []
    for n, scene in enumerate(scenes):
        frame = os.path.join(work, f"f{n:02d}.png")
        render_silent(scene, round(total_sec)).save(frame)
        seconds = durations[n]
        clip = os.path.join(work, f"c{n:02d}.mp4")
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-loop", "1", "-i", frame,
            "-t", str(seconds), "-vf", f"fps={FPS},format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23", clip,
        ], check=True)
        parts.append(clip)

    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for clip in parts:
            fh.write(f"file '{clip}'\n")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"waffletrip-{city}-silent.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out], check=True)
    poster = out.rsplit(".", 1)[0] + ".jpg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "0.5", "-i", out,
                    "-frames:v", "1", "-q:v", "3", poster], check=True)
    meta = out.rsplit(".", 1)[0] + ".json"
    with open(meta, "w", encoding="utf-8") as fh:
        meta = {"city": city, "name": CITY_NAMES[city],
                "caption": caption_for(city, scenes),
                "outlets": outlets_of(scenes),
                "kind": "silent", "scenes": len(scenes),
                "seconds": round(total_sec, 1),
                "poster": "/video/" + os.path.basename(poster),
                "note": "무음. 발행 앱에서 트렌드 음원을 얹는다."}
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    # 발행 잡은 저장소를 새로 받아온다. `static/video` 의 숏폼 메타는
    # gitignore 라 거기엔 없다. 그래서 **글자만 담은 작은 파일**을 따로
    # 남겨 커밋한다 — 이게 없으면 발행기가 오늘 뭘 올릴지 알 수 없다.
    latest = os.path.join("data", "shorts_latest.json")
    os.makedirs("data", exist_ok=True)
    with open(latest, "w", encoding="utf-8") as fh:
        json.dump({"stem": f"waffletrip-{city}-silent", "city": city,
                   "name": CITY_NAMES[city], "caption": meta["caption"],
                   "seconds": meta["seconds"],
                   "built_at": datetime.now(KST).isoformat(timespec="seconds")},
                  fh, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="와플트립 쇼츠")
    ap.add_argument("--city", default="tokyo")
    ap.add_argument("--frames", default="")
    ap.add_argument("--script", action="store_true")
    ap.add_argument("--silent", action="store_true",
                    help="무음 자막 영상을 만든다(나레이션 없음·비용 0).")
    ap.add_argument("--out", default="static/video")
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
    if args.silent:
        out = build_silent(args.city, args.out)
        seconds = sum(read_seconds(silent_text(sc)) for sc in scenes)
        print(f"무음 자막 영상 → {out} ({seconds:.1f}초)")
        print("  나레이션 없음. 발행 앱에서 트렌드 음원을 얹는다.")
    with open("shorts_script.json", "w", encoding="utf-8") as fh:
        json.dump(scenes, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
