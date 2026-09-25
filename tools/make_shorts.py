#!/usr/bin/env python3
"""피플로드 쇼츠(9:16)를 만든다. 롱폼과 다른 물건이다.

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

from PIL import Image, ImageDraw, ImageOps

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



# ── 사진 ────────────────────────────────────────────────────────────
#
# 글자 카드만 넘어가는 영상은 릴스가 아니다. 2026-09-15 사장님 지적 —
# "사진도 없고 머하는건데?". 사진 153장을 갖고 있으면서 안 썼다.
#
# 사진은 **화면을 꽉 채우고**, 글자는 그 위에 얹는다. 읽히게 하려고
# 아래쪽에 어둠을 깐다. 사진이 없는 지역은 영상을 아예 만들지 않는다 —
# 글자만 있는 영상을 내느니 안 내는 편이 낫다.
def region_photos(region: str, city: str = "") -> list[str]:
    """그 지역 사진의 실제 파일 경로. 같은 장소가 몰리지 않게 섞는다.

    **도시가 맞는 사진을 먼저 쓴다.** 베트남 41장을 한 덩어리로 쓰면 다낭
    영상에 하노이·하롱베이 사진이 섞인다. 다낭 편에 하노이 훅교가 나오면
    그건 그냥 틀린 화면이다. 도시 태그가 있는 것 → 태그 없는 것(그 지역
    어디서나 통하는 사진) 순으로 주고, 다른 도시 사진은 주지 않는다.
    """
    from src.photos import load_manifest
    manifest = load_manifest()
    entries = [e for e in (manifest.get(region) or []) if e.get("file")]
    if city:
        mine = [e for e in entries if (e.get("city") or "") in ("", city)]
        if any((e.get("city") or "") == city for e in mine):
            entries = mine
        else:
            # 그 도시 사진이 한 장도 없으면 태그 없는 것만 쓴다
            entries = [e for e in entries if not (e.get("city") or "")]
    if not entries:
        return []
    # 원본 폴더가 곧 장소다. 폴더를 돌아가며 뽑아야 한 장소만 반복되지 않는다
    by_place: dict[str, list[str]] = {}
    for e in entries:
        place = os.path.basename(os.path.dirname(e.get("src") or "")) or "?"
        if os.path.exists(e["file"]):
            by_place.setdefault(place, []).append(e["file"])
    out, places = [], sorted(by_place)
    i = 0
    while any(by_place.values()):
        bucket = by_place[places[i % len(places)]]
        if bucket:
            out.append(bucket.pop(0))
        i += 1
    return out


def photo_bg(path: str) -> Image.Image:
    """사진을 세로 화면에 꽉 차게 자르고, 글자가 읽히게 어둠을 깐다."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    scale = max(W / im.width, H / im.height)
    im = im.resize((max(W, int(im.width * scale)), max(H, int(im.height * scale))),
                   Image.LANCZOS)
    left, top = (im.width - W) // 2, (im.height - H) // 2
    im = im.crop((left, top, left + W, top + H))

    # 위에서 아래로 짙어지는 막. 글자는 아래쪽에 앉는다.
    # 아래로 갈수록 짙어진다. 곡선이 완만하면 글자가 앉는 자리(화면 아래
    # 절반)가 덜 어두워, 밝은 건물이나 하늘 위에서 번호가 안 읽힌다 —
    # 2026-09-15 실측: "02 / 04" 가 성당 벽에 묻혔다.
    veil = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        veil.putpixel((0, y), min(250, int(30 + 215 * (t ** 1.15))))
    veil = veil.resize((W, H))
    return Image.composite(Image.new("RGB", (W, H), (8, 10, 14)), im, veil)


WHITE = (255, 255, 255)
DIM = (214, 218, 224)


