import json

from src.indexnow import (KEY_URL_PATH, MAX_URLS, load_key, submit,
                          todays_urls)
from src.models import Item, item_to_dict

NOW = "2026-09-07T05:00:00+09:00"
TODAY = "2026-09-07"
SITE = "https://waffletrip.com"


def make(item_id, title, region="guam", grade="B"):
    return Item(id=item_id, grade=grade, region=region, section="news",
                title=title, summary="요약.", source_name="여행신문",
                source_url="https://example.com/a", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h")


def write_day(tmp_path, day, items):
    with open(tmp_path / f"{day}.jsonl", "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")


class FakeResponse:
    def __init__(self, code):
        self.status_code = code


class FakeClient:
    def __init__(self, code=200):
        self.code, self.sent = code, None

    def post(self, url, json=None, timeout=None):
        self.sent = (url, json)
        return FakeResponse(self.code)


# --- 키 ---

def test_missing_key_file_is_empty_string(tmp_path):
    """키가 없으면 통지를 건너뛴다. 발행을 막지 않는다."""
    assert load_key(str(tmp_path / "nope.txt")) == ""


def test_key_is_stripped(tmp_path):
    path = tmp_path / "k.txt"
    path.write_text("  abc123\n", encoding="utf-8")
    assert load_key(str(path)) == "abc123"


# --- 주소 목록 ---

def test_article_and_region_and_home_are_included(tmp_path):
    write_day(tmp_path, TODAY, [make("abcdef1234567890", "괌 신규 취항")])
    urls = todays_urls(str(tmp_path), TODAY, SITE)
    assert f"{SITE}/" in urls
    assert f"{SITE}/guam/" in urls
    assert any("/guam/abcdef12-" in u for u in urls)


def test_grade_a_gets_no_article_url_but_marks_data_page(tmp_path):
    """환율·날씨는 개별 쪽이 없다. 지역면과 데이터면만 알린다."""
    fx = make("fx1", "오늘의 환율 — 1 USD", grade="A")
    write_day(tmp_path, TODAY, [fx])
    urls = todays_urls(str(tmp_path), TODAY, SITE)
    assert f"{SITE}/data/" in urls
    assert not any("fx1" in u for u in urls)


def test_missing_day_file_yields_nothing(tmp_path):
    assert todays_urls(str(tmp_path), TODAY, SITE) == []


def test_urls_are_deduplicated_and_capped(tmp_path):
    items = [make(f"id{i:016d}", f"기사 {i}") for i in range(3)]
    write_day(tmp_path, TODAY, items + items)
    urls = todays_urls(str(tmp_path), TODAY, SITE)
    assert len(urls) == len(set(urls))
    assert len(urls) <= MAX_URLS


def test_unknown_region_is_not_added_as_a_section(tmp_path):
    """지역 키가 아닌 값이 지역면 주소로 새 나가면 404 를 알리게 된다."""
    odd = make("x1", "제목", region="mars")
    write_day(tmp_path, TODAY, [odd])
    urls = todays_urls(str(tmp_path), TODAY, SITE)
    assert f"{SITE}/mars/" not in urls


# --- 전송 ---

def test_submit_sends_host_key_and_keylocation():
    client = FakeClient()
    code = submit([f"{SITE}/"], "KEY", client, SITE)
    url, body = client.sent
    assert code == 200
    assert body["host"] == "waffletrip.com"
    assert body["key"] == "KEY"
    assert body["keyLocation"] == SITE + KEY_URL_PATH
    assert body["urlList"] == [f"{SITE}/"]


def test_submit_without_key_does_nothing():
    client = FakeClient()
    assert submit([f"{SITE}/"], "", client, SITE) == 0
    assert client.sent is None


def test_submit_without_urls_does_nothing():
    client = FakeClient()
    assert submit([], "KEY", client, SITE) == 0
    assert client.sent is None
