import json
from pathlib import Path

from src.build import (load_recent_items, site_has_content, build,
                       SITE_WINDOW_DAYS)
from src.models import Item, item_to_dict

TODAY = "2026-08-31"
NOW = "2026-08-31T05:00:00+09:00"


def make(item_id, title, published="2026-08-31T05:00:00+09:00", grade="B"):
    return Item(id=item_id, grade=grade, region="guam", section="news",
                title=title, summary="요약.", source_name="Guam Post",
                source_url=f"https://example.com/{item_id}",
                published_at=published, collected_at=NOW, status="draft",
                title_hash="h")


def write_day(items_dir: Path, day: str, items):
    items_dir.mkdir(parents=True, exist_ok=True)
    with open(items_dir / f"{day}.jsonl", "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")


def test_loads_todays_items(tmp_path):
    write_day(tmp_path, TODAY, [make("1", "오늘 소식")])
    assert [i.id for i in load_recent_items(str(tmp_path), TODAY)] == ["1"]


def test_loads_items_from_previous_days_in_window(tmp_path):
    write_day(tmp_path, TODAY, [make("1", "오늘")])
    write_day(tmp_path, "2026-08-25", [make("2", "엿새 전",
                                            published="2026-08-25T05:00:00+09:00")])
    assert len(load_recent_items(str(tmp_path), TODAY)) == 2


def test_ignores_items_outside_the_window(tmp_path):
    write_day(tmp_path, "2026-07-01", [make("old", "두 달 전")])
    assert load_recent_items(str(tmp_path), TODAY) == []


def test_same_article_in_two_days_appears_once(tmp_path):
    """14일 윈도우라 같은 기사가 여러 날 파일에 있을 수 있다.

    실측에서 이걸 안 걸러 지역 페이지마다 모든 기사가 두 번씩 실렸다
    (괌 페이지 20줄 = 고유 10건 x 2).
    """
    write_day(tmp_path, "2026-08-30", [make("same", "같은 기사",
                                            published="2026-08-30T05:00:00+09:00")])
    write_day(tmp_path, TODAY, [make("same", "같은 기사",
                                     published="2026-08-31T05:00:00+09:00")])
    items = load_recent_items(str(tmp_path), TODAY)
    assert len(items) == 1


def test_deduplication_keeps_the_newest_copy(tmp_path):
    """제목이 수정됐으면 최신 판본이 남아야 한다."""
    write_day(tmp_path, "2026-08-30", [make("same", "예전 제목",
                                            published="2026-08-30T05:00:00+09:00")])
    write_day(tmp_path, TODAY, [make("same", "고친 제목",
                                     published="2026-08-31T09:00:00+09:00")])
    assert load_recent_items(str(tmp_path), TODAY)[0].title == "고친 제목"


def test_sorts_newest_first(tmp_path):
    write_day(tmp_path, TODAY, [
        make("old", "예전", published="2026-08-28T05:00:00+09:00"),
        make("new", "최신", published="2026-08-31T09:00:00+09:00"),
    ])
    assert [i.id for i in load_recent_items(str(tmp_path), TODAY)] == ["new", "old"]


def test_missing_items_dir_is_not_an_error(tmp_path):
    assert load_recent_items(str(tmp_path / "nope"), TODAY) == []


def test_window_constant_is_two_weeks():
    assert SITE_WINDOW_DAYS == 14


def test_site_has_content_is_false_for_missing_dir(tmp_path):
    assert site_has_content(str(tmp_path / "nope")) is False


def test_site_has_content_is_true_when_index_exists(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    assert site_has_content(str(tmp_path)) is True


def test_build_writes_index_rss_sitemap_robots_cname(tmp_path):
    build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    for name in ("index.html", "rss.xml", "sitemap.xml", "robots.txt", "CNAME"):
        assert (tmp_path / name).exists(), name


def test_build_returns_the_paths_it_wrote(tmp_path):
    paths = build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    assert all(Path(p).exists() for p in paths)


def test_build_with_no_items_still_produces_a_site(tmp_path):
    """최초 실행에서 수집이 0건이어도 껍데기는 나와야 한다."""
    build([], str(tmp_path), TODAY, NOW)
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "guam" / "index.html").exists()
