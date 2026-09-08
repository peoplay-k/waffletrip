"""새로 낸 쪽을 검색엔진에 바로 알린다.

IndexNow 는 빙·네이버·얀덱스가 함께 쓰는 규약이다. 한 곳에 알리면 나머지로
퍼진다. 국내 유입에는 네이버가 중요한데, 네이버가 이 규약에 참여한다.
구글은 참여하지 않는다 — 구글은 서치콘솔에 사이트맵을 한 번 내면 알아서 다시 온다.

**키가 없으면 아무것도 하지 않는다.** 색인 통지는 있으면 좋은 것이지 발행의
전제조건이 아니다. 여기서 실패해도 신문은 이미 나갔다. 그래서 이 모듈은
어떤 경우에도 0 으로 끝난다 — 워크플로를 빨갛게 만들 이유가 없다.
"""
from __future__ import annotations

import json
import os
import sys

from src.models import item_from_dict
from src.render.site import REGION_NAMES, SITE_URL, article_url

ENDPOINT = "https://api.indexnow.org/IndexNow"
KEY_FILE = os.path.join("static", "indexnow.txt")
KEY_URL_PATH = "/indexnow.txt"
MAX_URLS = 10_000          # 규약 상한
TIMEOUT = 15.0


def load_key(path: str = KEY_FILE) -> str:
    """키를 읽는다. 없거나 비었으면 빈 문자열 — 그러면 통지를 건너뛴다."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def todays_urls(items_dir: str, today: str, site: str = SITE_URL) -> list[str]:
    """오늘 새로 나간 쪽의 주소.

    홈과 해당 지역면도 함께 넣는다 — 기사가 들어가면 그 목록 쪽도 바뀐다.
    A등급(환율·날씨)은 개별 쪽이 없으므로 지역면과 데이터면으로만 알린다.
    """
    path = os.path.join(items_dir, f"{today}.jsonl")
    if not os.path.exists(path):
        return []

    urls: list[str] = [f"{site}/"]
    regions: set[str] = set()
    has_data = False

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = item_from_dict(json.loads(line))
            if item.region in REGION_NAMES:
                regions.add(item.region)
            if item.grade == "A":
                has_data = True
                continue
            urls.append(site + article_url(item))

    urls += [f"{site}/{region}/" for region in sorted(regions)]
    if has_data:
        urls.append(f"{site}/data/")

    # 순서를 지키면서 중복만 없앤다.
    return list(dict.fromkeys(urls))[:MAX_URLS]


def submit(urls: list[str], key: str, client, site: str = SITE_URL) -> int:
    """IndexNow 에 알린다. 응답 코드를 돌려준다. 보낼 게 없으면 0."""
    if not urls or not key:
        return 0
    host = site.split("://", 1)[-1].rstrip("/")
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"{site}{KEY_URL_PATH}",
        "urlList": urls,
    }
    response = client.post(ENDPOINT, json=payload, timeout=TIMEOUT)
    return response.status_code


def main(items_dir: str = os.path.join("data", "items"),
         today: str = "") -> int:
    from datetime import datetime, timedelta, timezone

    if not today:
        today = datetime.now(timezone(timedelta(hours=9))).date().isoformat()

    key = load_key()
    if not key:
        print("IndexNow: 키가 없어 통지를 건너뛴다 "
              f"({KEY_FILE} 에 키를 넣으면 켜진다).")
        return 0

    urls = todays_urls(items_dir, today)
    if not urls:
        print(f"IndexNow: {today} 에 새로 나간 쪽이 없다.")
        return 0

    try:
        import httpx
        with httpx.Client() as client:
            code = submit(urls, key, client)
        print(f"IndexNow: {len(urls)}개 주소 통지 → HTTP {code}")
    except Exception as e:
        # 통지 실패로 발행을 되돌리지 않는다. 신문은 이미 나갔다.
        print(f"IndexNow: 통지 실패 {type(e).__name__}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