def _base(photo: str | None = None):
    """사진이 있으면 화면을 꽉 채우고, 없으면 흰 지면으로 간다."""
    if photo:
        img = photo_bg(photo)
        ink, muted = WHITE, DIM
    else:
        img = Image.new("RGB", (W, H), PAPER)
        ink, muted = INK, MUTED
    d = ImageDraw.Draw(img)
    brand = _f(38)
    d.text((PAD, 96), "피플로드", font=brand, fill=ink)
    d.text((PAD + d.textlength("피플로드", font=brand), 96), ".",
           font=brand, fill=CORAL)
    return img, d, ink, muted


# 글자는 **아래쪽**에 앉힌다. 사진은 위가 넓게 보여야 사진값을 하고,
# 세 플랫폼 다 화면 아래를 UI 로 덮으므로 그 위 안전선까지만 쓴다.
TEXT_TOP = H - SAFE_BOTTOM - 660


def card_open(name: str, count: int, seconds: int = 40,
              photo: str | None = None) -> Image.Image:
    img, d, ink, muted = _base(photo)
    y = TEXT_TOP + 180
    d.text((PAD, y), "이번 주", font=_f(44), fill=CORAL)
    d.text((PAD, y + 70), name, font=_f(150), fill=ink)
    d.line([(PAD, y + 270), (PAD + 160, y + 270)], fill=CORAL, width=8)
    d.text((PAD, y + 310), f"소식 {count}건", font=_f(56), fill=muted)
    # 화면에 적는 숫자는 사실이어야 한다. 무음판은 길이가 대본마다 달라진다.
    d.text((PAD, H - SAFE_BOTTOM + 60), f"{seconds}초면 다 봅니다",
           font=_f(40), fill=muted)
    return img


def card_fact(n: int, total: int, headline: str, outlet: str,
              photo: str | None = None) -> Image.Image:
    img, d, ink, muted = _base(photo)
    head = _f(76)
    lines = _wrap(d, tidy(headline), head, W - PAD * 2)[:5]
    # 줄 수가 달라도 글자 덩어리의 **아래쪽**이 늘 같은 자리에 오게 한다.
    y = H - SAFE_BOTTOM - 40 - len(lines) * 104
    d.text((PAD, y - 80), f"{n:02d} / {total:02d}", font=_f(40), fill=CORAL)
    for line in lines:
        d.text((PAD, y), line, font=head, fill=ink)
        y += 104
    if outlet:
        d.text((PAD, H - SAFE_BOTTOM + 60), f"출처 · {outlet}",
               font=_f(38), fill=muted)
    return img


def card_close(photo: str | None = None) -> Image.Image:
    img, d, ink, muted = _base(photo)
    y = TEXT_TOP + 240
    d.text((PAD, y), "매일 아침 8시", font=_f(96), fill=ink)
    d.line([(PAD, y + 140), (PAD + 160, y + 140)], fill=CORAL, width=8)
    d.text((PAD, y + 190), "waffletrip.com", font=_f(64), fill=CORAL)
    d.text((PAD, y + 310), "여행 뉴스를 정리해 올립니다", font=_f(44), fill=muted)
    return img


def place_name(key: str) -> str:
    """도시든 지역이든 우리말 이름. 둘 다 받으므로 한 곳에서 찾는다."""
    return CITY_NAMES.get(key) or REGION_NAMES.get(key) or key


MIN_FACTS = 3           # 한 건짜리 영상은 릴스로 낼 값이 안 된다


def is_korean(text: str) -> bool:
    """우리말 글자가 절반을 넘나.

    지역 매체 제목이 영문 그대로 들어온다. 신문 지면은 `title_ko` 로 옮겨
    싣지만 브리핑 본문은 원문이라, 영상·캡션에는 영어가 그대로 나간다.
    2026-09-16 실측: 인스타에 "First Alert Forecast: Mostly dry trade winds"
    한 줄이 그대로 올라갔다. 한국어로 읽는 독자에게 그건 빈 화면과 같다.
    """
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    ko = sum(1 for c in letters if "\uac00" <= c <= "\ud7a3")
    return ko / len(letters) >= 0.5


