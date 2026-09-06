import json
from pathlib import Path

from src.collect import collect_all, write_raw
from src.models import Item
from src.sources import Source

NOW = "2026-08-31T05:00:00+09:00"

RSS_SOURCE = Source(id="good_rss", region="guam", section="news", name="Good",
                    type="rss", url="https://example.com/rss", lang="en",
                    enabled=True)
BAD_SOURCE = Source(id="bad_rss", region="jeju", section="news", name="Bad",
                    type="rss", url="https://example.com/bad", lang="ko",
                    enabled=True)

FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Good story</title><link>https://example.com/a</link>
<description>Body sentence.</description></item></channel></rss>"""


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


class FakeClient:
    """good 은 피드를 주고 bad 는 터진다."""

    def get(self, url, **kwargs):
        if url.endswith("/bad"):
            raise ConnectionError("boom")
        return FakeResponse(FEED)


def test_one_failure_does_not_stop_the_others():
    items, errors = collect_all([RSS_SOURCE, BAD_SOURCE], FakeClient(), NOW)
    assert len(items) == 1
    assert items[0].title == "Good story"
    assert len(errors) == 1
    assert errors[0]["source_id"] == "bad_rss"
    assert "boom" in errors[0]["error"]


def test_all_failing_yields_no_items_but_records_errors():
    items, errors = collect_all([BAD_SOURCE], FakeClient(), NOW)
    assert items == []
    assert len(errors) == 1


def test_empty_source_list_is_not_an_error():
    assert collect_all([], FakeClient(), NOW) == ([], [])


def test_write_raw_groups_items_by_source(tmp_path):
    items = [
        Item(id="1", grade="B", region="guam", section="news", title="t1",
             summary="s", source_name="Good", source_url="https://example.com/a",
             published_at=NOW, collected_at=NOW, status="draft", title_hash="h1"),
    ]
    errors = [{"source_id": "bad_rss", "url": "u", "error": "boom"}]
    write_raw(str(tmp_path), items, errors)

    written = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    assert len(written) == 1
    assert written[0]["title"] == "t1"

    logged = json.loads((tmp_path / "_errors.json").read_text(encoding="utf-8"))
    assert logged[0]["source_id"] == "bad_rss"


def test_write_raw_creates_missing_directory(tmp_path):
    target = tmp_path / "deep" / "2026-08-31"
    write_raw(str(target), [], [])
    assert (target / "items.json").exists()
    assert (target / "_errors.json").exists()


class _Src:
    id, type, region, section = "s1", "rss", "guam", "news"
    name, url, lang, enabled, curated = "테스트", "https://x/rss", "ko", True, False


RETRY_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>괌 신규 취항</title><link>https://x/1</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""

NOW2 = "2026-09-03T05:00:00+09:00"


def test_retry_uses_a_browser_agent_when_blocked(monkeypatch):
    """봇 UA 를 규칙으로 막는 곳이 있다. 한 번 더 청한다."""
    import httpx
    from src.collect import collect_with_retry

    def blocked(*a, **k):
        raise httpx.HTTPStatusError(
            "403", request=httpx.Request("GET", "https://x/rss"),
            response=httpx.Response(403, request=httpx.Request("GET", "https://x/rss")))

    seen = {}

    class C2(httpx.Client):
        def __init__(self, *a, **k):
            seen.update(k)
            super().__init__(transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text=RETRY_FEED)), **{
                    x: y for x, y in k.items() if x != "verify"})

    monkeypatch.setattr("src.collect.httpx.Client", C2)
    items, err = collect_with_retry(_Src(), type("B", (), {"get": blocked})(), NOW2)
    assert err is None and len(items) == 1
    assert "Mozilla" in seen["headers"]["User-Agent"]


def test_retry_relaxes_verification_only_for_a_broken_chain(monkeypatch):
    """서버가 중간 인증서를 빠뜨린 설정 실수다. 그 소스에 한해서만 봐준다."""
    import httpx
    from src.collect import collect_with_retry

    def ssl_fail(*a, **k):
        raise httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] bad chain")

    seen = {}

    class C2(httpx.Client):
        def __init__(self, *a, **k):
            seen.update(k)
            super().__init__(transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text=RETRY_FEED)), **{
                    x: y for x, y in k.items() if x != "verify"})

    monkeypatch.setattr("src.collect.httpx.Client", C2)
    items, err = collect_with_retry(_Src(), type("B", (), {"get": ssl_fail})(), NOW2)
    assert err is None and len(items) == 1
    assert seen.get("verify") is False


def test_a_second_failure_is_reported_not_swallowed(monkeypatch):
    import httpx
    from src.collect import collect_with_retry

    def dead(*a, **k):
        raise httpx.ConnectTimeout("timed out")

    class C2(httpx.Client):
        def __init__(self, *a, **k):
            super().__init__(transport=httpx.MockTransport(
                lambda r: httpx.Response(500)), **{
                    x: y for x, y in k.items() if x != "verify"})

    monkeypatch.setattr("src.collect.httpx.Client", C2)
    items, err = collect_with_retry(_Src(), type("B", (), {"get": dead})(), NOW2)
    assert items == [] and err and "재시도" in err
