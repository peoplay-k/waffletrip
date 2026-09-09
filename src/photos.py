"""구운 사진을 사이트에 붙인다.

`assets/photos/manifest.json` 은 `tools/photo_prepare.py` 가 쓴다. 그 도구를
거치지 않은 사진은 여기 없고, 따라서 사이트에 나가지 않는다. **사람 승인을
통과한 것만 매니페스트에 들어간다**는 것이 이 파이프라인의 유일한 안전장치다.

매니페스트가 없어도 빌드는 돈다. 사진은 있으면 좋은 것이지 없으면 안 되는
것이 아니다 — 신문이 사진 때문에 안 나가면 안 된다.
"""
from __future__ import annotations

import json
import os
import shutil

MANIFEST = "assets/photos/manifest.json"
USED = "data/photos/used.json"      # 사진 사용 이력. 재사용을 막는 유일한 장치.
PUBLIC_DIR = "img"          # public/ 아래 경로


def load_used(path: str = USED) -> dict:
    """사진 → 그 사진을 쓴 기사 id."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_used(used: dict, path: str = USED) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2, sort_keys=True)


def load_manifest(path: str = MANIFEST) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def web_path(baked_file: str) -> str:
    """assets/photos/guam/x.webp → /img/guam/x.webp"""
    rel = baked_file.replace("assets/photos/", "", 1).lstrip("/")
    return f"/{PUBLIC_DIR}/{rel}"


def hero_photos(manifest: dict, region: str) -> list[str]:
    """풍경으로 표시된 사진만."""
    return [web_path(e["file"]) for e in (manifest.get(region) or [])
            if isinstance(e, dict) and e.get("file") and e.get("hero")]


def photos_for(manifest: dict, region: str) -> list[str]:
    """지역의 사진 목록. **풍경(hero)이 앞에 온다.**

    1면 사진은 그 매체의 인상을 결정한다. 해시로만 고르면 양념치킨
    클로즈업이 톱기사에 걸린다 — 실제로 그랬다. 풍경으로 표시된 사진을
    먼저 쓰고, 모자라면 나머지로 채운다.
    """
    entries = [e for e in (manifest.get(region) or [])
               if isinstance(e, dict) and e.get("file")]
    heroes = [e for e in entries if e.get("hero")]
    rest = [e for e in entries if not e.get("hero")]
    return [web_path(e["file"]) for e in heroes + rest]


# 사진에 붙는 장소. CITIES 의 도시 슬러그를 그대로 쓰되, 도시 페이지가 없는
# 촬영지(하롱베이·닌빈·우라이)는 여기서 낱말을 더 둔다. 기사 쪽 매칭에도 같이 쓴다.
PLACE_WORDS: dict[str, tuple[str, ...]] = {
    "halong": ("하롱베이", "하롱"),
    "ninhbinh": ("닌빈", "짱안", "항무아"),
    "wulai": ("우라이",),
}
PLACE_NAMES: dict[str, str] = {"halong": "하롱베이", "ninhbinh": "닌빈", "wulai": "우라이"}

# 영문 제목과 다른 나라 도시. VnExpress 같은 현지 영문 매체는 지역이 베트남으로
# 고정돼 싱가포르·도쿄 기사도 베트남면에 들어온다. 2026-09-09 실측: "Tokyo tourist
# hotspot Shinjuku bans vacation rentals" 에 다낭 사진이 붙었다 — 제목에 우리 도시
# 낱말이 없어 '도시를 안 가리는 기사' 로 보였기 때문이다. 다른 도시를 말하는
# 기사는 태그된 지역 사진을 받지 못한다(태그 없는 사진만). 소문자로 비교한다.
FOREIGN_WORDS: dict[str, tuple[str, ...]] = {
    "hanoi": ("hanoi",), "danang": ("da nang", "danang", "hoi an", "hoian", "ba na"),
    "nhatrang": ("nha trang", "khanh hoa"), "hochiminh": ("ho chi minh", "hcmc", "saigon"),
    "phuquoc": ("phu quoc",), "halong": ("ha long", "halong"), "hue": ("hue ",),
    "tokyo": ("tokyo", "shinjuku", "narita", "haneda"), "osaka": ("osaka", "kyoto", "kansai"),
    "fukuoka": ("fukuoka",), "sapporo": ("sapporo", "hokkaido"), "okinawa": ("okinawa",),
    "bangkok": ("bangkok",), "phuket": ("phuket",), "chiangmai": ("chiang mai",),
    "taipei": ("taipei", "taoyuan"), "kaohsiung": ("kaohsiung",),
    "kota": ("kota kinabalu", "sabah"), "jeju": ("jeju",),
    "singapore": ("singapore", "changi", "싱가포르"), "hongkong": ("hong kong", "홍콩"),
    "seoul": ("seoul", "gimpo", "incheon airport"), "bali": ("bali", "발리"),
    "jakarta": ("jakarta", "자카르타"), "kualalumpur": ("kuala lumpur", "쿠알라룸푸르"),
    "penang": ("penang", "페낭"), "langkawi": ("langkawi", "랑카위"),
    "maldives": ("maldives", "몰디브"), "seychelles": ("seychelles",),
    "macau": ("macau", "마카오"), "manila": ("manila", "cebu", "boracay", "세부", "보라카이"),
    "miami": ("miami",), "london": ("london",), "paris": ("paris",), "spain": ("spain", "madrid", "barcelona"),
}



def places_of(item) -> set[str]:
    """기사가 가리키는 장소들. CITIES 의 도시 + 촬영지 낱말."""
    if isinstance(item, str):
        return set()
    from src.cities import CITIES

    def scan(text: str) -> set[str]:
        found = {slug for slug, _, _, words in CITIES if any(w in text for w in words)}
        lowered = text.lower()
        for slug, words in list(PLACE_WORDS.items()) + list(FOREIGN_WORDS.items()):
            if any(w in lowered for w in words):
                found.add(slug)
        return found

    # 제목이 도시를 말하면 그 도시가 주제다. 요약에만 나온 도시는 배경일 뿐이다 —
    # "나트랑 관광 알려요" 기사의 요약에 "하노이에서 열린 설명회" 가 있다고
    # 하노이 사진을 붙이면 안 된다(2026-09-09 실측). 제목에 도시가 없을 때만
    # 요약의 도시를 본다.
    title_places = scan(getattr(item, 'title', '') or '')
    if title_places:
        return title_places
    return scan(getattr(item, 'summary', '') or '')


def place_names() -> dict[str, str]:
    from src.cities import CITY_NAMES
    return {**CITY_NAMES, **PLACE_NAMES}


def photo_places(manifest: dict) -> dict[str, str]:
    """웹 경로 → 장소 표시 이름. 캡션에 쓴다. 태그 없는 사진은 빈 문자열."""
    names = place_names()
    out: dict[str, str] = {}
    for entries in manifest.values():
        for e in entries if isinstance(entries, list) else []:
            if isinstance(e, dict) and e.get("file"):
                out[web_path(e["file"])] = names.get(e.get("city") or "", "")
    return out


def _entry_city(manifest: dict, region: str) -> dict[str, str]:
    return {web_path(e["file"]): (e.get("city") or "")
            for e in (manifest.get(region) or [])
            if isinstance(e, dict) and e.get("file")}


def assign(manifest: dict, region: str, seeds: list,
           used: dict | None = None) -> dict:
    """한 지역면의 기사들에 사진을 배정한다.

    **한 번 쓴 사진은 다시 쓰지 않는다.** 같은 사진이 여러 기사에 반복되면
    유사문서로 처리돼 검색에서 손해를 보고, 매체가 성의 없어 보인다.
    사진이 모자라면 재사용하는 대신 **사진 없이 내보낸다.**

    **사진은 도시를 가려서 붙는다.** 2026-09-09 실측: 하노이 사진 39장이 베트남
    전체에 배정돼 호치민 책방거리 기사에 호안끼엠 사진이 붙었다. 기사가 도시를
    가리키면(제목·요약에 도시명) 같은 도시 사진 → 장소 태그 없는 사진 순으로만
    주고, **다른 도시 사진은 주지 않는다**(차라리 사진 없이). 도시를 안 가리키는
    기사("베트남 항공권 15% 할인")는 어느 사진이든 받는다 — 베트남 사진이니까.

    used 는 사진 → 기사 id 기록이다. 같은 기사는 늘 같은 사진을 유지하고
    (빌드마다 바뀌면 어제 본 기사가 오늘 달라 보인다), 다른 기사가 쓴
    사진은 후보에서 빠진다. 다만 규칙에 어긋나게 붙어 있던 사진은 놓아준다.

    seeds 는 기사 객체(id·title·summary)이거나 예전처럼 id 문자열이어도 된다.
    """
    used = {} if used is None else used
    pool = photos_for(manifest, region)
    if not pool:
        return {}
    city_of = _entry_city(manifest, region)
    heroes = set(hero_photos(manifest, region))

    def sid(x):
        return x if isinstance(x, str) else x.id

    def allowed(photo: str, item) -> bool:
        places = places_of(item)
        if not places:
            return True                       # 도시 없는 기사는 아무 사진이나
        return city_of.get(photo, "") in places or not city_of.get(photo, "")

    def rank(photo: str, item) -> tuple:
        places = places_of(item)
        same = 0 if (places and city_of.get(photo) in places) else 1
        return (same, 0 if photo in heroes else 1, pool.index(photo))

    out: dict[str, str] = {}
    # ① 이미 이 기사에 배정된 사진은 규칙에 맞는 한 그대로 둔다.
    mine = {aid: ph for ph, aid in used.items()}
    for item in seeds:
        prev = mine.get(sid(item))
        if prev and prev in pool:
            if allowed(prev, item):
                out[sid(item)] = prev
            else:
                del used[prev]                # 잘못 붙은 사진은 놓아준다

    # ② 남은 기사에는 아직 아무도 쓰지 않은 사진 중 규칙에 맞는 것만 준다.
    for item in seeds:
        key = sid(item)
        if key in out:
            continue
        free = [p for p in pool if p not in used and allowed(p, item)]
        if not free:
            continue                          # 맞는 사진이 없으면 사진 없이 간다
        free.sort(key=lambda p: rank(p, item))
        out[key] = free[0]
        used[free[0]] = key
    return out


def pick(manifest: dict, region: str, seed: str) -> str:
    """지역 사진 하나를 고른다. 같은 기사는 항상 같은 사진을 받는다.

    난수를 쓰지 않는 이유 — 빌드할 때마다 사진이 바뀌면 캐시가 무의미해지고,
    무엇보다 '어제 본 기사'가 오늘 달라 보인다.
    """
    pool = photos_for(manifest, region)
    if not pool:
        return ""
    return pool[sum(ord(c) for c in seed) % len(pool)]


def copy_into(out_dir: str, source_root: str = "assets/photos",
              photos=None) -> int:
    """구운 사진을 public/img/ 로 옮긴다. 복사한 개수.

    photos 를 주면 그 사진만 옮긴다. 지면에 안 쓰인 사진까지 다 옮기면
    배포물이 불필요하게 커지고, 테스트가 render_site 를 부를 때마다 125장을
    임시 폴더에 복사해 하루 만에 6GB 를 먹었다(2026-09-09 실측).
    """
    manifest = load_manifest()
    want = None if photos is None else set(photos)
    copied = 0
    for entries in manifest.values():
        for e in entries if isinstance(entries, list) else []:
            if not isinstance(e, dict) or not e.get("file"):
                continue
            web = web_path(e["file"])
            if want is not None and web not in want:
                continue
            src = e["file"]
            if not os.path.exists(src):
                continue
            dst = os.path.join(out_dir, web.lstrip("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    return copied


# ── 공유 카드용 이미지 ─────────────────────────────────────────────────
# 카톡·페북은 og:image 로 1200×630 JPG 를 기대한다. 지면 사진은 webp 에 1024×1024
# 같은 정방형이라 카드가 잘리거나(카톡은 webp 를 안 그리기도 한다) 전 기사가
# 기본 이미지 하나로 보였다. 빌드 때 사진마다 JPG 카드를 굽는다.
OG_DIR = "og"
OG_SIZE = (1200, 630)


def og_path(web_photo: str) -> str:
    """/img/vietnam/x.webp → /og/vietnam/x.jpg"""
    rel = web_photo[len("/" + PUBLIC_DIR + "/"):] if web_photo.startswith("/" + PUBLIC_DIR + "/") else web_photo.lstrip("/")
    return "/" + OG_DIR + "/" + rel.rsplit(".", 1)[0] + ".jpg"


def _file_for(manifest: dict, web: str):
    for entries in manifest.values():
        for e in entries if isinstance(entries, list) else []:
            if isinstance(e, dict) and e.get("file") and web_path(e["file"]) == web:
                return e["file"]
    return None


def render_og_images(manifest: dict, out_dir: str, photos=None) -> int:
    """지면에 실제로 쓰인 사진만 1200×630 JPG 로 굽는다. 만든 개수.

    매니페스트 전체를 굽지 않는다 — 안 쓰인 사진 카드는 아무도 안 보고,
    테스트가 render_site 를 부를 때마다 125장을 인코딩해 몇 분씩 걸렸다.
    """
    from PIL import Image, ImageOps
    made = 0
    for web in sorted(set(photos or [])):
        src = _file_for(manifest, web)
        if not src or not os.path.exists(src):
            continue
        dst = os.path.join(out_dir, og_path(web).lstrip("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with Image.open(src) as im:
            ImageOps.fit(im.convert("RGB"), OG_SIZE, Image.LANCZOS).save(dst, "JPEG", quality=82, optimize=True)
        made += 1
    return made


def photo_dims(manifest: dict, photos=None) -> dict[str, tuple[int, int]]:
    """웹 경로 → (너비, 높이). <img width height> 에 쓴다 — 없으면 사진이 뜰 때
    본문이 밀린다(CLS). 쓰인 사진만 잰다."""
    from PIL import Image
    out: dict[str, tuple[int, int]] = {}
    for web in set(photos or []):
        src = _file_for(manifest, web)
        if src and os.path.exists(src):
            try:
                with Image.open(src) as im:
                    out[web] = im.size
            except Exception:
                pass
    return out