MIN_PHOTOS = 5          # 장면 수만큼은 있어야 같은 사진이 반복되지 않는다


def build(city: str) -> list[dict]:
    """도시도 지역도 받는다.

    괌·사이판·코타키나발루는 도시 목록에 없고 **지역**이다. 그런데 사진이
    가장 많은 곳이 하필 거기다(괌 26·사이판 53·코타 25). 도시만 받으면
    사진이 제일 넉넉한 지면을 영상으로 못 만든다.
    """
    if city in CITY_NAMES:
        name, region = CITY_NAMES[city], CITY_REGION[city]
    elif city in REGION_NAMES:
        name, region = REGION_NAMES[city], city
        city = ""                       # 지역 전체 — 도시 태그로 거르지 않는다
    else:
        raise SystemExit(
            f"모르는 곳 '{city}'.\n  도시 {', '.join(CITY_NAMES)}\n"
            f"  지역 {', '.join(REGION_NAMES)}")
    items = load_items()
    pool = [i for i in items
            if i.get("grade") == "C"
            and (i.get("title") or "") == f"이번 주 {name}에서 나온 소식"
            or (i.get("grade") == "C"
                and (i.get("title") or "").startswith(f"이번 주 {name}에서"))]
    if not pool:
        raise SystemExit(f"{name} 브리핑이 없다. 기사가 더 쌓여야 한다.")
    pool.sort(key=lambda i: i.get("published_at") or "", reverse=True)
    facts = [f for f in facts_from(pool[0], focus=name)
             if is_korean(f.get("headline") or "")][:MAX_FACTS]
    if len(facts) < MIN_FACTS:
        raise SystemExit(
            f"{name} 은(는) 우리말 소식이 {len(facts)}건뿐이라 영상을 만들지 않는다.\n"
            f"  한 건짜리 영상은 릴스로 낼 값이 안 되고, 영문 제목은 한국어로\n"
            f"  읽는 독자에게 빈 화면과 같다.")

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
        "narration": "피플로드은 매일 아침 여덟 시에 여행 뉴스를 정리해 올립니다.",
    })

    # 장면마다 사진 한 장. 사진이 없으면 **영상을 만들지 않는다** —
    # 글자만 넘어가는 영상은 릴스가 아니다(2026-09-15 사장님 지적).
    photos = region_photos(region, city)
    if len(photos) < MIN_PHOTOS:
        raise SystemExit(
            f"{name} 은(는) 쓸 사진이 {len(photos)}장뿐이라 영상을 만들지 않는다.\n"
            f"  글자만 넘어가는 영상은 릴스가 아니고, 같은 사진을 돌려쓰면\n"
            f"  그것대로 티가 난다. NAS 에서 더 캐면 그때 생긴다.")
    for i, sc in enumerate(scenes):
        sc["photo"] = photos[i % len(photos)]
    return scenes


def render(scene: dict) -> Image.Image:
    ph = scene.get("photo")
    if scene["kind"] == "open":
        return card_open(scene["name"], scene["count"], photo=ph)
    if scene["kind"] == "close":
        return card_close(ph)
    return card_fact(scene["n"], scene["total"], scene["headline"],
                     scene.get("outlet", ""), ph)


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


def card_caption(n: int, total: int, caption: str, outlet: str,
                 photo: str | None = None) -> Image.Image:
    """무음판 사실 카드. 제목이 아니라 **읽어줄 문장**을 얹는다."""
    img, d, ink, muted = _base(photo)
    body = _f(64)
    lines = _wrap(d, tidy(caption), body, W - PAD * 2)[:8]
    y = H - SAFE_BOTTOM - 40 - len(lines) * 92
    d.text((PAD, y - 80), f"{n:02d} / {total:02d}", font=_f(40), fill=CORAL)
    for line in lines:
        d.text((PAD, y), line, font=body, fill=ink)
        y += 92
    if outlet:
        d.text((PAD, H - SAFE_BOTTOM + 60), f"출처 · {outlet}",
               font=_f(38), fill=muted)
    return img


