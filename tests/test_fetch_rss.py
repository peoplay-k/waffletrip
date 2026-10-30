from pathlib import Path

from src.fetch.rss import strip_html, first_sentences, parse_feed
from src.sources import Source

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"
NOW = "2026-08-31T05:00:00+09:00"

SOURCE = Source(id="guam_sample", region="guam", section="news",
                name="Sample Guam News", type="rss",
                url="https://example.com/rss", lang="en", enabled=True)


def test_strip_html_removes_tags_and_entities():
    assert strip_html("<p>Hello &amp; bye</p>") == "Hello & bye"


def test_strip_html_collapses_whitespace():
    assert strip_html("a\n\n  b\t c") == "a b c"


def test_first_sentences_takes_two():
    text = "One. Two. Three. Four."
    assert first_sentences(text, 2) == "One. Two."


def test_first_sentences_returns_all_when_fewer_than_n():
    assert first_sentences("Only one.", 2) == "Only one."


def test_first_sentences_handles_no_terminator():
    assert first_sentences("No terminator here", 2) == "No terminator here"


def test_parse_feed_returns_all_entries():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert len(items) == 2


def test_parse_feed_summary_is_two_sentences():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].summary == (
        "United Airlines will add a third daily flight. "
        "The new service starts in October."
    )


def test_parse_feed_carries_source_metadata():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].source_name == "Sample Guam News"
    assert items[0].region == "guam"
    assert items[0].section == "news"
    assert items[0].collected_at == NOW


def test_parse_feed_normalizes_tracking_params_in_id():
    """utm_source 가 붙은 링크와 안 붙은 링크가 같은 id 여야 한다."""
    from src.models import make_id
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].id == make_id("https://example.com/news/united-guam", "", "")


def test_parse_feed_defaults_to_draft_and_grade_b():
    items = parse_feed(SOURCE, FIXTURE.read_text(encoding="utf-8"), NOW)
    assert items[0].status == "draft"
    assert items[0].grade == "B"


def test_parse_feed_uses_collected_at_when_no_pubdate():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>No date</title><link>https://example.com/x</link>
    <description>Body.</description></item></channel></rss>"""
    items = parse_feed(SOURCE, xml, NOW)
    assert items[0].published_at == NOW


def test_parse_feed_skips_entry_without_title():
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><link>https://example.com/x</link><description>Body.</description></item>
    </channel></rss>"""
    assert parse_feed(SOURCE, xml, NOW) == []


def test_parse_feed_on_garbage_returns_empty():
    assert parse_feed(SOURCE, "not xml at all", NOW) == []


# --- region: auto (국내 여행 전문 매체) ---

AUTO_SOURCE = Source(id="traveltimes", region="auto", section="news",
                     name="여행신문", type="rss",
                     url="https://example.com/rss", lang="ko", enabled=True)

AUTO_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>진에어, 괌 노선 증편 결정</title><link>https://example.com/g</link>
<description>10월부터 주 7회로 늘린다.</description></item>
<item><title>오사카 벚꽃 명소 총정리</title><link>https://example.com/o</link>
<description>봄 시즌 추천 코스.</description></item>
<item><title>다낭 신규 리조트 오픈</title><link>https://example.com/d</link>
<description>5성급이 문을 연다.</description></item>
</channel></rss>"""


def test_auto_source_assigns_region_per_article():
    items = parse_feed(AUTO_SOURCE, AUTO_FEED, NOW)
    got = [(i.title[:2], i.region) for i in items]
    assert ("진에", "guam") in got
    assert ("다낭", "vietnam") in got


def test_auto_source_now_keeps_japan_articles():
    """일본 지역면이 생겼다. 예전에는 오사카 기사를 버렸다.

    한국인이 가장 많이 가는 해외 도시 TOP10 에 일본이 네 곳 들어 있어
    지역면을 열었고, 그 순간 버려지던 기사가 살아났다.
    """
    items = parse_feed(AUTO_SOURCE, AUTO_FEED, NOW)
    osaka = [i for i in items if "오사카" in i.title]
    assert osaka, "오사카 기사가 버려지고 있다"
    assert all(i.region == "japan" for i in osaka)


def test_auto_source_ignores_regions_that_appear_only_in_the_summary():
    """요약에 스쳐 지나간 지명으로 지역을 정하지 않는다.

    실측 근거: 요약까지 보고 판정했더니 8건 중 5건이 오탐이었다.
    "티웨이항공 타고 싱가포르 가면…"이 제주로, 여행 기사도 아닌
    "신복위-나주시 금융취약계층 지원"이 제주로 잡혔다.
    """
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>신규 취항 소식</title><link>https://example.com/x</link>
    <description>제주 노선이 늘어난다.</description></item></channel></rss>"""
    got = parse_feed(AUTO_SOURCE, xml, NOW)
    # 제주로 잡히면 안 된다. 목적지 없는 업계 소식으로 받는다(2026-10-15 여행업계면).
    assert [i.region for i in got] == ["industry"]


