"""자동 생성 데이터 기사. 지어내지 않는 것이 이 모듈의 전제다."""
from __future__ import annotations

from src.autowrite import build_daily
from src.models import Item, title_hash

DAY = "2026-09-02"


def fact(region, summary):
    return Item(id=f"a-{region}", grade="A", region=region, section="data",
                title="오늘의 값", summary=summary, source_name="날씨",
                source_url="", published_at=DAY, collected_at=DAY,
                status="published", title_hash=title_hash(summary))


WEATHER = fact("guam", "2026-09-02 하갓냐 뇌우, 최고 31°C · 최저 25°C · 강수확률 100%")
FX = fact("guam", "2026-09-02 기준 1 USD = 약 1,377원")


def test_no_material_means_no_article():
    """데이터가 없으면 기사를 만들지 않는다. 빈 기사를 내보내면 안 된다."""
    assert build_daily([], DAY) is None
    ordinary = Item(id="b", grade="B", region="guam", section="news", title="남의 기사",
                    summary="요약", source_name="타사", source_url="",
                    published_at=DAY, collected_at=DAY, status="published",
                    title_hash=title_hash("남의 기사"))
    assert build_daily([ordinary], DAY) is None


def test_weather_becomes_a_table(tmp_path):
    art = build_daily([WEATHER], DAY, str(tmp_path))
    assert "| 괌 | 31°C | 25°C | 뇌우 | 100% |" in art.body_md
    assert "## 오늘의 날씨" in art.body_md


def test_exchange_rate_becomes_a_table(tmp_path):
    art = build_daily([FX], DAY, str(tmp_path))
    assert "| 괌 | 1 USD | 1,377원 |" in art.body_md


def test_headline_uses_a_real_number(tmp_path):
    """제목의 숫자는 실제 수집값이어야 한다."""
    art = build_daily([WEATHER], DAY, str(tmp_path))
    assert "괌 31°C" in art.title
    assert art.title.startswith("09월 2일") or "9월 2일" in art.title


def test_article_says_it_is_compiled_not_written(tmp_path):
    """사람이 쓴 해설로 오인되면 안 된다."""
    art = build_daily([WEATHER, FX], DAY, str(tmp_path))
    assert "데이터 정리 기사" in art.body_md
    assert "직접 수집한" in art.body_md


def test_byline_is_the_data_desk(tmp_path):
    from src.desks import DATA_DESK
    assert build_daily([WEATHER], DAY, str(tmp_path)).source_name == DATA_DESK


def test_is_graded_as_our_own_writing(tmp_path):
    """자체 생산이므로 C등급이다. 큐레이션으로 섞이면 안 된다."""
    assert build_daily([WEATHER], DAY, str(tmp_path)).grade == "C"


def test_comparison_paragraph_is_omitted_without_history(tmp_path):
    """이력이 없으면 비교 문단을 아예 쓰지 않는다 — 없는 비교를 지어내지 않는다."""
    art = build_daily([FX], DAY, str(tmp_path))
    assert "어제와 비교" not in art.body_md


def test_same_day_produces_the_same_id(tmp_path):
    a = build_daily([WEATHER], DAY, str(tmp_path))
    b = build_daily([WEATHER], DAY, str(tmp_path))
    assert a.id == b.id


# ── 주간 지역 브리핑 ──────────────────────────────────────────────
def curated(region, title, day="2026-09-01", outlet="여행신문"):
    return Item(id=f"b-{title}", grade="B", region=region, section="news",
                title=title, summary=f"{title} 요약", source_name=outlet,
                source_url="https://example.com/a", published_at=day,
                collected_at=day, status="published", title_hash=title_hash(title))


def test_roundup_needs_enough_material():
    """두 건짜리 '브리핑'은 브리핑이 아니다."""
    from src.autowrite import build_roundup
    assert build_roundup([curated("guam", "가")], "guam", DAY) is None
    two = [curated("guam", "가"), curated("guam", "나")]
    assert build_roundup(two, "guam", DAY) is None