def silent_text(scene: dict) -> str:
    """무음판 화면에 얹을 글. 사실 장면은 출처 꼬리를 뗀 문장만 쓴다."""
    if scene["kind"] == "fact":
        return scene.get("line") or scene["narration"]
    return scene["narration"]


def render_silent(scene: dict, seconds: int = 40) -> Image.Image:
    ph = scene.get("photo")
    if scene["kind"] == "open":
        return card_open(scene["name"], scene["count"], seconds, ph)
    if scene["kind"] == "close":
        return card_close(ph)
    return card_caption(scene["n"], scene["total"], silent_text(scene),
                        scene.get("outlet", ""), ph)


# 말이 끊긴 제목은 캡션에 쓰지 않는다. 원문이 잘려 들어오는 일이 있다 —
# 실측: "다낭 관광의 브랜드 이미지를 향상시키기 위해" 가 그대로 나갈 뻔했다.
# 영상 자막은 화면 안에서 맥락이 잡히지만, 캡션은 그 줄 하나만 읽힌다.
_DANGLING = ("위해", "위한", "통해", "대한", "따라", "하여", "으로", "로써",
             "에서", "관련", "맞아", "앞두고", "두고", "중인", "면서")


# RSS 제목 끝에 분류 딱지가 붙어 들어온다 —
# "…패키지 출시, , 생활/문화" 실측. 화면에 그대로 얹히면 기사 제목이 아니라
# 긁어온 티가 난다.
_TAIL_LABEL = re.compile(
    r"[,·\s]+(생활/문화|사회|경제|정치|국제|문화|스포츠|연예|종합|IT/과학)\s*$")


def tidy(text: str) -> str:
    """겹쉼표를 줄이고 끝에 붙은 분류 딱지를 뗀다."""
    t = re.sub(r"[ \t]+", " ", (text or "").strip())
    t = re.sub(r"(,\s*){2,}", ", ", t)
    for _ in range(3):
        new = _TAIL_LABEL.sub("", t).strip(" ,·")
        if new == t:
            break
        t = new
    return t


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
    name = place_name(city)
    heads = [h for h in ((sc.get("headline") or "").strip()
                         for sc in scenes if sc.get("kind") == "fact")
             if h and not _dangling(h)]
    # 건수는 **실제로 적은 줄 수**와 같아야 한다. 걸러낸 것까지 세면
    # 캡션이 사실과 어긋난다.
    lines = [f"{name} 이번 주 소식 {len(heads)}건", ""]
    lines += [f"· {tidy(h)}" for h in heads]
    outlets = outlets_of(scenes)
    lines += ["", f"인용 · {' · '.join(outlets)}" if outlets else "",
              "전문은 waffletrip.com", ""]
    tags = [f"#{name}", f"#{name}여행", f"#{name}자유여행"] + BIG_TAGS
    lines.append(" ".join(tags))
    return "\n".join(x for x in lines if x is not None).strip()


