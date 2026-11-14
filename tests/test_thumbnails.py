"""유튜브 표지(썸네일) — 크기·용량·발행기 연결."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

from PIL import Image  # noqa: E402

import publish_youtube as yt  # noqa: E402
import thumbnails as th  # noqa: E402


def test_short_cover_is_vertical_and_fits_youtube_limit(tmp_path):
    img = th.short_cover("괌", 4, "괌 정부관광청, 겨울 성수기 맞아 직항 늘린다", None, 38)
    assert img.size == (1080, 1920)
    path = th.save_jpg(img, str(tmp_path / "s-thumb.jpg"))
    assert os.path.getsize(path) <= 2_000_000


def test_long_and_ent_thumbs_are_16_9(tmp_path):
    long = th.long_thumb(["괌", "사이판", "하와이"], 9, [])
    assert long.size == (1280, 720)
    photo = Image.new("RGB", (800, 1000), (120, 140, 160))
    ent = th.ent_thumb("11월 14일", ["나 혼자 산다", "런닝맨"], 2, photo, credit="사진: 홍길동 · CC BY-SA 4.0")
    assert ent.size == (1280, 720)
    plain = th.ent_thumb("11월 14일", ["나 혼자 산다", "런닝맨"], 2)
    assert plain.size == (1280, 720)


def test_thumb_url_sits_next_to_video():
    assert yt.thumb_url("https://waffletrip.com/video/peopleroad-week.mp4") == \
        "https://waffletrip.com/video/peopleroad-week-thumb.jpg"


def test_set_thumbnail_skips_unknown_uploads():
    assert yt.set_thumbnail("t", "unknown", {"url": "https://x/v.mp4"}) is False
    assert yt.set_thumbnail("t", "", {"url": "https://x/v.mp4"}) is False


def test_short_hook_only_trims_never_rewrites():
    assert th.short_hook("노랑풍선, 괌정부관광청과 공동 프로모션…내년 3월 출발까지") == "노랑풍선, 괌정부관광청과 공동 프로모션"
    assert th.short_hook("호이안 '등불 축제' 12월") == "호이안 등불 축제 12월"


def test_photo_history_puts_recent_photos_last(tmp_path):
    import photo_history as ph
    path = str(tmp_path / "latest.json")
    ph.write_latest({"stem": "x"}, path)
    ph.remember(["a.jpg", "b.jpg"], path)
    assert ph.fresh_first(["a.jpg", "b.jpg", "c.jpg"], path)[0] == "c.jpg"
    # 다른 칸을 새로 써도 기록은 남는다
    ph.write_latest({"stem": "y"}, path)
    assert set(ph.history(path)) == {"a.jpg", "b.jpg"}


def test_short_cover_has_three_layouts():
    imgs = [th.short_cover("괌", 4, "괌 소식…덧붙임", None, variant=v) for v in range(3)]
    assert len({im.tobytes() for im in imgs}) == 3


def test_motion_starts_at_cover_size():
    import make_shorts as ms
    f = ms.motion(0, 3.0)
    assert "zoompan" in f and "min(1+" in f and f"s={ms.W}x{ms.H}" in f


def test_bgm_is_stereo_soft_and_varies_by_seed():
    import bgm
    a, b = bgm.synth(6, seed=1), bgm.synth(6, seed=2)
    assert a.shape[1] == 2 and abs(a).max() <= 0.81
    assert a.shape == b.shape and not (a == b).all()


def test_seed_of_is_stable():
    import editing
    assert editing.seed_of("peopleroad-guam-20261115-voiced.mp4") == editing.seed_of("peopleroad-guam-20261115-voiced.mp4")
