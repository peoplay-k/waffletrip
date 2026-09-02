"""사진 연결. 승인을 통과한 것만 사이트에 나가야 한다."""
from __future__ import annotations

import json

import pytest

from src.photos import copy_into, load_manifest, photos_for, pick, web_path


def _manifest(tmp_path, data):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_web_path_maps_assets_to_public_url():
    assert web_path("assets/photos/guam/a.webp") == "/img/guam/a.webp"


def test_missing_manifest_is_not_an_error(tmp_path):
    """사진이 없다고 신문이 안 나가면 안 된다."""
    assert load_manifest(str(tmp_path / "없음.json")) == {}


def test_broken_manifest_is_not_an_error(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{{{ 깨진 json", encoding="utf-8")
    assert load_manifest(str(path)) == {}


def test_manifest_that_is_a_list_is_rejected(tmp_path):
    """모양이 틀리면 조용히 이상하게 해석되지 않고 빈 것으로 본다."""
    assert load_manifest(_manifest(tmp_path, ["a"])) == {}


def test_photos_for_skips_entries_without_a_file():
    manifest = {"guam": [{"file": "assets/photos/guam/a.webp"}, {"src": "x"}, "쓰레기"]}
    assert photos_for(manifest, "guam") == ["/img/guam/a.webp"]


def test_region_without_photos_returns_empty():
    assert photos_for({"guam": []}, "hawaii") == []
    assert pick({}, "guam", "seed") == ""


def test_pick_is_stable_for_the_same_article():
    """빌드할 때마다 사진이 바뀌면 '어제 본 기사'가 오늘 달라 보인다."""
    manifest = {"guam": [{"file": f"assets/photos/guam/{c}.webp"} for c in "abcde"]}
    first = pick(manifest, "guam", "article-123")
    assert first == pick(manifest, "guam", "article-123")
    assert first in [f"/img/guam/{c}.webp" for c in "abcde"]


def test_pick_spreads_across_articles():
    manifest = {"guam": [{"file": f"assets/photos/guam/{c}.webp"} for c in "abcde"]}
    chosen = {pick(manifest, "guam", f"id-{i}") for i in range(30)}
    assert len(chosen) > 1


def test_copy_into_only_copies_files_that_exist(tmp_path, monkeypatch):
    import src.photos as photos
    src_dir = tmp_path / "assets" / "photos" / "guam"
    src_dir.mkdir(parents=True)
    (src_dir / "real.webp").write_bytes(b"webp")
    monkeypatch.chdir(tmp_path)
    manifest = {"guam": [{"file": "assets/photos/guam/real.webp"},
                         {"file": "assets/photos/guam/없는파일.webp"}]}
    (tmp_path / "assets" / "photos" / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    out = tmp_path / "public"
    assert copy_into(str(out)) == 1
    assert (out / "img" / "guam" / "real.webp").exists()


def test_assign_does_not_repeat_within_a_region():
    """톱기사와 카드에 같은 사진이 걸리면 지면이 성의 없어 보인다."""
    from src.photos import assign
    manifest = {"guam": [{"file": f"assets/photos/guam/{c}.webp"} for c in "abcde"]}
    got = assign(manifest, "guam", [f"id-{i}" for i in range(5)])
    assert len(set(got.values())) == 5


def test_assign_is_stable_for_the_same_input():
    from src.photos import assign
    manifest = {"guam": [{"file": f"assets/photos/guam/{c}.webp"} for c in "abcde"]}
    seeds = ["a1", "b2", "c3"]
    assert assign(manifest, "guam", seeds) == assign(manifest, "guam", seeds)


def test_assign_reuses_when_articles_outnumber_photos():
    """사진보다 기사가 많아도 배정이 비지 않아야 한다."""
    from src.photos import assign
    manifest = {"guam": [{"file": "assets/photos/guam/only.webp"}]}
    got = assign(manifest, "guam", ["a", "b", "c"])
    assert len(got) == 3 and set(got.values()) == {"/img/guam/only.webp"}


def test_assign_without_photos_returns_empty():
    from src.photos import assign
    assert assign({}, "guam", ["a"]) == {}


def test_hero_photos_come_first():
    """1면 사진이 매체의 인상을 결정한다.

    해시로만 고르면 음식 클로즈업이 톱기사에 걸린다 — 실제로 양념치킨이
    여행신문 1면에 올라갔다. 풍경으로 표시한 사진을 먼저 쓴다.
    """
    from src.photos import photos_for
    manifest = {"guam": [
        {"file": "assets/photos/guam/food.webp"},
        {"file": "assets/photos/guam/beach.webp", "hero": True},
    ]}
    assert photos_for(manifest, "guam")[0] == "/img/guam/beach.webp"


def test_lead_article_gets_the_hero_photo():
    from src.photos import assign
    manifest = {"guam": [
        {"file": "assets/photos/guam/food.webp"},
        {"file": "assets/photos/guam/beach.webp", "hero": True},
    ]}
    got = assign(manifest, "guam", ["lead", "second"])
    assert got["lead"] == "/img/guam/beach.webp"
    assert got["second"] == "/img/guam/food.webp"


def test_without_hero_flags_nothing_breaks():
    from src.photos import assign, photos_for
    manifest = {"guam": [{"file": f"assets/photos/guam/{c}.webp"} for c in "abc"]}
    assert len(photos_for(manifest, "guam")) == 3
    assert len(set(assign(manifest, "guam", ["a", "b", "c"]).values())) == 3


def test_first_three_slots_get_scenery():
    """첫 화면은 톱과 사이드 둘이다. 거기에 음식 클로즈업이 걸리면
    여행신문으로 보이지 않는다."""
    from src.photos import assign
    manifest = {"guam": [
        {"file": "assets/photos/guam/food1.webp"},
        {"file": "assets/photos/guam/food2.webp"},
        {"file": "assets/photos/guam/beach1.webp", "hero": True},
        {"file": "assets/photos/guam/beach2.webp", "hero": True},
        {"file": "assets/photos/guam/beach3.webp", "hero": True},
    ]}
    got = assign(manifest, "guam", ["a", "b", "c", "d", "e"])
    first_three = [got["a"], got["b"], got["c"]]
    assert all("beach" in p for p in first_three), first_three
    assert len(set(got.values())) == 5


def test_fewer_heroes_than_slots_still_works():
    from src.photos import assign
    manifest = {"guam": [
        {"file": "assets/photos/guam/beach.webp", "hero": True},
        {"file": "assets/photos/guam/food.webp"},
    ]}
    got = assign(manifest, "guam", ["a", "b"])
    assert got["a"] == "/img/guam/beach.webp"
    assert got["b"] == "/img/guam/food.webp"
