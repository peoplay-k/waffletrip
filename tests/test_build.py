import json
from pathlib import Path

from src.build import (load_recent_items, site_has_content, build, main,
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


def test_build_writes_index_rss_sitemap_robots(tmp_path):
    build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    for name in ("index.html", "rss.xml", "sitemap.xml", "robots.txt"):
        assert (tmp_path / name).exists(), name


def test_build_writes_cname_for_the_custom_domain(tmp_path):
    """CNAME 이 있어야 Pages 가 waffletrip.com 으로 서비스한다.

    순서가 중요하다. DNS(A·CNAME)를 먼저 붙인 뒤에 이 파일을 낸다 —
    반대로 하면 Pages 가 죽은 도메인으로 301 을 걸어 사이트가 통째로
    안 열린다. 2026-09-06 에 DNS 가 붙어 켰다.
    """
    build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    assert (tmp_path / "CNAME").read_text(encoding="utf-8").strip() == "waffletrip.com"


def test_build_returns_the_paths_it_wrote(tmp_path):
    paths = build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    assert all(Path(p).exists() for p in paths)


def test_build_with_no_items_still_produces_a_site(tmp_path):
    """최초 실행에서 수집이 0건이어도 껍데기는 나와야 한다."""
    build([], str(tmp_path), TODAY, NOW)
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "guam" / "index.html").exists()


def test_main_refuses_to_build_an_empty_site(tmp_path):
    """빈 사이트를 배포하면 색인된 페이지가 전부 사라진다.

    CI 에서는 public/ 이 gitignore 라 체크아웃에 없다. 기존 사이트 존재 여부로
    판단하던 방어선이 러너에서는 항상 거짓이었다.
    """
    out = tmp_path / "public"
    assert main(data_dir=str(tmp_path), out_dir=str(out)) == 1
    assert not out.exists()


def test_build_clears_stale_pages(tmp_path):
    """내려간 기사의 쪽이 남아 있으면 안 된다.

    CI 는 새 체크아웃이라 문제가 없지만 로컬은 쌓인다. 로컬과 라이브가
    달라지면 점검 결과를 믿을 수 없다.
    """
    stale = tmp_path / "guam" / "내려간-기사"
    stale.mkdir(parents=True)
    (stale / "index.html").write_text("옛 기사", encoding="utf-8")

    build([make("1", "괌 소식")], str(tmp_path), TODAY, NOW)
    assert not stale.exists()
    assert (tmp_path / "index.html").exists()
