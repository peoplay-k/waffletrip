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
