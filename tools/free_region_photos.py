#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""우리 사진이 없는 지역에 자유 이용 풍경 사진을 들인다 (2026-10-28).

사장님: "사진도 좀 다 넣어". 직접 찍은 사진은 괌·사이판·하와이·코타키나발루·베트남에만
있어 일본·태국·대만·라오스·국내·업계 기사와 제주 대부분이 글자만으로 나갔다.

그 지역 대표 장소의 위키데이터 대표 사진(P18)을 위키미디어 공용에서 받는다.
**자유 라이선스(CC BY·CC BY-SA·CC0·퍼블릭 도메인)가 확인된 것만** 쓰고, 작성자와
라이선스를 manifest 에 적어 기사 사진 캡션에 밝힌다(CC BY 조건). 장소 사진이라 사람
얼굴이 주제인 사진은 거의 없지만, 사진 반입과 같은 얼굴 검사를 지나야 들인다.

직접 찍은 사진이 들어오면 그쪽이 앞선다 — 이 스크립트는 지역마다 우리 사진이
MIN_OWN 장보다 적을 때만 채운다. 이미 받은 파일은 다시 받지 않는다.

발행 작업(GitHub Actions)에서 돈다. 이 저장소의 작업 컨테이너에서는 위키미디어가 막혀 있다.

    python3 tools/free_region_photos.py            # 모자란 지역만
    python3 tools/free_region_photos.py --dry-run  # 무엇을 받을지만
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

MANIFEST = os.path.join(ROOT, "assets", "photos", "manifest.json")
WD = "https://www.wikidata.org/w/api.php"
MIN_OWN = 6            # 우리 사진이 이만큼 있으면 그 지역은 건드리지 않는다
WIDTH = 1280          # 위키미디어는 정해진 썸네일 폭(…960·1280…)만 바로 준다

