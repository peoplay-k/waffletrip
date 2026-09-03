"""Google 뉴스 리다이렉트를 실제 기사로 푼다.

Google 뉴스 검색 피드는 세 가지를 주지 않는다 — 실제 기사 URL(대신
news.google.com/rss/articles/... 리다이렉트), 요약, 매체의 정식 이름(도메인이
그대로 오기도 한다: v.daum.net, newsis.com). 그대로 실으면 기사 페이지가
제목 한 줄짜리 얇은 페이지가 되고("본문 91자"), 서명에 도메인이 찍힌다.
B등급 867건 중 722건이 그랬다.

리다이렉트를 풀어 실제 페이지를 한 번 읽고 og:site_name·og:description·
article:published_time 을 가져온다. 결과는 data/resolved.json 에 남겨
같은 기사를 두 번 읽지 않는다 — 매일 새로 들어오는 것만 푼다.

**실패해도 기사를 버리지 않는다.** 요약이 없는 채로 나가는 것이 안 나가는 것보다
낫다. 단 요약을 못 채운 기사는 edit 단계에서 검색 색인에서 뺀다(noindex).
"""
from __future__ import annotations

import json
import os
import re

import httpx

from src.fetch.rss import first_sentences, strip_html

CACHE = "data/resolved.json"
# 한 번에 너무 많이 풀면 CI 가 오래 걸린다. 하루 신규는 보통 100건 안팎.
MAX_PER_RUN = 250
TIMEOUT = 12.0
# 인용은 두 문장·200자까지. B등급 규칙과 같다.
MAX_SUMMARY = 200

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko,en;q=0.8",
}
_BATCH = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def is_google(url: str) -> bool:
    return "news.google.com/rss/articles/" in url


def decode_google_url(url: str, client: httpx.Client) -> str | None:
    """news.google.com/rss/articles/<id> → 실제 URL.

    리다이렉트 페이지에 박힌 서명(data-n-a-sg, data-n-a-ts)을 읽어
    batchexecute 에 되돌려 주면 실제 주소를 준다. googlenewsdecoder 가 쓰는
    방식이다. 구글이 바꾸면 깨지므로 실패는 None 으로 조용히 돌려준다.
    """
    art_id = url.split("/articles/", 1)[1].split("?", 1)[0]
    try:
        page = client.get(f"https://news.google.com/articles/{art_id}")
    except httpx.HTTPError:
        return None
    sg = re.search(r'data-n-a-sg="([^"]+)"', page.text)
    ts = re.search(r'data-n-a-ts="([^"]+)"', page.text)
    if not (sg and ts):
        return None
    inner = (
        '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,'
        'null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],'
        f'"{art_id}",{ts.group(1)},"{sg.group(1)}"]'
    )
    req = [[["Fbv4je", inner, None, "generic"]]]
    try:
        resp = client.post(
            _BATCH, data={"f.req": json.dumps(req)},
            headers={"Content-Type":
                     "application/x-www-form-urlencoded;charset=UTF-8"})
        body = resp.text.split("\n\n", 1)[-1]
        outer = json.loads(body)
        real = json.loads(outer[0][2])[1]
    except (httpx.HTTPError, ValueError, IndexError, TypeError):
        return None
    return real if isinstance(real, str) and real.startswith("http") else None


_META = {
    "outlet": (r'property="og:site_name"\s+content="([^"]*)"',
               r'content="([^"]*)"\s+property="og:site_name"'),
    "summary": (r'property="og:description"\s+content="([^"]*)"',
                r'content="([^"]*)"\s+property="og:description"',
                r'name="description"\s+content="([^"]*)"'),
    "published": (r'property="article:published_time"\s+content="([^"]*)"',
                  r'content="([^"]*)"\s+property="article:published_time"'),
}


def read_page(url: str, client: httpx.Client) -> dict:
    """기사 페이지에서 매체명·요약·발행시각. 없는 값은 빈 문자열."""
    out = {"outlet": "", "summary": "", "published": ""}
    try:
        r = client.get(url)
        html = r.text
    except httpx.HTTPError:
        return out
    for key, patterns in _META.items():
        for pat in patterns:
            m = re.search(pat, html, re.S)
            if m and m.group(1).strip():
                out[key] = strip_html(m.group(1)).strip()
                break
    if out["summary"]:
        out["summary"] = first_sentences(out["summary"], 2)[:MAX_SUMMARY]
    return out


