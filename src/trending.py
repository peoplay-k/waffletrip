"""검색 급상승 키워드를 받아 data/trending.json 에 둔다.

인수인계 문서가 "네이버 데이터랩은 Actions 러너에서 접근할 수 없으므로 파일
이음매로 받는다"고 적어둔 그 이음매다. 지금까지 비어 있어서 해설 기사 후보
선정의 세 경로 중 하나(검색 급상승)가 죽어 있었다.

**Google Trends RSS 를 쓴다 — 인증키가 필요 없다.** 돌아오는 키워드는 대부분
여행과 무관한 일반 뉴스지만, 쓰이는 방식이 "여행 기사 제목에 이 키워드가
들어 있는가"라 **매칭 자체가 필터**다. 겹치는 순간이 곧 진짜 신호다
(태풍·환율·항공 이슈가 대중 관심사로 올라온 날).

실패해도 파이프라인을 멈추지 않는다. 키워드는 후보 선정의 보조 신호이지
발행의 전제조건이 아니다 — load_trending 이 이미 그렇게 설계돼 있다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import httpx

KST = timezone(timedelta(hours=9))
FEED_URL = "https://trends.google.com/trending/rss?geo=KR"
USER_AGENT = "WaffleTripBot/1.0 (+https://waffletrip.com/about/)"
TIMEOUT = 15.0
MAX_KEYWORDS = 30
MIN_LENGTH = 2      # 한 글자 키워드는 아무 제목에나 걸린다

_ITEM = re.compile(r"<item>(.*?)</item>", re.S)
_TITLE = re.compile(r"<title>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</title>", re.S)


def parse_feed(xml: str) -> list[str]:
    """<item> 안의 <title> 만 뽑는다.

    채널 제목("Daily Search Trends")과 뉴스 기사 제목이 함께 잡히지 않도록
    item 블록으로 먼저 자르고 그 안의 첫 title 만 본다.
    """
    keywords: list[str] = []
    for block in _ITEM.findall(xml or ""):
        m = _TITLE.search(block)
        if not m:
            continue
        word = m.group(1).strip()
        if len(word) >= MIN_LENGTH and word not in keywords:
            keywords.append(word)
    return keywords[:MAX_KEYWORDS]


def write(data_dir: str, keywords: list[str], day: str) -> str:
    path = os.path.join(data_dir, "trending.json")
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": day, "source": "google_trends_kr",
                   "keywords": keywords}, f, ensure_ascii=False, indent=2)
    return path


def main(data_dir: str = "data") -> int:
    day = datetime.now(KST).date().isoformat()
    try:
        with httpx.Client() as client:
            response = client.get(FEED_URL, timeout=TIMEOUT,
                                  follow_redirects=True,
                                  headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
        keywords = parse_feed(response.text)
    except Exception as e:
        # 여기서 죽으면 그날 신문이 안 나간다. 키워드는 있으면 좋은 것이지
        # 없으면 안 되는 것이 아니다.
        print(f"급상승 키워드를 받지 못했다: {type(e).__name__}: {e}. "
              f"이전 값을 그대로 둔다.", file=sys.stderr)
        return 0

    if not keywords:
        print("급상승 키워드가 비어 있다. 이전 값을 그대로 둔다.", file=sys.stderr)
        return 0

    write(data_dir, keywords, day)
    print(f"급상승 키워드 {len(keywords)}건: {', '.join(keywords[:6])} …")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