# 지역 → (위키데이터 검색어(영문), 캡션 이름, 도시 슬러그). 그 지역 기사에 자주 나오는 곳부터.
# 도시 슬러그(src/cities.py)를 달면 그 도시를 말하는 기사에만 간다 — 후쿠오카 기사에
# 교토 사진이 붙지 않게. 빈 칸은 나라 단위 기사("태국 무비자")도 받는 사진이다.
# **한 번 쓴 사진은 다시 쓰지 않는다**(src/photos.py assign) — 그래서 넉넉히 둔다.
PLACES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "japan": (
        ("Tokyo Tower", "도쿄 타워", "tokyo"), ("Sensō-ji", "아사쿠사 센소지", "tokyo"),
        ("Tokyo Skytree", "도쿄 스카이트리", "tokyo"), ("Meiji Shrine", "메이지 신궁", "tokyo"),
        ("Osaka Castle", "오사카성", "osaka"), ("Kinkaku-ji", "교토 금각사", "osaka"),
        ("Fushimi Inari-taisha", "교토 후시미이나리", "osaka"), ("Kiyomizu-dera", "교토 기요미즈데라", "osaka"),
        ("Fukuoka Tower", "후쿠오카 타워", "fukuoka"), ("Dazaifu Tenman-gū", "다자이후 텐만구", "fukuoka"),
        ("Sapporo TV Tower", "삿포로 TV 타워", "sapporo"), ("Otaru Canal", "오타루 운하", "sapporo"),
        ("Shuri Castle", "오키나와 슈리성", "okinawa"), ("Churaumi Aquarium", "오키나와 추라우미 수족관", "okinawa"),
        ("Nagoya Castle", "나고야성", "nagoya"),
        ("Mount Fuji", "후지산", ""), ("Himeji Castle", "히메지성", ""), ("Itsukushima Shrine", "미야지마 이쓰쿠시마 신사", ""),
        ("Shirakawa-gō", "시라카와고", ""), ("Kenroku-en", "가나자와 겐로쿠엔", ""), ("Lake Kawaguchi", "가와구치호", ""),
        ("Beppu", "벳푸", ""), ("Kumamoto Castle", "구마모토성", ""), ("Hakone", "하코네", ""),
    ),
    "thailand": (
        ("Wat Arun", "방콕 왓 아룬", "bangkok"), ("Grand Palace (Bangkok)", "방콕 왕궁", "bangkok"),
        ("Wat Pho", "방콕 왓 포", "bangkok"), ("Chao Phraya River", "방콕 짜오프라야강", "bangkok"),
        ("Wat Phra That Doi Suthep", "치앙마이 도이수텝", "chiangmai"), ("Tha Phae Gate", "치앙마이 타패 게이트", "chiangmai"),
        ("Patong Beach", "푸껫 빠통 해변", "phuket"), ("Phang Nga Bay", "팡아만", "phuket"),
        ("Ayutthaya Historical Park", "아유타야", ""), ("Railay Beach", "끄라비 라일레이", ""),
        ("Ko Phi Phi Don", "피피섬", ""), ("Ko Samui", "사무이", ""), ("Sukhothai Historical Park", "수코타이", ""),
        ("Hua Hin", "후아힌", ""), ("Pattaya", "파타야", ""),
    ),
    "taiwan": (
        ("Taipei 101", "타이베이 101", "taipei"), ("Chiang Kai-shek Memorial Hall", "타이베이 중정기념당", "taipei"),
        ("National Palace Museum", "타이베이 고궁박물원", "taipei"), ("Longshan Temple", "타이베이 룽산쓰", "taipei"),
        ("Lotus Pond (Kaohsiung)", "가오슝 롄츠탄", "kaohsiung"), ("Pier-2 Art Center", "가오슝 보얼예술특구", "kaohsiung"),
        ("Jiufen", "지우펀", ""), ("Taroko National Park", "타이루거 협곡", ""), ("Sun Moon Lake", "르웨탄", ""),
        ("Alishan National Scenic Area", "아리산", ""), ("Tainan", "타이난", ""), ("Shifen Waterfall", "스펀 폭포", ""),
    ),
    "laos": (
        ("Pha That Luang", "비엔티안 탓루앙", ""), ("Patuxai", "비엔티안 빠뚜싸이", ""),
        ("Wat Xieng Thong", "루앙프라방 왓 씨엥통", ""), ("Kuang Si Falls", "꽝시 폭포", ""),
        ("Vang Vieng", "방비엥", ""), ("Mount Phousi", "루앙프라방 푸시산", ""), ("Plain of Jars", "항아리 평원", ""),
    ),
    "jeju": (
        ("Hallasan", "한라산", ""), ("Seongsan Ilchulbong", "성산일출봉", ""), ("Manjanggul", "만장굴", ""),
        ("Udo (island)", "우도", ""), ("Cheonjiyeon Falls", "천지연 폭포", ""), ("Jusangjeolli Cliff", "주상절리", ""),
        ("Hyeopjae Beach", "협재 해변", ""), ("Jeongbang Falls", "정방 폭포", ""),
    ),
    "korea": (
        ("Haeundae Beach", "부산 해운대", ""), ("Gamcheon Culture Village", "부산 감천문화마을", ""),
        ("Bulguksa", "경주 불국사", ""), ("Cheomseongdae", "경주 첨성대", ""), ("Gyeongpodae", "강릉 경포대", ""),
        ("Jeonju Hanok Village", "전주 한옥마을", ""), ("Hahoe Folk Village", "안동 하회마을", ""),
        ("Seoraksan", "설악산", ""), ("Yeosu", "여수", ""), ("Suncheonman Bay", "순천만", ""),
        ("Tongyeong", "통영", ""), ("Damyang Juknokwon", "담양 죽녹원", ""), ("Nami Island", "남이섬", ""),
        ("Ulleungdo", "울릉도", ""),
    ),
    # 업계면 — 목적지가 없는 기사(항공·여행사). 공항 사진을 둔다.
    "industry": (
        ("Incheon International Airport", "인천국제공항", ""), ("Gimpo International Airport", "김포국제공항", ""),
        ("Gimhae International Airport", "김해국제공항", ""), ("Cheongju International Airport", "청주국제공항", ""),
        ("Daegu International Airport", "대구국제공항", ""),
    ),
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_manifest(path: str = MANIFEST) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def own_count(manifest: dict, region: str) -> int:
    return sum(1 for e in manifest.get(region) or []
               if isinstance(e, dict) and e.get("file") and not e.get("free"))