def test_roundup_is_built_from_three_or_more():
    from src.autowrite import build_roundup
    items = [curated("hawaii", f"소식 {i}") for i in range(4)]
    art = build_roundup(items, "hawaii", DAY)
    assert art is not None
    assert "이번 주 하와이" in art.title
    assert art.grade == "C"


def test_roundup_credits_every_outlet():
    """남의 보도를 묶는 것이므로 출처를 빠짐없이 밝힌다."""
    from src.autowrite import build_roundup
    items = [curated("jeju", "가", outlet="제주의소리"),
             curated("jeju", "나", outlet="제주일보"),
             curated("jeju", "다", outlet="TTL뉴스")]
    art = build_roundup(items, "jeju", DAY)
    for outlet in ("제주의소리", "제주일보", "TTL뉴스"):
        assert outlet in art.body_md


def test_roundup_ignores_other_regions_and_our_own_articles():
    from src.autowrite import build_roundup
    items = [curated("guam", f"괌 {i}") for i in range(3)]
    items += [curated("hawaii", f"하와이 {i}") for i in range(5)]
    art = build_roundup(items, "guam", DAY)
    assert "하와이" not in art.body_md.replace("하와이 지역면", "")


def test_roundup_skips_stale_items():
    """지난 이레만 본다. 한 달 전 소식이 '이번 주'로 나가면 안 된다."""
    from src.autowrite import build_roundup
    old = [curated("guam", f"옛 {i}", day="2026-07-01") for i in range(5)]
    assert build_roundup(old, "guam", "2026-09-02") is None


def _b(item_id, title, region, published, summary="한 줄 요약입니다."):
    return Item(id=item_id, grade="B", region=region, section="news",
                title=title, summary=summary, source_name="여행신문",
                source_url="https://example.com/" + item_id,
                published_at=published, collected_at=published,
                status="published", title_hash=item_id)


def test_city_roundup_groups_by_city_not_region():
    """도쿄 기사만 모은다. 같은 일본이어도 오사카 기사는 도쿄 브리핑에 안 들어간다."""
    from src.autowrite import build_city_roundup
    recent = [
        _b("c1", "도쿄 하네다 노선 증편", "japan", "2026-09-02T00:00:00+09:00"),
        _b("c2", "나리타 신규 취항", "japan", "2026-09-01T00:00:00+09:00"),
        _b("c3", "도쿄 호텔 개장", "japan", "2026-08-31T00:00:00+09:00"),
        _b("c4", "오사카 간사이 노선 확대", "japan", "2026-09-02T00:00:00+09:00"),
    ]
    art = build_city_roundup(recent, "tokyo", "2026-09-03")
    assert art is not None
    assert art.title == "이번 주 도쿄에서 나온 소식 3건"
    assert art.grade == "C" and art.region == "japan"
    assert "오사카 간사이" not in art.body_md
    assert "/city/tokyo/" in art.body_md


def test_city_roundup_needs_three_items():
    from src.autowrite import build_city_roundup
    recent = [_b("c1", "도쿄 노선 증편", "japan", "2026-09-02T00:00:00+09:00")]
    assert build_city_roundup(recent, "tokyo", "2026-09-03") is None


def test_city_roundup_ignores_unknown_city():
    from src.autowrite import build_city_roundup
    assert build_city_roundup([], "atlantis", "2026-09-03") is None


def test_region_roundup_still_works():
    from src.autowrite import build_roundup
    recent = [_b(f"r{n}", f"괌 소식 {n}", "guam", "2026-09-02T00:00:00+09:00")
              for n in range(3)]
    art = build_roundup(recent, "guam", "2026-09-03")
    assert art and art.title == "이번 주 괌에서 나온 소식 3건"
    assert "/guam/" in art.body_md
