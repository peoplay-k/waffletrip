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
