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


def test_예고편은_공식채널_날짜_프로그램이_다_맞아야_붙는다():
    ok = {"id": "NTk5p8RJJ6k", "title": "［22회 예고］말 바꾸려고 [사랑이 온다] | KBS 방송",
          "channel_id": "UChpjIaEgwtDZtmWEkzFulSA", "age_days": 1}
    fan = {**ok, "channel_id": "UCxxxxxxxxxxxxxxxxxxxxxx"}
    old = {**ok, "title": "［21회 예고］저 이혼 안 할 거예요 [사랑이 온다]"}
    assert tv.pick_preview([fan, old, ok], "주말드라마 사랑이 온다", "2026-10-17", "22")["id"] == ok["id"]
    assert tv.pick_preview([fan, old], "주말드라마 사랑이 온다", "2026-10-17", "22") is None


def test_제목에_프로그램명이_없으면_설명으로_확인한다():
    v = {"id": "DUeob9d4_y8", "title": "[10월 18일 예고] 김승수×송종호, 러브라인",
         "channel_id": "UCmjNKt6kITwaZTqvWuaSPLg", "age_days": 1}
    assert tv.pick_preview([v], "미운 우리 새끼", "2026-10-18", "") is None
    assert tv.pick_preview([v], "미운 우리 새끼", "2026-10-18", "",
                           confirm=lambda vid, key: key == "미운우리새끼")["id"] == v["id"]


def test_편성표_머리말을_뗀다():
    assert tv.core_name("주말드라마 사랑이 온다") == "사랑이 온다"
    assert tv.core_name("일일드라마 욕망의 덫") == "욕망의 덫"
    assert tv.core_name("미운 우리 새끼") == "미운 우리 새끼"


def test_출연자_후보는_제목_출연줄_편성표에서_뽑는다():
    item = {"title": "[SBS 비서진] 이서진, 지석진 연기에 돌직구", "program": "비서진",
            "text": "출연: 김광규, 지예은\n본문"}
    slots = [{"title": "비서진", "actors": "이서진,김광규", "time": "2310", "channel": "SBS"}]
    names = tv.cast_names(item, slots)
    assert names[:2] == ["이서진", "지석진"] and "김광규" in names and "지예은" in names
