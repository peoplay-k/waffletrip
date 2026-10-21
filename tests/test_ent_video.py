"""연예 '오늘의 방송' 영상 대본 (2026-10-16)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import make_ent_video as v  # noqa: E402

BODY = ("> **방송 정보**\n> 채널 · KBS2 | 프로그램 · 욕망의 덫 | 회차 · 39회\n"
        "> 방송 · 2026년 10월 16일(금) 오후 7시 50분\n\n본문")


def test_방송_정보_상자를_읽는다():
    info = v.info_of({"body_md": BODY})
    assert info == {"channel": "KBS2", "program": "욕망의 덫", "episode": "39회",
                    "when": "오후 7시 50분", "sort": 1950, "day": "10/16"}


def test_밤_시각은_저녁으로_센다():
    body = BODY.replace("오후 7시 50분", "밤 11시 10분")
    assert v.info_of({"body_md": body})["sort"] == 2310


def test_나레이션은_우리_요약만_읽고_시각을_두_번_읽지_않는다():
    item = {"title": "'욕망의 덫' 39회", "body_md": BODY, "info": v.info_of({"body_md": BODY}),
            "summary": "KBS2 '욕망의 덫' 39회가 16일 밤 7시 50분 방송된다. 은설이 알아챈다. 셋째 문장."}
    scenes = v.script_long([item, item], "2026-10-16")
    story = scenes[1]["narration"]
    assert story == "KBS2 욕망의 덫 39회가 16일 밤 7시 50분 방송된다. 은설이 알아챈다."
    assert scenes[0]["kind"] == "open" and scenes[-1]["kind"] == "close"


def test_유튜브_설명에_AI_음성임을_밝힌다():
    item = {"title": "t", "info": v.info_of({"body_md": BODY})}
    meta = v.youtube_meta([item], "2026-10-16")
    assert "AI 음성" in meta["description"] and meta["title"].startswith("[오늘의 방송] 10/16")


def test_기사_본문의_자유_이용_사진을_읽는다():
    body = BODY + "\n\n![김혜윤 · 사진 TV10 · CC BY 4.0 · 위키미디어 공용](https://upload.wikimedia.org/a/b.jpg)\n\n![x](https://evil.example/c.jpg)"
    assert v.photos_of({"body_md": body}) == [
        {"caption": "김혜윤 · 사진 TV10 · CC BY 4.0 · 위키미디어 공용",
         "url": "https://upload.wikimedia.org/a/b.jpg"}]
