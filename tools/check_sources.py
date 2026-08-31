"""소스 후보를 실제로 두드려 살아있는지 확인한다.

사용법: .venv/bin/python tools/check_sources.py candidates.txt
candidates.txt 는 한 줄에 하나씩 "id<TAB>url" 형식.
결과를 표로 출력하고 살아있는 것만 stdout 마지막에 yaml 스니펫으로 낸다.
"""
import sys
import urllib.robotparser
from urllib.parse import urlsplit, urlunsplit

import httpx
import feedparser

UA = "WaffleTripBot/1.0 (+https://waffletrip.com/about/)"
TIMEOUT = 10.0


def robots_allows(url: str) -> tuple[bool, str]:
    """대상 사이트의 robots.txt 가 우리 봇에게 이 경로를 허용하는가.

    스펙 5절 규칙 4. 금지된 경로는 소스로 쓰지 않는다.
    robots.txt 를 못 읽는 경우는 허용으로 본다 — 표준 관행이고,
    없는 robots.txt 를 금지로 해석하면 정상 피드를 전부 버리게 된다.
    """
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    parser = urllib.robotparser.RobotFileParser()
    try:
        r = httpx.get(robots_url, timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": UA})
        if r.status_code >= 400:
            return True, "robots.txt 없음 (허용으로 간주)"
        parser.parse(r.text.splitlines())
    except Exception:
        return True, "robots.txt 조회 실패 (허용으로 간주)"
    allowed = parser.can_fetch(UA, url)
    return allowed, "robots 허용" if allowed else "robots 금지 — 소스로 쓸 수 없다"


def probe(url: str) -> tuple[bool, str]:
    """(살아있는가, 사유). RSS면 항목 수까지 확인한다."""
    try:
        r = httpx.get(url, timeout=TIMEOUT, follow_redirects=True,
                      headers={"User-Agent": UA})
    except Exception as e:
        return False, f"연결실패: {type(e).__name__}"
    if r.status_code >= 400:
        return False, f"HTTP {r.status_code}"
    body = r.text
    if "<rss" in body[:2000].lower() or "<feed" in body[:2000].lower():
        parsed = feedparser.parse(body)
        n = len(parsed.entries)
        return (n > 0), f"RSS 항목 {n}개"
    if body.lstrip().startswith(("{", "[")):
        return True, "JSON 응답"
    return False, "RSS/JSON 아님 (HTML만 반환)"


def main(path: str) -> None:
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sid, url = line.split("\t", 1)
        allowed, robots_why = robots_allows(url)
        if not allowed:
            rows.append((sid, url, False, robots_why))
            print(f"X   {sid:24s} {robots_why:34s} {url}")
            continue
        ok, why = probe(url)
        rows.append((sid, url, ok, why))
        print(f"{'OK ' if ok else 'X  '} {sid:24s} {why:34s} {url}")
    alive = [r for r in rows if r[2]]
    print(f"\n=== 사용 가능 {len(alive)}/{len(rows)} ===")
    print("robots 금지로 걸린 소스는 sources.yaml 에 넣지 않는다.")


if __name__ == "__main__":
    main(sys.argv[1])