def test_korean_sentences_split_without_a_space_after_the_period():
    """한국어 기사는 마침표 뒤에 공백이 없는 경우가 흔하다.

    못 자르면 문단 전체가 한 문장이 되어 인용 한도를 넘긴다. 실측에서
    국내 매체 기사의 70%가 200자 초과로 전량 폐기됐다.
    """
    assert first_sentences("개최한다.열린 페스타는 무장애 여행이다.잘 된다.", 2) == (
        "개최한다. 열린 페스타는 무장애 여행이다.")


def test_two_sentences_glued_together_do_not_leak_a_third():
    """종결부호 뒤 공백이 없으면 두 문장이 한 조각으로 붙어 n 을 무력화한다.

    이 함수가 원문 전재를 막는 장치인데 정확히 그 지점에서 샜다.
    n=2 를 요청했는데 실제 문장 3개가 나오면 안 된다.
    """
    text = "First one.Second one attached tightly. Third real one. Fourth."
    assert first_sentences(text, 2) == "First one. Second one attached tightly."


def test_abbreviation_periods_split_conservatively():
    """'U.S.' 뒤 공백에서도 잘린다. 원래 규칙부터 그랬고 그대로 둔다.

    요약이 의도보다 짧아질 뿐 인용 한도를 넘기지는 않는다. 보수적으로 짧은 쪽으로
    틀리는 것은 저작권 관점에서 안전한 방향이라 잡지 않는다.
    """
    assert first_sentences("The U.S. Navy arrived. Next one.", 2) == (
        "The U.S. Navy arrived.")


