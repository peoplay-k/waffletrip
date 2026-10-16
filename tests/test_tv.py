"""연예 '방송' 부문 (2026-10-16): 보도자료 재료 수집과 우리 카드."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import tv_material as tv  # noqa: E402
from src.models import Item, title_hash  # noqa: E402
from src.render.tv_cards import attach_tv_cards  # noqa: E402

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 10, 16, 9, 0, tzinfo=KST)


def test_예고의_방송일을_읽는다():
    assert "2026-10-16" in tv.air_dates("오늘(16일) 밤 10시 방송", NOW)
    assert "2026-10-16" in tv.air_dates("16일 방송되는 SBS 금요 예능", NOW)
    assert "2026-10-17" in tv.air_dates("(10월 17일 밤 9시 5분, EBS1)", NOW)
    assert "2026-10-17" in tv.air_dates("17일(토) 밤 9시", NOW)


def test_지난_방송_리뷰는_오늘_날짜가_없다():
    got = tv.air_dates("15일(목) 방송된 MBC '구해줘! 홈즈'는 시청률 1위", NOW)
    assert "2026-10-16" not in got and "2026-10-17" not in got


def test_보도자료_제목에서_프로그램을_뽑는다():
    assert tv.program_of("[SBS 골 때리는 그녀들] FC월드클라쓰 VS …") == "골 때리는 그녀들"
    assert tv.program_of("[구해줘! 홈즈]  양세찬X김대호") == "구해줘! 홈즈"
    assert tv.program_of("'제프 딘' 강연 방송") == ""


def test_편성표에서_띄어쓰기를_무시하고_찾는다():
    slots = [{"title": "해피투게더-혼자가 아니어서 좋아", "time": "2030", "channel": "KBS2"}]
    assert tv.find_slot("해피투게더 - 혼자가 아니어서 좋아", slots)["time"] == "2030"
    assert tv.find_slot("명의", slots) is None


def test_EBS_본문의_글자_조각을_붙인다():
    assert tv.plain("<p>정원 <span>619</span>명</p><p>둘째 문단</p>") == "정원 619명\n둘째 문단"


def _ent(item_id, category, photo=None):
    now = "2026-10-16T09:00:00+09:00"
    return Item(id=item_id, grade="C", region="", section="news", title="해피투게더 마지막 이야기",
                summary="요약", source_name="", source_url="", published_at=now,
                collected_at=now, status="published", title_hash=title_hash("x"),
                body_md="본문", photo=photo, channel="ent", category=category)


def test_방송_기사에만_우리_카드를_붙인다(tmp_path):
    tv_item, movie, has_photo = _ent("c-1", "tv"), _ent("c-2", "movie"), _ent("c-3", "tv", "/img/x.webp")
    made = attach_tv_cards([tv_item, movie, has_photo], str(tmp_path))
    if made == 0:                      # 한글 글꼴이 없는 환경 — 사진 없이 나가는 것이 맞다
        assert tv_item.photo is None
        return
    assert made == 1
    assert tv_item.photo == "/img/tv/c-1.jpg"
    assert (tmp_path / "img/tv/c-1.jpg").exists() and (tmp_path / "og/tv/c-1.jpg").exists()
    assert movie.photo is None and has_photo.photo == "/img/x.webp"
