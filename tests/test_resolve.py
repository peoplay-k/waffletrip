"""Google 뉴스 원문 해결."""
import json

import httpx

from src.fetch.resolve import apply, read_page, resolve_rows

GN = "https://news.google.com/rss/articles/CBMiAbc?oc=5"
REDIRECT_PAGE = '<c-wiz data-n-a-sg="SIG" data-n-a-ts="1234"></c-wiz>'
BATCH_BODY = ")]}'\n\n" + json.dumps(
    [["wrb.fr", "Fbv4je", json.dumps(["garturlres", "https://www.newsis.com/view/1"])]])
ARTICLE = '''<html><head>
<meta property="og:site_name" content="뉴시스">
<meta property="og:description" content="진주문화관광재단은 일본 도쿄에서 열린 EXPO 에 참가했다. 두 번째 문장. 세 번째 문장은 잘린다.">
<meta property="article:published_time" content="2026-09-03T10:00:00+09:00">
</head></html>'''


def _client():
    def handler(req: httpx.Request) -> httpx.Response:
        u = str(req.url)
        if "news.google.com/articles/" in u:
            return httpx.Response(200, text=REDIRECT_PAGE)
        if "batchexecute" in u:
            return httpx.Response(200, text=BATCH_BODY)
        if "newsis.com" in u:
            return httpx.Response(200, text=ARTICLE)
        return httpx.Response(404)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_google_item_gets_real_url_outlet_and_summary():
    row = {"id": "a1", "source_url": GN, "source_name": "newsis.com",
           "summary": "", "published_at": "2026-09-01T00:00:00+00:00"}
    cache = {}
    with _client() as c:
        fetched, failed, patched = resolve_rows([row], cache, client=c)
    assert (fetched, failed, patched) == (1, 0, 1)
    assert row["source_url"] == "https://www.newsis.com/view/1"
    assert row["source_name"] == "뉴시스"
    assert row["summary"].startswith("진주문화관광재단은")
    assert "세 번째" not in row["summary"], "인용은 두 문장까지"
    assert row["published_at"] == "2026-09-03T10:00:00+09:00"


def test_cache_prevents_a_second_fetch_and_survives_url_rewrite():
    """URL 을 실제 주소로 바꾼 뒤에도 같은 기사를 알아봐야 한다 — id 로 찾는다."""
    row = {"id": "a1", "source_url": GN, "source_name": "", "summary": ""}
    cache = {}
    with _client() as c:
        resolve_rows([row], cache, client=c)
        again = {"id": "a1", "source_url": row["source_url"],
                 "source_name": "", "summary": ""}
        fetched, failed, patched = resolve_rows([again], cache, client=c)
    assert fetched == 0 and patched == 1
    assert again["source_name"] == "뉴시스"


def test_failure_keeps_the_item_untouched():
    """구글이 방식을 바꿔 못 풀어도 기사를 버리지 않는다."""
    row = {"id": "b2", "source_url": GN, "source_name": "v.daum.net", "summary": ""}
    cache = {}
    with httpx.Client(transport=httpx.MockTransport(
            lambda r: httpx.Response(500))) as c:
        fetched, failed, patched = resolve_rows([row], cache, client=c)
    assert (fetched, failed, patched) == (0, 1, 0)
    assert row["source_url"] == GN and row["source_name"] == "v.daum.net"


def test_apply_never_overwrites_an_existing_summary():
    row = {"id": "x", "source_url": "https://real", "summary": "원래 요약"}
    assert not apply(row, {"summary": "다른 요약"})
    assert row["summary"] == "원래 요약"


def test_apply_rejects_non_iso_dates():
    row = {"id": "x", "source_url": "https://real", "published_at": "2026-09-03"}
    apply(row, {"published": "3 Sep 2026"})
    assert row["published_at"] == "2026-09-03"
