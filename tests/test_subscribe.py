from pathlib import Path

from src.models import Item
from src.render.feeds import render_rss
from src.render.site import render_site

NOW = "2026-09-09T05:00:00+09:00"


def make(item_id, title, region="guam"):
    return Item(id=item_id, grade="B", region=region, section="news", title=title,
                summary="요약 문장.", source_name="Guam Post",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h")


def test_구독_페이지가_전체와_지역_피드를_안내한다(tmp_path):
    render_site([make("1", "괌 신규 취항")], str(tmp_path), "2026-09-09")
    html = (tmp_path / "subscribe" / "index.html").read_text(encoding="utf-8")
    assert "/rss.xml" in html and "/guam/rss.xml" in html and "/jeju/rss.xml" in html
    assert "아직 없습니다" in html          # 없는 이메일 구독을 약속하지 않는다
    assert 'href="/subscribe/"' in html    # 상단 '구독' 이 XML 원문이 아니라 여기로


def test_지역_피드는_그_지역_기사만_담는다(tmp_path):
    items = [make("1", "괌 신규 취항", "guam"), make("2", "제주 축제", "jeju")]
    path = render_rss(items, str(tmp_path), NOW, region="guam")
    xml = Path(path).read_text(encoding="utf-8")
    assert path.endswith("guam/rss.xml")
    assert "괌 신규 취항" in xml and "제주 축제" not in xml
    assert "/guam/rss.xml" in xml and "<title>와플트립 괌</title>" in xml


def test_지역면이_지역_피드를_알린다(tmp_path):
    render_site([make("1", "괌 신규 취항")], str(tmp_path), "2026-09-09")
    html = (tmp_path / "guam" / "index.html").read_text(encoding="utf-8")
    assert 'type="application/rss+xml"' in html and "/guam/rss.xml" in html
