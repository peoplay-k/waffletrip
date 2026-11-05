"""기사거리 묶음. 남의 단독 기사는 재료로 쓰지 않는다(2026-10-01 편집국장)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
from story_material import is_exclusive  # noqa: E402


def test_exclusive_stories_are_not_material():
    for title in ("[단독] 대한항공, 괌 노선 증편", "(단독)제주항공 신규 취항",
                  "단독: 아시아나 사이판 재개", "【단독】 하와이 호텔 매각",
                  "EXCLUSIVE: Guam resort sold"):
        assert is_exclusive(title), title


def test_ordinary_words_are_not_mistaken_for_exclusives():
    for title in ("괌 단독 여행 늘어", "단독주택 화재 없이 지나가", "사이판 단독 패키지 출시"):
        assert not is_exclusive(title), title


def test_여행_기사거리가_아닌_제목은_재료에서_뺀다():
    """2026-10-30 종합지 여행면을 붙인 첫 실행에서 재료에 섞여 들어온 것들."""
    from story_material import is_not_travel
    for t in ["[부고] 서호영 씨(대한항공 전무) 모친상",
              "북한, '무인항공기술발전-2026' 전시회 개최",
              "인천공항, '바이오 화물' 잡는다…유럽 콜드체인 동맹 강화",
              "놀에 이어 마이리얼트립까지…여행·숙박 플랫폼 잇단 개인정보 유출",
              "염동열 강원관광재단 대표 후보자 청문회서 '보은 인사' 공방"]:
        assert is_not_travel(t), t
    for t in ["이스타항공 홍콩~부산 신규 취항…첫 입국 관광객 200여명 '환영'",
              "엔저에 일본행 급증…원·엔 환율 900원대",
              "하동군, 섬진강권 관광지 순환버스로 주말여행 편의 높인다",
              "겨울에 눈여겨볼 만한 해외 패키지여행 3"]:
        assert not is_not_travel(t), t


def test_여행신문_최근_50건을_따로_늘어놓고_쓴_것에_표시한다(tmp_path, monkeypatch):
    """2026-11-04 사장님: "기사 매일 여행신문쪽 50개 훑어보고 거기서 기사를 가지고와"."""
    import json
    import story_material as sm
    items = tmp_path / "data" / "items"
    items.mkdir(parents=True)
    rows = [{"id": f"x{i}", "grade": "B", "region": "industry", "source_name": "여행신문",
             "title": f"여행 소식 {i}", "summary": "요약", "published_at": f"2026-11-0{1 + i % 3}T0{i % 10}:00",
             "source_url": f"https://www.traveltimes.co.kr/a{i}"} for i in range(60)]
    rows.append({"id": "y", "grade": "B", "region": "industry", "source_name": "트래블데일리",
                 "title": "다른 매체", "published_at": "2026-11-03T00:00", "source_url": "https://t/1"})
    rows.append({"id": "z", "grade": "B", "region": "industry", "source_name": "여행신문",
                 "title": "[단독] 남의 단독", "published_at": "2026-11-03T09:00", "source_url": "https://t/2"})
    (items / "2026-11-03.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    picked = sm.latest_from("여행신문", 50)
    assert len(picked) == 50
    assert all(r["source_name"] == "여행신문" for r in picked)
    assert all("단독" not in r["title"] for r in picked)
    lines = sm.traveltimes_section(picked, {picked[0]["source_url"]})
    assert lines[0].startswith("## 여행신문 최근 50건")
    assert lines[5].startswith("- ✅ ")
    assert sum(1 for x in lines if x.startswith("- ✅")) == 1


def test_연예_제목에서_사람_그룹_이름을_뽑고_작품명은_뺀다():
    """2026-11-05 사장님: "연예기사는 인터넷에서 활용할 수 있는 이미지들 체크하고 올리자"."""
    from story_material import ent_names
    assert ent_names("김우빈 주연 드라마 ‘기프트’, 12월 5일 첫 방송")[0] == "김우빈"
    assert "기프트" not in ent_names("김우빈 주연 드라마 ‘기프트’, 12월 5일 첫 방송")
    assert ent_names("[잇슈 컬처] 리센느, 컴백과 동시에 음원 차트 1위")[0] == "리센느"
    assert "BTS" in ent_names("BTS 남미 투어에 85만명…전체 매진")


def test_연예_사진_줄은_찾은_이름만_최대_두_장_붙인다():
    from story_material import ent_photo_lines
    groups = [[{"title": "트와이스 나연, 11월 20일 솔로 컴백"}], [{"title": "박스오피스 1위"}]]

    def finder(names):
        found = {n: {"label": n} for n in names if n in ("트와이스", "나연")}
        return found, lambda p: f"![{p['label']} · 사진 X · CC BY 3.0 · 위키미디어 공용](https://upload.wikimedia.org/x.jpg)"
    out = ent_photo_lines(groups, finder)
    assert len(out[0]) == 2 and out[0][0].startswith("- 사진(자유 이용, 트와이스)")
    assert out[1] == []


def test_연예_사진_찾기가_실패해도_재료는_나간다():
    from story_material import ent_photo_lines

    def broken(names):
        raise RuntimeError("network")
    assert ent_photo_lines([[{"title": "트와이스 컴백"}]], broken) == {}


def test_기사_말은_사람_이름으로_보지_않는다():
    """2026-11-05: "차트 강타!" 의 강타가 가수 강타 사진으로 붙었다."""
    from story_material import ent_names
    names = ent_names("'국민 걸그룹' 차트 강타! 리센느, 신보 발매 2시간만 멜론 TOP100 1위")
    assert "강타" not in names and "리센느" in names


def test_공식_채널_인기_영상만_고른다():
    """2026-11-05 사장님: "유튜브 … 1만 이상 되는 영상 보고 그걸 기사화해서 올리는 거"."""
    import official_videos as ov
    assert ov.views_of("조회수 12,345회") == 12345
    assert ov.views_of("조회수 1.2만회") == 12000
    assert ov.views_of("조회수 없음") == 0

    def vr(vid, channel, views, age, verified=True, cid="UCx"):
        badge = ',"badges":[{"style":"BADGE_STYLE_TYPE_VERIFIED"}]' if verified else ""
        return ('"videoRenderer":{"videoId":"%s","title":{"runs":[{"text":"영상 %s"}]},'
                '"ownerText":{"runs":[{"text":"%s"}]},"browseId":"%s",'
                '"publishedTimeText":{"simpleText":"%s"},"viewCountText":{"simpleText":"조회수 %s회"}%s},'
                % (vid, vid, channel, cid, age, views, badge))
    html = (vr("aaaaaaaaaaa", "HYBE LABELS", "152,003", "2일 전")
            + vr("bbbbbbbbbbb", "여행 브이로거", "90,000", "1일 전")            # 개인 — 빠진다
            + vr("ccccccccccc", "HYBE LABELS", "9,999", "1일 전")              # 1만 미만
            + vr("ddddddddddd", "JYP Entertainment", "50,000", "2주 전")        # 일주일 넘음
            + vr("eeeeeeeeeee", "KBS Drama", "20,000", "3일 전", verified=False,
                 cid="UChpjIaEgwtDZtmWEkzFulSA")                                 # 방송사 id 목록
            + vr("fffffffffff", "SMTOWN 팬계정", "80,000", "1일 전", verified=False))  # 배지 없음
    got = [v["id"] for v in ov.pick(ov.parse_results(html))]
    assert got == ["aaaaaaaaaaa", "eeeeeeeeeee"]
    md = ov.to_markdown({"items": [{**ov.parse_results(html)[0], "description": "설명"}], "queries": 3})
    assert "@youtube aaaaaaaaaaa" in md and "조회수 152,003회" in md