def test_static_region_source_is_not_retagged():
    """region 이 고정된 소스는 기사 내용과 무관하게 그 지역을 쓴다."""
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>Hawaii tourism note</title><link>https://example.com/h</link>
    <description>Body.</description></item></channel></rss>"""
    # SOURCE 는 region="guam" 고정이다
    assert parse_feed(SOURCE, xml, NOW)[0].region == "guam"


GOOGLE_SOURCE = Source(
    id="gn_japan", region="japan", section="news", name="일본 여행뉴스",
    type="rss", url="https://news.google.com/rss/search?q=%EC%9D%BC%EB%B3%B8",
    lang="ko", enabled=True)

GOOGLE_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>오사카 노선 증편…겨울 성수기 대비 - 여행신문</title>
<link>https://example.com/a</link>
<pubDate>Wed, 03 Sep 2026 01:00:00 GMT</pubDate></item>
<item><title>항공물류 운임 상승세, 3분기 실적 갈린다 - 물류신문</title>
<link>https://example.com/b</link>
<pubDate>Wed, 03 Sep 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_google_news_keeps_articles_about_the_destination():
    items = parse_feed(GOOGLE_SOURCE, GOOGLE_FEED, NOW)
    assert [i.title[:3] for i in items] == ["오사카"]
    assert items[0].region == "japan"


def test_google_news_drops_articles_that_only_match_a_query_word():
    """검색 쿼리가 '일본 (항공 OR 노선 OR 관광 OR 호텔)' 이라 본문에 '항공'만
    있어도 걸려 온다. 물류·주식·부동산 기사가 실제로 일본면에 들어왔다."""
    items = parse_feed(GOOGLE_SOURCE, GOOGLE_FEED, NOW)
    assert all("물류" not in i.title for i in items)


def test_google_news_credits_the_outlet_that_wrote_it():
    items = parse_feed(GOOGLE_SOURCE, GOOGLE_FEED, NOW)
    assert items[0].source_name == "여행신문"


GOSSIP_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>조혜련 "일본 유명 호텔서 제재 받아" - 스포츠조선</title>
<link>https://example.com/g</link>
<pubDate>Wed, 03 Sep 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_entertainment_outlets_never_reach_the_paper():
    """검색 피드가 '일본'만 보고 연예 가십을 물어온다. 여행면에 실을 수 없다."""
    assert parse_feed(GOOGLE_SOURCE, GOSSIP_FEED, NOW) == []


STALE_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>오사카 호텔 신규 개장 - 여행신문</title>
<link>https://example.com/old</link>
<pubDate>Mon, 18 May 2026 01:00:00 GMT</pubDate></item>
<item><title>오사카 노선 증편 - 여행신문</title>
<link>https://example.com/new</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_google_news_drops_stale_articles():
    """검색 피드는 넉 달 전 기사도 준다. 오늘 뉴스처럼 실으면 안 된다."""
    items = parse_feed(GOOGLE_SOURCE, STALE_FEED, NOW)
    assert [i.source_url for i in items] == ["https://example.com/new"]


PORTAL_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>한눈에 보는 오늘 : 방송/가요 - 도쿄 편집숍 - 네이트 뉴스</title>
<link>https://example.com/p1</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
<item><title>도쿄 하네다 노선 증편 - 여행신문</title>
<link>https://example.com/p2</link>
<pubDate>Wed, 02 Sep 2026 02:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_portal_redistribution_is_not_a_source():
    """네이트·다음은 기사를 쓴 곳이 아니라 옮긴 곳이다.
    서명에 '네이트 뉴스'가 찍히면 누가 취재했는지 알 수 없다."""
    items = parse_feed(GOOGLE_SOURCE, PORTAL_FEED, NOW)
    assert [i.source_name for i in items] == ["여행신문"]


def test_a_portal_index_page_is_not_an_article():
    items = parse_feed(GOOGLE_SOURCE, PORTAL_FEED, NOW)
    assert all("한눈에 보는" not in i.title for i in items)


# ── 종합 보도자료가 섞인 소스(industry: false) — TTL뉴스·문화뉴스·ㅍㅍㅅㅅ ──────────
# 2026-10-30 사장님: "여행 기사 더 만들어 … 여기 기사들 많은데 뭐하는거야? 좀 챙겨서 가지고와서
# 좀 올려". 지명으로만 가르던 것을 여행 말로 가른다.

def _feed(*rows):
    items = "".join(
        f"<item><title>{t}</title><link>https://example.com/{i}</link>"
        f"<description>{d}</description></item>" for i, (t, d) in enumerate(rows))
    return f'<?xml version="1.0"?><rss version="2.0"><channel>{items}</channel></rss>'


def test_업계면을_끈_소스는_여행_말_없는_보도자료를_버린다():
    """TTL뉴스는 종합 보도자료가 섞여 있다(2026-10-15 실측 37건 중 27건이 금융·교육청·식품)."""
    from dataclasses import replace
    xml = _feed(("하나금융 잡매칭 페스타 개막", "강소기업 20곳이 참여한다."),
                ("괌 노선 증편", "겨울 증편이다."))
    got = parse_feed(replace(AUTO_SOURCE, industry=False), xml, NOW)
    assert [i.region for i in got] == ["guam"]


def test_업계면을_끈_소스도_여행업계_말이_있으면_지명_없이_업계면으로_받는다():
    """지명이 없다고 통째로 버리니 진짜 여행업계 기사까지 사라져 TTL뉴스가 하루 1~6건만 남았다."""
    from dataclasses import replace
    xml = _feed(("하나투어, 겨울 패키지 3종 출시", "동남아 상품이다."),
                ("대한항공, 비즈니스 기내식 개편", "와인을 강화한다."),
                ("노랑풍선, 3분기 실적 발표", "매출이 늘었다."),
                ("신한투자증권, 크로스보더 펀드 결성", "벤처 투자다."),
                ("세종대, 하반기 취업반 모집", "3·4학년 대상."))
    got = parse_feed(replace(AUTO_SOURCE, industry=False), xml, NOW)
    assert [(i.title[:4], i.region) for i in got] == [
        ("하나투어", "industry"), ("대한항공", "industry"), ("노랑풍선", "industry")]
    assert all(i.channel == "travel" for i in got)


def test_업계면을_끈_소스는_지명만_있는_보도자료도_버린다():
    """2026-09~10 실측: TTL뉴스 발행 88건 중 27건이 "SK어스온, 베트남 광구서 첫 원유 생산" 같은
    증권·제약·지자체 교류 보도자료였다. 지명이 있어도 제목·요약에 여행 말이 없으면 여행 기사가 아니다."""
    from dataclasses import replace
    xml = _feed(("SK어스온, 베트남 15-1/05 광구서 첫 원유 생산", "추정 매장량 6000만 배럴."),
                ("포항시, 일본 치바시와 교류의향서 체결", "지자체 교류다."),
                ("베트남항공, 한국 노선 대거 증편", "7월부터다."),
                ("태국 왕실 바지선 행렬 개최", "방콕 짜오프라야강에서 관광객을 맞는다."))
    got = parse_feed(replace(AUTO_SOURCE, industry=False), xml, NOW)
    assert [(i.title[:4], i.region) for i in got] == [("베트남항", "vietnam"), ("태국 왕", "thailand")]


def test_여행_전문지는_그대로_전부_받는다():
    """industry 기본값(True)인 소스는 바뀐 것이 없다 — 지명 없는 기사도 업계면으로."""
    xml = _feed(("신한투자증권, 크로스보더 펀드 결성", "벤처 투자다."))
    assert [i.region for i in parse_feed(AUTO_SOURCE, xml, NOW)] == ["industry"]


CULTURE_SOURCE = Source(id="mhns", region="auto", section="news", name="문화뉴스", type="rss",
                        url="https://example.com/rss", lang="ko", enabled=True,
                        curated=True, industry=False, culture=True)


def test_문화_소스는_여행은_여행으로_문화_발표는_문화_채널로_가른다():
    """문화뉴스는 여행면과 영화·공연·전시·방송면이 한 피드로 온다."""
    xml = _feed(("담양 죽녹원에 빛 더한다…야간관광 확대", "야간 개장이다."),
                ("포시즌스 호텔 방콕, 현지 문화 체험 프로그램 확대", "가을 시즌."),
                ("가을 호캉스 패키지 총정리", "전국 호텔."),
                ("'라라랜드' 개봉 10주년 맞아 재개봉", "11월 극장."),
                ("국립현대미술관 특별전 개막", "11월까지 전시한다."),
                ("이세돌, KBS 새 예능 23일 첫 방송", "바둑 은퇴 후."),
                ("○○시, 하반기 일자리 박람회 개최", "구인 기업 50곳."),
                # 첫 실행(2026-10-30)에 문화로 들어왔던 것 — '수상'은 기본 부문(스타의 여행) 규칙의
                # 말이고 어느 보도자료에나 있다. 부문이 분명한 문화 말이 없으면 버린다.
                ("국립창원대, 동남권 CAM기술경진대회서 학생 4명 수상", "학생 4명이 상을 받았다."))
    got = parse_feed(CULTURE_SOURCE, xml, NOW)
    assert [(i.channel, i.region) for i in got] == [
        ("travel", "korea"), ("travel", "thailand"), ("travel", "industry"),
        ("ent", ""), ("ent", ""), ("ent", "")]
    # 부문은 비워 둔다 — 편집 단계가 공식 발표성 제목만 남기고 지면이 제목으로 부문을 정한다.
    assert all(i.category == "" for i in got if i.channel == "ent")


def test_문화_소스가_아니면_문화_발표도_버린다():
    """TTL뉴스에 영화 기사가 섞여 와도 문화면에 넣지 않는다 — 문화 매체가 아니다."""
    from dataclasses import replace
    xml = _feed(("'라라랜드' 개봉 10주년 맞아 재개봉", "11월 극장."))
    assert parse_feed(replace(AUTO_SOURCE, industry=False), xml, NOW) == []


def test_문화_채널로_보낸_기사는_편집_단계의_연예_필터를_그대로_지난다():
    """수집이 문화로 보낸 것이 편집에서 공식 발표성·가십 필터를 거쳐 발행 대상이 된다."""
    from src.edit import edit_items
    from src.guards.dup_guard import PublishedIndex
    xml = _feed(("'라라랜드' 개봉 10주년 맞아 재개봉", "11월 극장."),
                ("배우 ○○, 결혼식 사진 공개…영화 개봉 앞두고", "축하."))
    got = parse_feed(CULTURE_SOURCE, xml, NOW)
    assert len(got) == 2
    result = edit_items(got, PublishedIndex(set(), []), [], {"문화뉴스"})
    assert [i.title[:6] for i in result["publish"]] == ["'라라랜드'"]


def test_요약은_인용_한도_안에서_자른다():
    """두 문장이 200자를 넘으면 첫 문장만, 첫 문장이 넘으면 띄어쓰기에서 자르고 말줄임표.

    2026-10-30 첫 실행에서 문화뉴스 여행 기사 4건이 전부 '인용 한도 초과'로 폐기됐다 —
    가드가 버리기 전에 수집이 한도 안으로 맞춘다.
    """
    from src.guards.copyright_guard import MAX_SUMMARY_CHARS
    s1 = "울릉군이 동절기 주요 관광시설 여섯 곳을 무료로 개방한다고 밝혔다."
    s2 = "대상 시설은 " + "독도박물관과 " * 30 + "등이다."
    assert len(s1 + " " + s2) > MAX_SUMMARY_CHARS
    assert first_sentences(f"{s1} {s2}") == s1
    long_one = "경주시가 " + "천년고도 달빛 따라 걷는 " * 15 + "걷기대회를 연다."
    got = first_sentences(long_one)
    assert len(got) <= MAX_SUMMARY_CHARS and got.endswith("…") and not got.endswith(" …")
    # 짧은 두 문장은 그대로
    assert first_sentences("첫 문장이다. 둘째 문장이다. 셋째는 버린다.") == "첫 문장이다. 둘째 문장이다."


# ── region: auto 인 구글뉴스 검색 소스(2026-10-30 "왜 3군데만 봐 다른곳도 다 봐") ──────────
# ㅍㅍㅅㅅ와 종합지 site: 검색 피드는 지역이 고정돼 있지 않다. 그런데 검색 피드 공통의 제목 검증
# (mentions_region)이 "auto" 에는 지명 키워드가 없어 늘 거짓이었고, ㅍㅍㅅㅅ는 붙인 날부터 0건이었다.
GOOGLE_AUTO_SOURCE = Source(
    id="gn_yna", region="auto", section="news", name="연합뉴스 여행", type="rss",
    url="https://news.google.com/rss/search?q=site%3Ayna.co.kr%20%28%EC%97%AC%ED%96%89%29",
    lang="ko", enabled=True, industry=False)

GOOGLE_AUTO_FEED = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>오사카 여행에서 배운 것 - ㅍㅍㅅㅅ</title><link>https://example.com/a</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
<item><title>하나투어, 겨울 패키지 출시 - 연합뉴스</title><link>https://example.com/b</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
<item><title>신한투자증권, 크로스보더 펀드 결성 - 연합뉴스</title><link>https://example.com/c</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
<item><title>포항시, 일본 치바시와 교류의향서 체결 - 연합뉴스</title><link>https://example.com/d</link>
<pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
</channel></rss>"""