def place_image(c, query: str) -> str | None:
    """장소의 위키데이터 대표 사진 파일명. 없으면 None."""
    found = _get_json(c, WD, {"action": "wbsearchentities", "search": query, "language": "en",
                              "type": "item", "limit": 1, "format": "json"})
    hits = found.get("search") or []
    if not hits:
        return None
    ent = _get_json(c, WD, {"action": "wbgetclaims", "entity": hits[0]["id"], "property": "P18",
                            "format": "json"})
    claims = (ent.get("claims") or {}).get("P18") or []
    try:
        return claims[0]["mainsnak"]["datavalue"]["value"]
    except (KeyError, IndexError, TypeError):
        return None


COMMONS = "https://commons.wikimedia.org/w/api.php"
# 'Attribution' 은 공용의 저작자 표시 조건 자유 라이선스 틀이다(작성자만 밝히면 된다).
FREE = re.compile(r"^(CC BY|CC0|Public domain|PD|KOGL|공공누리|Attribution)", re.I)
# 썸네일을 주는 위키미디어 주소. 2026-10-28 실측: 공용은 썸네일을 thumb.wikimedia.org 로
# 준다(원본은 upload.). upload. 만 받았더니 82곳이 버려졌다 — *.wikimedia.org 면 받는다.
def _wikimedia(host: str) -> bool:
    return host == "wikimedia.org" or host.endswith(".wikimedia.org")


def _get_json(c, url: str, params: dict, tries: int = 4) -> dict:
    """위키미디어 API 한 번. 'ratelimited'·'maxlag'·429 면 쉬었다 다시 묻는다.

    2026-10-28 첫 실행: 공용 조회 85건 중 82건이 정보 없이 돌아와 '자유 라이선스가
    아니다'로 읽혔다(도쿄 타워·불국사까지). GitHub 러너는 IP 를 여럿이 나눠 써
    위키미디어 요청 제한에 걸린다. 오류 본문을 '라이선스 없음'으로 오판하지 않는다.
    """
    import time
    last = {}
    for n in range(tries):
        r = c.get(url, params={**params, "maxlag": 5})
        code = getattr(r, "status_code", 200)
        try:
            last = r.json()
        except Exception:
            last = {"error": {"code": f"http {code}"}}
        err = (last.get("error") or {}).get("code") if isinstance(last, dict) else None
        if code == 429 or err in ("ratelimited", "maxlag") or (err or "").startswith("http"):
            wait = 3 * (n + 1)
            try:
                wait = max(wait, int(r.headers.get("retry-after", 0)))
            except Exception:
                pass
            time.sleep(min(wait, 30))
            continue
        return last
    return last