def build_voiced(city: str, out_dir: str) -> str:
    """나레이션을 얹은 숏폼. 장면 길이를 **말하는 길이**에 맞춘다.

    무음판은 읽는 속도로 길이를 잡았는데, 목소리가 생기면 그럴 이유가 없다.
    말이 끝나기 전에 화면이 넘어가면 문장이 잘린 것처럼 들린다 —
    말이 끝나고 짧게 숨을 두고 넘긴다.
    """
    import subprocess
    import tempfile

    import imageio_ffmpeg
    from narrate import speak

    scenes = build(city)
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    work = tempfile.mkdtemp(prefix="waffle-voiced-")
    TAIL = 0.6                      # 말끝에 두는 숨(초)

    parts, total = [], 0.0
    for n, scene in enumerate(scenes):
        mp3 = os.path.join(work, f"a{n:02d}.mp3")
        speak(scene["narration"], mp3)
        probe = subprocess.run([ff, "-i", mp3], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
        secs = ((int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)))
                if m else 4.0) + TAIL
        total += secs

        frame = os.path.join(work, f"f{n:02d}.png")
        render(scene).save(frame)
        clip = os.path.join(work, f"c{n:02d}.mp4")
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-loop", "1", "-i", frame, "-i", mp3,
            "-filter_complex",
            f"[1:a]apad=pad_dur={TAIL},aresample=44100[a];"
            f"[0:v]scale={W}:{H},format=yuv420p,fps={FPS}[v]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
            "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-t", f"{secs:.2f}", clip,
        ], check=True)
        parts.append(clip)

    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for clip in parts:
            fh.write(f"file '{os.path.abspath(clip)}'\n")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"waffletrip-{city}-voiced.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out], check=True)
    poster = out.rsplit(".", 1)[0] + ".jpg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "0.5", "-i", out,
                    "-frames:v", "1", "-q:v", "3", poster], check=True)
    _write_meta(city, scenes, out, poster, round(total, 1), "voiced")
    return out


def _write_meta(city, scenes, out, poster, seconds, kind):
    meta = {"city": city, "name": place_name(city),
            "caption": caption_for(city, scenes),
            "outlets": outlets_of(scenes), "kind": kind,
            "scenes": len(scenes), "seconds": seconds,
            "poster": "/video/" + os.path.basename(poster)}
    with open(out.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    latest = os.path.join("data", "shorts_latest.json")
    os.makedirs("data", exist_ok=True)
    stem = os.path.basename(out).rsplit(".", 1)[0]
    with open(latest, "w", encoding="utf-8") as fh:
        json.dump({"stem": stem, "city": city, "name": place_name(city),
                   "caption": meta["caption"], "seconds": seconds, "kind": kind,
                   "built_at": datetime.now(KST).isoformat(timespec="seconds")},
                  fh, ensure_ascii=False, indent=2)


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
        meta = {"city": city, "name": place_name(city),
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
                   "name": place_name(city), "caption": meta["caption"],
                   "seconds": meta["seconds"],
                   "built_at": datetime.now(KST).isoformat(timespec="seconds")},
                  fh, ensure_ascii=False, indent=2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="피플로드 쇼츠")
    ap.add_argument("--city", default="tokyo")
    ap.add_argument("--frames", default="")
    ap.add_argument("--script", action="store_true")
    ap.add_argument("--rotate", default="",
                    help="후보를 공백으로 나열한다. 오늘 날짜에서 시작해 "
                         "**만들 수 있는 첫 곳**을 만든다.")
    ap.add_argument("--voiced", action="store_true",
                    help="나레이션을 얹는다(일레븐랩스 · 크레딧 0원).")
    ap.add_argument("--silent", action="store_true",
                    help="무음 자막 영상을 만든다(나레이션 없음·비용 0).")
    ap.add_argument("--out", default="static/video")
    args = ap.parse_args()

    # 고정 도시로 하면 그날 그곳에 우리말 소식이 모자랄 때 아무것도 안
    # 나온다. 2026-09-16 실측: 다섯 곳 중 사이판 하나만 통과했다.
    # 순서는 유지하되(한 곳만 계속 나가지 않게) **되는 곳까지 내려간다.**
    if args.rotate:
        places = args.rotate.split()
        start = datetime.now(KST).toordinal() % len(places)
        order = places[start:] + places[:start]
        for place in order:
            try:
                scenes = build(place)
            except SystemExit as why:
                print(f"  건너뜀 · {place} — {str(why).splitlines()[0]}")
                continue
            args.city = place
            print(f"오늘 만들 곳: {place}")
            break
        else:
            print("오늘은 만들 수 있는 곳이 없다.", file=sys.stderr)
            return 0
    else:
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
    if args.voiced:
        out = build_voiced(args.city, args.out)
        print(f"나레이션 영상 → {out}")
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