def load_cache(path: str = CACHE) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_cache(cache: dict, path: str = CACHE) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=0)


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


def apply(row: dict, got: dict) -> bool:
    """캐시 값을 항목(dict)에 입힌다. 바뀐 게 있으면 True."""
    changed = False
    if got.get("url") and row.get("source_url") != got["url"]:
        row["source_url"] = got["url"]; changed = True
    if got.get("outlet") and row.get("source_name") != got["outlet"]:
        row["source_name"] = got["outlet"]; changed = True
    if got.get("summary") and not (row.get("summary") or "").strip():
        row["summary"] = got["summary"]; changed = True
    pub = got.get("published") or ""
    if _ISO.match(pub) and row.get("published_at") != pub:
        row["published_at"] = pub; changed = True
    return changed


SAVE_EVERY = 25


def resolve_rows(rows: list[dict], cache: dict, limit: int = MAX_PER_RUN,
                 client: httpx.Client | None = None,
                 cache_path: str | None = None) -> tuple[int, int, int]:
    """Google 뉴스 항목(dict)의 URL·출처·요약을 실제 값으로 바꾼다.

    캐시는 항목 id 로 찾는다 — URL 을 실제 주소로 바꾼 뒤에도 같은 기사를
    다시 알아봐야 하기 때문이다(id 는 바뀌지 않는다).
    돌려주는 값은 (새로 푼 수, 실패 수, 고친 항목 수).
    """
    own = client is None
    client = client or httpx.Client(headers=_HEADERS, timeout=TIMEOUT,
                                    follow_redirects=True)
    fetched = failed = patched = 0
    try:
        for row in rows:
            key = row["id"]
            if key not in cache:
                if not is_google(row.get("source_url", "")):
                    continue
                if fetched + failed >= limit:
                    continue
                real = decode_google_url(row["source_url"], client)
                if not real:
                    failed += 1
                    cache[key] = {"url": ""}
                else:
                    cache[key] = {"url": real, **read_page(real, client)}
                    fetched += 1
                # 수백 건을 풀다 중간에 죽으면 전부 잃는다. 자주 남긴다.
                if cache_path and (fetched + failed) % SAVE_EVERY == 0:
                    save_cache(cache, cache_path)
            if apply(row, cache[key]):
                patched += 1
    finally:
        if own:
            client.close()
    return fetched, failed, patched


def _load_jsonl(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _save_jsonl(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(data_dir: str = "data", limit: int = MAX_PER_RUN) -> int:
    """오늘 raw 를 풀고, 이미 발행된 jsonl 도 캐시로 다시 입힌다.

    collect 다음, edit 전에 돈다. jsonl 까지 손대는 이유: 요약 없이 나간
    기사도 다음 빌드에서 채워져야 한다. 빌드는 jsonl 을 읽는다.
    """
    import glob
    from src.collect import now_kst
    cache_path = os.path.join(data_dir, "resolved.json")
    cache = load_cache(cache_path)
    day = now_kst()[:10]
    raw = os.path.join(data_dir, "raw", day, "items.json")
    fetched = failed = patched = 0
    try:
        if os.path.exists(raw):
            with open(raw, encoding="utf-8") as f:
                rows = json.load(f)
            fetched, failed, patched = resolve_rows(rows, cache, limit,
                                                    cache_path=cache_path)
            with open(raw, "w", encoding="utf-8") as f:
                json.dump(rows, f, ensure_ascii=False, indent=2)
        rest = limit - fetched - failed
        for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl"))):
            rows = _load_jsonl(path)
            f2, x2, p2 = resolve_rows(rows, cache, max(rest, 0),
                                      cache_path=cache_path)
            fetched += f2; failed += x2; patched += p2; rest -= f2 + x2
            if p2:
                _save_jsonl(path, rows)
    finally:
        save_cache(cache, cache_path)
    print(f"해결 완료: 새로 {fetched}건, 실패 {failed}건, 고친 항목 {patched}건 "
          f"(캐시 {len(cache)}건)")
    return 0


if __name__ == "__main__":
    import sys
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else MAX_PER_RUN
    raise SystemExit(main(limit=lim))