def commons_credits(c, filenames: list[str]) -> dict[str, tuple[dict | None, str]]:
    """공용 파일들의 썸네일·라이선스·작성자를 **한 번에** 묻는다(최대 50개씩).
    파일명 → (credit 또는 None, 못 쓰는 이유)."""
    import html as _html
    out: dict[str, tuple[dict | None, str]] = {}
    for i in range(0, len(filenames), 50):
        chunk = filenames[i:i + 50]
        r = _get_json(c, COMMONS, {"action": "query", "titles": "|".join(f"File:{f}" for f in chunk),
                                   "prop": "imageinfo", "iiprop": "url|extmetadata",
                                   "iiurlwidth": WIDTH, "format": "json"})
        if r.get("error"):
            for f in chunk:
                out[f] = (None, f"공용 API 오류 {r['error'].get('code')}")
            continue
        q = r.get("query") or {}
        back = {n["to"]: n["from"] for n in q.get("normalized") or []}
        for page in (q.get("pages") or {}).values():
            title = page.get("title", "")
            fname = back.get(title, title).split(":", 1)[-1]
            info = (page.get("imageinfo") or [None])[0]
            if not info:
                out[fname] = (None, "공용에 파일 정보가 없다")
                continue
            meta = info.get("extmetadata") or {}
            lic = (meta.get("LicenseShortName") or {}).get("value", "")
            if not FREE.search(lic):
                out[fname] = (None, f"라이선스 '{lic or '없음'}'")
                continue
            artist = _html.unescape(re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")))
            from urllib.parse import urlparse
            url = info.get("thumburl") or info.get("url") or ""
            if url.startswith("//"):
                url = "https:" + url
            from urllib.parse import parse_qsl, urlencode, urlunparse
            parts = urlparse(url)
            # 공용이 붙이는 추적 꼬리(utm_)만 뗀다. thumb.php 같은 주소는 쿼리가 본체다.
            keep = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
            url = urlunparse(parts._replace(query=urlencode(keep)))
            host = parts.netloc
            if not (url.startswith("https://") and _wikimedia(host)):
                out[fname] = (None, f"썸네일 주소가 위키미디어가 아니다: {url[:90] or '(빈 값)'}")
                continue
            out[fname] = ({"url": url, "page": info.get("descriptionurl"), "license": lic,
                           "artist": re.sub(r"\s+", " ", artist).strip()[:60] or "작성자 미상"}, "")
        for f in chunk:
            out.setdefault(f, (None, "공용 응답에 없다"))
    return out


def _has_face(img) -> bool:
    """사진 반입(tools/photo_intake.py)과 같은 검사기 — 얼굴·사람이 잡히면 True.
    검사기(cv2)를 못 쓰면 들이지 않는다(True, fail-closed)."""
    import tempfile
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import photo_prepare                                # noqa: WPS433
    except Exception:
        return True
    with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
        img.convert("RGB").save(tmp.name, "JPEG", quality=90)
        try:
            return not photo_prepare.inspect(tmp.name).get("ok")
        except Exception:
            return True


def fetch_region(c, manifest: dict, region: str, *, dry_run: bool = False,
                 face_check=_has_face) -> int:
    """한 지역을 채운다. 새로 들인 장수."""
    import time
    from PIL import Image

    entries = manifest.setdefault(region, [])
    have = {e.get("commons") for e in entries if isinstance(e, dict)}
    added = 0
    wanted = []
    for query, name, city in PLACES.get(region, ()):
        filename = place_image(c, query)
        if not filename:
            print(f"  [{region}] {name}: 위키데이터에 대표 사진이 없다 — 건너뜀")
        elif filename not in have:
            wanted.append((query, name, city, filename))
    credits = commons_credits(c, [w[3] for w in wanted]) if wanted else {}
    for query, name, city, filename in wanted:
        credit, why = credits.get(filename, (None, "공용 응답에 없다"))
        if not credit:
            print(f"  [{region}] {name}: {why} — 건너뜀")
            continue
        rel = f"assets/photos/{region}/free-{_slug(query)}.webp"
        print(f"  [{region}] {name}: {filename} · {credit['license']} · {credit['artist']}")
        if dry_run:
            continue
        raw = b""
        for n in range(3):                     # 사진 서버도 요청 제한이 있다
            r = c.get(credit["url"])
            if getattr(r, "status_code", 200) != 429:
                raw = r.content
                break
            time.sleep(5 * (n + 1))
        try:
            img = Image.open(io.BytesIO(raw))
            img.load()
        except Exception:
            print(f"  [{region}] {name}: 사진을 열지 못했다({len(raw)}바이트) — 건너뜀")
            continue
        if face_check(img):
            print(f"  [{region}] {name}: 얼굴이 잡혀 들이지 않는다")
            continue
        img = img.convert("RGB")
        if img.width > WIDTH:
            img = img.resize((WIDTH, round(img.height * WIDTH / img.width)))
        dst = os.path.join(ROOT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        img.save(dst, "WEBP", quality=82)
        entries.append({
            "file": rel, "hero": True, "free": True, "place": name, "city": city,
            "commons": filename, "license": credit["license"], "artist": credit["artist"],
            "source": credit.get("page") or "", "origin": "위키미디어 공용(자유 이용)",
        })
        have.add(filename)
        added += 1
    return added


def main(argv: list[str]) -> int:
    import httpx
    from tools.free_photos import UA
    dry = "--dry-run" in argv
    manifest = load_manifest()
    total = 0
    with httpx.Client(headers=UA, timeout=30, follow_redirects=True) as c:
        for region in PLACES:
            if own_count(manifest, region) >= MIN_OWN:
                continue
            try:
                total += fetch_region(c, manifest, region, dry_run=dry)
            except Exception as e:                 # 한 지역이 막혀도 나머지는 받는다
                print(f"  [{region}] 받지 못했다 — {type(e).__name__}: {e}", file=sys.stderr)
    if total and not dry:
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print(f"자유 이용 사진 {total}장 들였다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
