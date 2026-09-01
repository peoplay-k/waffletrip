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