def test_auto_소스의_구글뉴스_검색은_기사마다_지역을_정한다():
    got = parse_feed(GOOGLE_AUTO_SOURCE, GOOGLE_AUTO_FEED, NOW)
    assert [(i.title[:4], i.region, i.source_name) for i in got] == [
        ("오사카 ", "japan", "ㅍㅍㅅㅅ"), ("하나투어", "industry", "연합뉴스")]


def test_auto_소스의_구글뉴스_검색도_여행_말_없는_보도자료는_버린다():
    """종합지를 site: 로 묶으면 금융·지자체 기사가 같이 온다. industry: false 규칙이 그대로 막는다."""
    got = parse_feed(GOOGLE_AUTO_SOURCE, GOOGLE_AUTO_FEED, NOW)
    assert all("증권" not in i.title and "교류의향서" not in i.title for i in got)


def test_지역이_고정된_구글뉴스_검색은_여전히_제목으로_지역을_검증한다():
    """auto 예외가 기존 목적지 피드의 검증을 풀어서는 안 된다."""
    items = parse_feed(GOOGLE_SOURCE, GOOGLE_FEED, NOW)
    assert [i.title[:3] for i in items] == ["오사카"]


def test_구글뉴스가_이름으로_돌려주는_연예_매체도_싣지_않는다():
    """2026-10-30 2주 실측: '스포츠동아' 24건·'bntnews' 40건이 도메인 표기를 비켜 들어왔다."""
    xml = """<?xml version="1.0"?><rss version="2.0"><channel>
    <item><title>배우 ○○, 도쿄 호텔서 포착 - 스포츠동아</title><link>https://example.com/s1</link>
    <pubDate>Wed, 02 Sep 2026 01:00:00 GMT</pubDate></item>
    <item><title>도쿄 하네다 노선 증편 - 여행신문</title><link>https://example.com/s2</link>
    <pubDate>Wed, 02 Sep 2026 02:00:00 GMT</pubDate></item></channel></rss>"""
    assert [i.source_name for i in parse_feed(GOOGLE_SOURCE, xml, NOW)] == ["여행신문"]
