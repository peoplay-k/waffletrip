"""본문 매체 인용 금지(2026-10-19 사장님: "PDN 보도에 따르면 이런 부분은 아예 삭제해")."""
from __future__ import annotations

import json

import yaml

from src.attribution import find_media_attribution, media_names, strip_media_attribution

SRC = ("\n\n**출처** · [Pacific Daily News 「a」](https://x/a) (2026-10-18 보도), "
       "[Pacific Island Times 「b」](https://x/b) (2026-10-18 보도), "
       "[MTN 머니투데이방송 「c」](https://x/c) (2026-10-01 보도). 이 기사는 위 보도를 바탕으로 피플로드가 정리했다.")


def fix(s: str) -> str:
    return strip_media_attribution(s + SRC).split("\n\n**출처**")[0]


def test_outlet_report_frame_is_removed_and_ending_restored():
    assert fix("PDN은 18일 보도에서 공립학교가 19일(월) 모두 휴교한다고 전했다.") == \
        "공립학교가 19일(월) 모두 휴교한다."
    assert fix("Pacific Island Times는 18일 보도에서 아기 16명이 태어났다고 병원 측이 밝혔다고 전했다.") == \
        "아기 16명이 태어났다고 병원 측이 밝혔다."


def test_quoted_primary_source_survives_as_according_to():
    out = fix("PDN은 17일 별도 보도에서 합동정보센터(Joint Information Center)를 인용해 "
              "섬 전력의 약 50%만 공급되고 있다고 전했다.")
    assert out == "합동정보센터(Joint Information Center)에 따르면 섬 전력의 약 50%만 공급되고 있다."


def test_same_report_and_outlet_according_to_are_dropped():
    assert fix("같은 보도에 따르면 이 호텔은 네 번째 지점이다.") == "이 호텔은 네 번째 지점이다."
    assert fix("MTN 보도에 따르면 **10월 15일 숙박분부터 예약을 받는다.**") == "**10월 15일 숙박분부터 예약을 받는다.**"
    assert fix("PDN에 따르면 괌은 17일 오후 1시부터 대비태세 1단계에 들어갔다.") == \
        "괌은 17일 오후 1시부터 대비태세 1단계에 들어갔다."


def test_trailing_outlet_attribution_is_dropped():
    assert fix("마을 이장들은 주민들을 대피소로 옮겼다고 PDN이 전했다.") == "마을 이장들은 주민들을 대피소로 옮겼다."


def test_not_in_report_becomes_not_yet_known():
    assert fix("- 요금은 이번 보도에 나오지 않았다.") == "- 요금은 아직 알려지지 않았다."


def test_primary_sources_and_source_line_are_untouched():
    for s in ("합동정보센터에 따르면 전력의 절반이 끊겼다.",
              "괌전력청은 복구에 사흘이 걸린다고 밝혔다.",
              "대한항공은 12월부터 매일 운항한다고 밝혔다."):
        assert fix(s) == s
    full = strip_media_attribution("본문이다." + SRC)
    assert full.endswith(SRC.strip().split("\n\n")[-1])


def test_unfixable_quote_is_reported():
    body = 'Hawaii News Now는 별도 보도에서 **"경로가 불확실하다"**고 명시했다.' + SRC
    assert strip_media_attribution(body).startswith("Hawaii News Now는")
    assert find_media_attribution(strip_media_attribution(body))


def test_names_come_from_source_line_with_aliases():
    names = media_names(SRC)
    assert "Pacific Daily News" in names and "PDN" in names and "MTN" in names


def _draft(tmp_path, body: str, summary: str = "") -> str:
    front = {"id": "t-1", "channel": "travel", "region": "guam", "title": "괌 학교 휴교",
             "status": "approved", "summary": summary}
    p = tmp_path / "review" / "20261019_guam_test.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\n" + yaml.safe_dump(front, allow_unicode=True) + "---\n" + body, encoding="utf-8")
    return str(p.parent)


def test_publish_cleans_body_summary_and_draft(tmp_path, monkeypatch):
    from src import publish_drafts
    body = ("괌 공립학교가 쉰다. PDN은 18일 보도에서 공립학교가 19일(월) 휴교한다고 전했다.\n\n"
            "같은 보도에 따르면 사업장 명단도 공개됐다." + SRC)
    review = _draft(tmp_path, body, summary="PDN 보도에 따르면 괌 공립학교가 19일 쉰다.")
    data = tmp_path / "data"
    (data / "items").mkdir(parents=True)
    monkeypatch.setattr(publish_drafts, "datetime", type("D", (), {
        "now": staticmethod(lambda tz=None: __import__("datetime").datetime(2026, 10, 19, 9, tzinfo=tz))}))
    publish_drafts.main(str(data), review)
    rows = [json.loads(x) for x in (data / "items" / "2026-10-19.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert "보도에서" not in rows[0]["body_md"] and "따르면" not in rows[0]["body_md"].split("**출처**")[0]
    assert rows[0]["summary"] == "괌 공립학교가 19일 쉰다."
    draft = (tmp_path / "review" / "20261019_guam_test.md").read_text(encoding="utf-8")
    assert "PDN은 18일 보도에서" not in draft and "status: published" in draft


def test_publish_holds_back_article_with_leftover_attribution(tmp_path, monkeypatch, capsys):
    from src import publish_drafts
    body = ("괌에 태풍이 왔다. Hawaii News Now는 별도 보도에서 **\"경로가 불확실하다\"**고 명시했다." + SRC)
    review = _draft(tmp_path, body)
    data = tmp_path / "data"
    (data / "items").mkdir(parents=True)
    publish_drafts.main(str(data), review)
    assert not (data / "items" / "2026-10-19.jsonl").exists() or \
        "괌 학교 휴교" not in (data / "items" / "2026-10-19.jsonl").read_text(encoding="utf-8")
    assert "발행 보류" in capsys.readouterr().err


def test_moved_article_url_redirects_to_new_address(tmp_path, monkeypatch):
    from src.models import Item, title_hash
    from src.render import site
    it = Item(id="c-abcdef12", grade="C", region="guam", section="news", title="괌 새 제목",
              summary="요약.", source_name="", source_url="", published_at="2026-10-19T09:00:00+09:00",
              collected_at="2026-10-19T09:00:00+09:00", status="published", title_hash=title_hash("괌 새 제목"),
              body_md="본문이다.")
    moved = tmp_path / "moved.json"
    moved.write_text(json.dumps({"/guam/c-abcdef-옛-제목/": "c-abcdef12"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(site, "MOVED_URLS", str(moved))
    out = tmp_path / "out"
    site.render_site([it], str(out), "2026-10-19")
    page = (out / "guam" / "c-abcdef-옛-제목" / "index.html").read_text(encoding="utf-8")
    assert site.article_url(it) in page and "noindex" in page
