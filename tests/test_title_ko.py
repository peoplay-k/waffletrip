import json

from src.models import Item
from src.render.site import article_url, render_site
from src.title_ko import SKIP, apply, is_english, load, merge, todo

NOW = "2026-09-09T05:00:00+09:00"


def make(item_id, title, region="hawaii"):
    return Item(id=item_id, grade="B", region=region, section="news", title=title,
                summary="요약 문장.", source_name="Beat of Hawaii",
                source_url=f"https://example.com/{item_id}", published_at=NOW,
                collected_at=NOW, status="draft", title_hash="h")


def test_영문_판정():
    assert is_english("Runway crack leads to another closure at Kona airport")
    assert not is_english("코나공항 활주로 균열로 또 폐쇄")
    assert not is_english("KTX 증편·SRT 신설")
    assert not is_english("")


def test_번역을_입히면_원제가_남고_주소는_그대로():
    it = make("abcdef1234567890", "Runway crack leads to another closure at Kona airport")
    before = article_url(it)
    assert apply([it], {it.id: "코나공항 활주로 균열로 또 폐쇄"}) == 1
    assert it.title == "코나공항 활주로 균열로 또 폐쇄"
    assert it.title_orig.startswith("Runway crack")
    assert article_url(it) == before


def test_한글_없는_번역과_건너뛰기_표시는_입히지_않는다():
    it = make("1", "Some English title")
    assert apply([it], {"1": "still english"}) == 0
    assert apply([it], {"1": SKIP}) == 0
    assert it.title == "Some English title" and it.title_orig is None


def test_할일_목록은_영문이면서_표에_없는_것만():
    items = [make("1", "English one"), make("2", "한글 제목"),
             make("3", "English two"), make("4", "English three")]
    assert [t["id"] for t in todo(items, {"3": "영문 둘", "4": SKIP})] == ["1"]
    assert todo(items, {}, limit=2)[1]["id"] == "3"


def test_merge_는_검사하고_앞자리로_풀고_정렬해_저장한다(tmp_path):
    table = tmp_path / "title_ko.json"
    new = tmp_path / "new.json"
    new.write_text(json.dumps({"bbbb": "한글 제목", "aaaa": "no hangul", "cccc": SKIP,
                               "dddd": "짝 없는 것"}), encoding="utf-8")
    items = [make("bbbbbbbb-1", "B"), make("cccccccc-1", "C"),
             make("dddddddd-1", "D"), make("dddddddd-2", "D2")]
    added, errors = merge(str(new), str(table), items)
    assert added == 2
    assert sorted(e[:4] for e in errors) == ["aaaa", "dddd"]
    assert list(json.loads(table.read_text(encoding="utf-8"))) == ["bbbbbbbb-1", "cccccccc-1"]
    assert load(str(table)) == {"bbbbbbbb-1": "한글 제목", "cccccccc-1": SKIP}


def test_기사_페이지에_원제를_병기한다(tmp_path):
    it = make("abcdef1234567890", "Runway crack leads to another closure at Kona airport")
    apply([it], {it.id: "코나공항 활주로 균열로 또 폐쇄"})
    render_site([it], str(tmp_path), "2026-09-09")
    html = (tmp_path / article_url(it).strip("/") / "index.html").read_text(encoding="utf-8")
    assert "코나공항 활주로 균열로 또 폐쇄" in html
    assert 'class="orig"' in html and "Runway crack" in html
    assert "alternativeHeadline" in html
