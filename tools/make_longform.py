#!/usr/bin/env python3
"""피플로드 롱폼(16:9)을 만든다. 사진 없이 지면처럼 보이는 카드로 채운다.

사진이 모자라 만든 방식이 아니라, 뉴스 롱폼이 원래 쓰는 방식이다. 우리가
가진 것은 **글과 숫자**이고 그것을 읽기 좋게 짜면 화면이 된다. 사진은
들어오는 대로 섞어 쓴다(--photos).

한 주치 브리핑을 지역별로 묶어 3~5분으로 낸다. 숏폼이 한 지역 한 편이라면
롱폼은 "이번 주 여행 뉴스" 한 편이다.

    python tools/make_longform.py --script-only     # 대본만 (크레딧 0)
    python tools/make_longform.py --voice-id <id>   # 나레이션까지
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from src.brand import DOMAIN, SITE_URL  # noqa: E402 — 정본은 brand.py
from src.models import REGION_NAMES  # noqa: E402
from video_brief import _speakable, facts_from, load_items  # noqa: E402


def _sentence(text: str, limit: int) -> str:
    """**완결된 문장**만 돌려준다. 잘릴 것 같으면 빈 값이다.

    글자 수로 자르면 "…항공기 6대를." 처럼 말이 끊긴 채 낭독된다. 읽는
    사람이 없는 영상에서 그건 그냥 틀린 문장이다. 자를 바에는 쓰지 않는다.
    """
    first = re.split(r"(?<=[.!?。])\s+", (text or "").strip())[0]
    first = _speakable(first, limit + 40)
    if not first or len(first) > limit:
        return ""
    return first

KST = timezone(timedelta(hours=9))
# 통신사 리드에서 앞머리를 뗀 뒤 남는 날짜 조각("1일 …", "9월 3일 …")
_LEDE_DATE = re.compile(r"^(\d{1,2}월\s*)?\d{1,2}일\s+")

W, H = 1920, 1080
# 한글 폰트. 맥에서 만들고 리눅스(CI)에서도 만든다. 리눅스 러너에는 애플
# 폰트가 없고, PIL 의 기본 폰트는 한글을 못 그려 화면이 네모로 찬다.
# 그래서 있는 것을 골라 쓴다 — 없으면 만들지 않고 왜 못 만드는지 말한다.
_FONT_CANDIDATES = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",                 # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",     # Debian/Ubuntu
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
)


def _find_font() -> str:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return ""


FONT = _find_font()
PAD = 132

# 사이트와 같은 색을 쓴다. 영상만 다른 색이면 같은 매체로 보이지 않는다.
INK = (14, 14, 15)
PAPER = (250, 250, 249)
CORAL = (240, 78, 55)
MUTED = (110, 110, 115)
LINE = (225, 225, 220)

# 한 편에 담을 지역. 한국인이 많이 가는 곳부터.
ORDER = ["japan", "vietnam", "thailand", "taiwan", "jeju",
         "guam", "saipan", "hawaii", "kota", "laos"]
PER_REGION = 2          # 지역마다 기사 두 건. 더 넣으면 지루해진다.
MAX_REGIONS = 6


def _f(size: int, weight: int = 0):
    """한글 폰트를 연다. 없으면 조용히 넘어가지 않고 멈춘다.

    기본 폰트로 물러나면 한글이 전부 네모로 그려진 화면이 만들어진다.
    깨진 화면을 만드는 것보다 만들지 않는 편이 낫다.
    """
    if not FONT:
        raise RuntimeError(
            "한글 폰트를 찾지 못했다. 화면을 만들지 않는다.\n"
            "  우분투: sudo apt-get install -y fonts-noto-cjk")
    try:
        return ImageFont.truetype(FONT, size, index=weight)
    except OSError as e:
        raise RuntimeError(f"폰트를 열지 못했다: {FONT} — {e}") from e


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    # 제호는 늘 같은 자리에. 어느 장면을 캡처해도 매체를 알 수 있어야 한다.
    brand = _f(34)
    d.text((PAD, 64), "피플로드", font=brand, fill=INK)
    d.text((PAD + d.textlength("피플로드", font=brand), 64), ".",
           font=brand, fill=CORAL)
    d.line([(PAD, H - 96), (W - PAD, H - 96)], fill=LINE, width=2)
    d.text((PAD, H - 78), DOMAIN, font=_f(26), fill=MUTED)
    return img, d


def card_title(headline: str, sub: str) -> Image.Image:
    img, d = _base()
    big = _f(96)
    lines = _wrap(d, headline, big, W - PAD * 2)[:3]
    y = H // 2 - len(lines) * 62 - 40
    for line in lines:
        d.text((PAD, y), line, font=big, fill=INK)
        y += 124
    d.text((PAD, y + 24), sub, font=_f(40), fill=MUTED)
    d.line([(PAD, y + 8), (PAD + 120, y + 8)], fill=CORAL, width=6)
    return img


def card_section(name: str, count: int) -> Image.Image:
    img, d = _base()
    d.text((PAD, H // 2 - 130), "지역", font=_f(34), fill=CORAL)
    d.text((PAD, H // 2 - 80), name, font=_f(140), fill=INK)
    d.text((PAD, H // 2 + 96), f"이번 주 {count}건", font=_f(42), fill=MUTED)
    return img


def card_story(headline: str, summary: str, outlet: str, n: int,
               total: int) -> Image.Image:
    img, d = _base()
    d.text((PAD, 190), f"{n:02d} / {total:02d}", font=_f(32), fill=CORAL)
    head = _f(64)
    lines = _wrap(d, headline, head, W - PAD * 2)[:3]
    y = 260
    for line in lines:
        d.text((PAD, y), line, font=head, fill=INK)
        y += 86
    if summary:
        y += 26
        body = _f(40)
        for line in _wrap(d, summary, body, W - PAD * 2)[:4]:
            d.text((PAD, y), line, font=body, fill=MUTED)
            y += 58
    if outlet:
        d.text((PAD, H - 190), f"출처 · {outlet}", font=_f(32), fill=MUTED)
    return img


def card_data(rows: list[tuple[str, str]]) -> Image.Image:
    img, d = _base()
    d.text((PAD, 190), "오늘의 데이터", font=_f(34), fill=CORAL)
    d.text((PAD, 240), "환율과 날씨는 저희가 매일 직접 만듭니다",
           font=_f(40), fill=MUTED)
    # 줄 수가 늘면 **간격도 글자도** 같이 줄인다. 셋 다 고정이었더니
    # 2026-09-15 라이브에서 두 번 깨졌다 — 일곱 줄일 때는 마지막 밑줄이
    # 바닥선을 넘었고, 간격만 줄였더니 이번엔 밑줄이 값 글자를 관통했다.
    top, floor_y = 370, H - 96 - 40     # 바닥선 위로 40px 은 비워 둔다
    rows = rows[:9]
    pitch = min(96, (floor_y - top) // max(len(rows), 1))
    name_f = _f(min(48, pitch - 26))
    value_f = _f(min(42, pitch - 32))

    # 값이 시작하는 자리는 **가장 긴 이름** 뒤로 잡는다. 300 으로 박아
    # 뒀더니 "코타키나발루" 가 값과 맞붙었다.
    label_w = max((d.textlength(n, font=name_f) for n, _ in rows), default=0)
    value_x = PAD + max(300, int(label_w) + 48)

    y = top
    for name, value in rows:
        d.text((PAD, y), name, font=name_f, fill=INK)
        d.text((value_x, y + 6), value, font=value_f, fill=MUTED)
        # 밑줄은 글자 아래로. 글자 높이를 재서 그 밑에 긋는다.
        below = max(d.textbbox((0, y), name, font=name_f)[3],
                    d.textbbox((0, y + 6), value, font=value_f)[3])
        d.line([(PAD, below + 8), (W - PAD, below + 8)], fill=LINE, width=2)
        y += pitch
    return img


def build_script(items: list[dict]) -> list[dict]:
    """한 주치 브리핑에서 롱폼 대본을 짠다. 사실은 전부 기사에서 온다."""
    roundups = [i for i in items
                if i.get("grade") == "C"
                and (i.get("title") or "").startswith("이번 주 ")
                and (i.get("body_md") or "").strip()]
    # **가장 최근 브리핑을 쓴다.** load_items() 가 날짜 오름차순으로 주므로
    # setdefault 로 담으면 보관된 것 중 **가장 오래된** 브리핑이 잡힌다.
    # 2026-09-15 실측: 9월 15일에 만든 영상이 9월 6일 브리핑으로 채워졌다.
    # 제목 카드만 오늘 날짜라, 날짜와 내용이 어긋난 화면이 나갔다.
    by_region: dict[str, dict] = {}
    for item in roundups:
        # 지역면 브리핑을 쓴다. 도시 브리핑은 그 안에 이미 담겨 있다.
        name = item["title"].replace("이번 주 ", "").split("에서")[0]
        if name != REGION_NAMES.get(item.get("region", ""), ""):
            continue
        prev = by_region.get(item["region"])
        if prev is None or (item.get("published_at") or "") >= (prev.get("published_at") or ""):
            by_region[item["region"]] = item

    scenes: list[dict] = []
    today = max((i.get("published_at") or "")[:10] for i in items)
    scenes.append({
        "kind": "title",
        "narration": "안녕하세요, 피플로드입니다. 이번 주 여행 뉴스를 정리해 드립니다.",
        "headline": "이번 주 여행 뉴스",
        "sub": f"{today[:4]}년 {int(today[5:7])}월 {int(today[8:10])}일 · 피플로드",
    })

    facts_rows = []
    for region in ORDER:
        # **오늘 값**이어야 한다. 화면과 나레이션이 "오늘의 환율"이라고 말한다.
        # 오름차순 목록을 앞에서부터 훑으면 보관된 것 중 가장 오래된 값이
        # 잡힌다 — 2026-09-15 실측: 9월 3일의 855원이 "오늘의 환율"로 나갔고
        # 그날 실제 값은 871원이었다. 16원 틀린 숫자를 화면에 박은 것이다.
        for item in reversed(items):
            if (item.get("grade") == "A" and item.get("region") == region
                    and "환율" in (item.get("title") or "")):
                value = (item.get("summary") or "").strip()
                # "2026-09-03 기준 100 JPY = 약 855원" 에서 날짜를 뗀다.
                # 화면에는 오늘 값만 걸리므로 날짜를 읽어줄 이유가 없다.
                value = re.sub(r"^\d{4}-\d{2}-\d{2}\s*기준\s*", "", value)
                if value:
                    facts_rows.append((REGION_NAMES.get(region, region), value))
                break
    if facts_rows:
        spoken = ", ".join(f"{n}은 {v}" for n, v in facts_rows[:3])
        scenes.append({
            "kind": "data", "rows": facts_rows,
            "narration": f"먼저 오늘의 환율입니다. {spoken}. "
                         "환율과 날씨는 저희가 매일 직접 만드는 값입니다.",
        })

    used = 0
    for region in ORDER:
        item = by_region.get(region)
        if not item or used >= MAX_REGIONS:
            continue
        name = REGION_NAMES.get(region, region)
        facts = [f for f in facts_from(item, focus=name)][:PER_REGION]
        if not facts:
            continue
        used += 1
        scenes.append({
            "kind": "section", "name": name, "region": region,
            "count": len(facts),
            "narration": f"{name} 소식입니다.",
        })
        for n, fact in enumerate(facts, 1):
            # 요약이 한 문장으로 끝나면 그걸 읽고, 아니면 제목을 읽는다.
            # 제목은 원래 한 덩어리라 중간에서 끊기지 않는다.
            summary = _sentence(fact["summary"], 100)
            # 통신사 리드는 "[서울=뉴시스] 홍길동 기자 = 1일 태국 방콕에…" 꼴이라,
            # 앞머리를 떼고 나면 날짜 조각으로 시작한다. 화면에 "1일 태국 방콕에
            # 위치한…" 이 걸리면 읽는 사람은 무슨 1일인지 알 수 없다. 날짜를
            # 잘라내는 대신 **제목으로 바꾼다** — "1일 왕복 2회" 같은 것을
            # 잘못 자르지 않으려면 이쪽이 안전하다.
            if _LEDE_DATE.match(summary or ""):
                summary = ""
            line = summary or _speakable(fact["headline"], 100)
            if not line:
                continue
            cite = f"{fact['outlet']} 보도" if fact["outlet"] else "현지 보도"
            scenes.append({
                "kind": "story", "n": n, "total": len(facts),
                "headline": _speakable(fact["headline"], 60),
                "summary": _speakable(fact["summary"], 150),
                "outlet": fact["outlet"],
                "narration": f"{line}. {cite}입니다.",
            })

    scenes.append({
        "kind": "title",
        "headline": "매일 아침 8시",
        "sub": DOMAIN,
        "narration": "피플로드은 매일 아침 여덟 시에 새 기사를 올립니다. "
                     f"{DOMAIN} 에서 보실 수 있습니다.",
    })
    return scenes


def render(scene: dict) -> Image.Image:
    kind = scene["kind"]
    if kind == "title":
        return card_title(scene["headline"], scene["sub"])
    if kind == "section":
        return card_section(scene["name"], scene["count"])
    if kind == "data":
        return card_data(scene["rows"])
    return card_story(scene["headline"], scene.get("summary", ""),
                      scene.get("outlet", ""), scene["n"], scene["total"])


def main() -> int:
    ap = argparse.ArgumentParser(description="피플로드 롱폼")
    ap.add_argument("--script-only", action="store_true")
    ap.add_argument("--out", default="public/video")
    ap.add_argument("--frames", default="")
    ap.add_argument("--silent", action="store_true",
                    help="무음 영상까지 굽는다(나레이션 없음·비용 0원).")
    args = ap.parse_args()

    scenes = build_script(load_items())
    chars = sum(len(s["narration"]) for s in scenes)
    print(f"장면 {len(scenes)}개 · 나레이션 {chars}자 · 예상 {chars // 6}초")
    for n, s in enumerate(scenes, 1):
        print(f"  [{n:02d}] {s['kind']:8} {s['narration'][:64]}")

    if args.frames:
        os.makedirs(args.frames, exist_ok=True)
        for n, s in enumerate(scenes):
            render(s).save(os.path.join(args.frames, f"s{n:02d}.png"))
        print(f"화면 {len(scenes)}장 → {args.frames}")

    if args.silent:
        out = build_silent(scenes, args.out)
        secs = sum(read_seconds(screen_text(s)) for s in scenes)
        print(f"무음 영상 {round(secs)}초 → {out}")

    with open(os.path.join(args.out if not args.script_only else ".",
                           "longform_script.json"), "w", encoding="utf-8") as fh:
        json.dump(scenes, fh, ensure_ascii=False, indent=2)
    return 0


# ── 무음판 ──────────────────────────────────────────────────────────
#
# 나레이션이 유료라서 영상이 2026-09-06 에 멈춰 있었다. 홈에 걸린 영상이
# "이번 주 여행 뉴스" 라고 적힌 채 아흐레 묵었다 — 매일 나오는 신문에서
# 그건 그냥 틀린 화면이다.
#
# 목소리가 없으면 화면이 정보를 전부 져야 한다. 그래서 장면 길이를
# **말하는 속도가 아니라 읽는 속도**로 잡는다. 숏폼 무음판에서 쓰던 값과
# 같다(tools/make_shorts.py).
READ_CPS = 8.5          # 초당 읽는 글자 수
READ_FLOOR = 3.0        # 장면 최소 길이. 1920×1080 은 눈이 훑을 면적이 넓다
READ_LEAD = 1.4         # 화면이 바뀌고 눈이 자리를 잡는 시간


def screen_text(scene: dict) -> str:
    """그 장면에서 **화면에 실제로 적힌** 글. 나레이션이 아니다.

    무음판에서 독자가 읽는 것은 카드에 얹힌 글자뿐이다. 나레이션 길이로
    재면 화면에 없는 말("…보도입니다")까지 세어 길이가 어긋난다.
    """
    kind = scene.get("kind")
    if kind == "title":
        return f"{scene.get('headline', '')} {scene.get('sub', '')}"
    if kind == "section":
        return scene.get("name", "")
    if kind == "data":
        return " ".join(f"{n} {v}" for n, v in scene.get("rows", []))
    return " ".join(str(scene.get(k, "")) for k in ("headline", "summary", "outlet"))


def read_seconds(text: str) -> float:
    return round(max(READ_FLOOR, len(text or "") / READ_CPS + READ_LEAD), 2)


def build_silent(scenes: list[dict], out_dir: str,
                 name: str = "peopleroad-week") -> str:
    """무음 롱폼을 만든다. 오디오 트랙이 아예 없다. 비용 0원."""
    import tempfile

    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    work = tempfile.mkdtemp(prefix="waffle-longform-")

    durations = [read_seconds(screen_text(sc)) for sc in scenes]
    clips = []
    for n, scene in enumerate(scenes):
        frame = os.path.join(work, f"f{n:02d}.png")
        render(scene).save(frame)
        clip = os.path.join(work, f"c{n:02d}.mp4")
        subprocess.run([
            ff, "-y", "-loglevel", "error", "-loop", "1", "-i", frame,
            "-t", f"{durations[n]:.2f}",
            "-vf", f"scale={W}:{H},format=yuv420p,fps=25",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22", clip,
        ], check=True)
        clips.append(clip)

    listing = os.path.join(work, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for clip in clips:
            fh.write(f"file '{os.path.abspath(clip)}'\n")

    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{name}.mp4")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out], check=True)
    poster = out.rsplit(".", 1)[0] + ".jpg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "1", "-i", out,
                    "-frames:v", "1", "-q:v", "3", poster], check=True)

    # 인용한 매체는 화면 밖에도 밝힌다. 사실은 각 매체의 보도이고 우리가
    # 한 것은 고르고 묶은 일이다.
    outlets, seen = [], set()
    for sc in scenes:
        o = (sc.get("outlet") or "").strip()
        if o and o not in seen:
            seen.add(o)
            outlets.append(o)
    region = next((sc["region"] for sc in scenes if sc.get("region")), "japan")
    meta = {
        "title": scenes[0].get("headline", "이번 주 여행 뉴스"),
        "region": region,
        "seconds": round(sum(durations)),
        "poster": "/video/" + os.path.basename(poster),
        "outlets": outlets,
        "kind": "silent",
        "built_at": datetime.now(KST).isoformat(timespec="seconds"),
    }
    with open(out.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    return out


if __name__ == "__main__":
    raise SystemExit(main())


def assemble(frames_dir: str, audio_dir: str, out_path: str) -> str:
    """장면 그림과 나레이션을 이어 붙인다. 정지 화면이라 인코딩이 가볍다.

    장면마다 나레이션 길이에 맞춰 화면을 띄우고, 앞뒤로 숨 쉴 틈을 조금 준다.
    말이 끝나자마자 다음 장면으로 넘어가면 쫓기는 느낌이 든다.
    """
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tail = 0.55                     # 문장 끝에 두는 여백(초)
    clips = []
    work = os.path.dirname(out_path) or "."
    tmp = os.path.join(work, "_lf")
    os.makedirs(tmp, exist_ok=True)

    frames = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
    for n, frame in enumerate(frames):
        wav = os.path.join(audio_dir, f"a{n:02d}.wav")
        if not os.path.exists(wav):
            continue
        probe = subprocess.run([ff, "-i", wav], capture_output=True, text=True)
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe.stderr)
        secs = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                + float(m.group(3))) if m else 4.0
        secs += tail
        clip = os.path.join(tmp, f"c{n:02d}.mp4")
        subprocess.run([
            ff, "-y", "-loglevel", "error",
            "-loop", "1", "-i", os.path.join(frames_dir, frame),
            "-i", wav,
            "-filter_complex",
            f"[1:a]apad=pad_dur={tail}[a];"
            f"[0:v]scale={W}:{H},format=yuv420p,fps=25[v]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k", "-t", f"{secs:.2f}", clip,
        ], check=True)
        clips.append(clip)

    listing = os.path.join(tmp, "list.txt")
    with open(listing, "w", encoding="utf-8") as fh:
        for clip in clips:
            fh.write(f"file '{os.path.abspath(clip)}'\n")
    subprocess.run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", out_path], check=True)
    poster = out_path.rsplit(".", 1)[0] + ".jpg"
    subprocess.run([ff, "-y", "-loglevel", "error", "-ss", "1", "-i", out_path,
                    "-frames:v", "1", "-q:v", "3", poster], check=True)
    return out_path
