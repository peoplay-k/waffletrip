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


def test_assign_never_reuses_even_when_short():
    """사진보다 기사가 많으면 사진 없이 낸다. 재사용이 우선순위보다 먼저 금지다.

    (예전에는 모자라면 돌려 썼다. 그 동작을 금지로 바꿨다.)
    """
    from src.photos import assign
    manifest = {"guam": [{"file": "assets/photos/guam/only.webp"}]}
    got = assign(manifest, "guam", ["a", "b", "c"])
    assert len(got) == 1
    assert list(got.values()) == ["/img/guam/only.webp"]


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


# ── 사진 재사용 금지 ──────────────────────────────────────────────
def _m(n, heroes=0):
    return {"guam": [{"file": f"assets/photos/guam/p{i}.webp",
                      **({"hero": True} if i < heroes else {})} for i in range(n)]}


def test_a_photo_is_never_given_to_a_second_article():
    """한 번 쓴 사진은 다시 쓰지 않는다. 같은 사진이 여러 기사에 반복되면
    유사문서로 처리돼 검색에서 손해를 보고 매체가 성의 없어 보인다."""
    from src.photos import assign
    used = {}
    first = assign(_m(3), "guam", ["a", "b"], used)
    second = assign(_m(3), "guam", ["c", "d"], used)
    assert set(first.values()) & set(second.values()) == set()


def test_running_out_means_no_photo_not_a_repeat():
    """사진이 모자라면 재사용하는 대신 사진 없이 낸다."""
    from src.photos import assign
    used = {}
    got = assign(_m(2), "guam", ["a", "b", "c", "d"], used)
    assert len(got) == 2
    assert len(set(got.values())) == 2
    assert "c" not in got and "d" not in got


def test_same_article_keeps_its_photo_across_builds():
    """빌드마다 사진이 바뀌면 어제 본 기사가 오늘 달라 보인다."""
    from src.photos import assign
    used = {}
    first = assign(_m(4), "guam", ["a", "b"], used)
    again = assign(_m(4), "guam", ["a", "b"], used)
    assert first == again


def test_new_article_gets_a_fresh_photo_not_an_old_one():
    from src.photos import assign
    used = {}
    assign(_m(4), "guam", ["a", "b"], used)
    later = assign(_m(4), "guam", ["a", "b", "c"], used)
    assert later["c"] not in (later["a"], later["b"])


def test_scenery_still_goes_first_among_unused():
    from src.photos import assign
    used = {}
    got = assign(_m(5, heroes=2), "guam", ["lead"], used)
    assert got["lead"] in ("/img/guam/p0.webp", "/img/guam/p1.webp")


def test_used_ledger_survives_a_round_trip(tmp_path):
    from src.photos import load_used, save_used
    path = str(tmp_path / "used.json")
    save_used({"/img/guam/a.webp": "article-1"}, path)
    assert load_used(path) == {"/img/guam/a.webp": "article-1"}


def test_broken_ledger_does_not_crash_the_build(tmp_path):
    from src.photos import load_used
    p = tmp_path / "used.json"
    p.write_text("{{{ 깨진", encoding="utf-8")
    assert load_used(str(p)) == {}


# ── 사진은 도시를 가려서 붙는다 ────────────────────────────────────────
# 2026-09-09 실측: 하노이 사진이 호치민 책방거리 기사에 붙었다.

class _It:
    def __init__(self, id, title, summary=""):
        self.id, self.title, self.summary = id, title, summary


def _vn_manifest():
    return {"vietnam": [
        {"file": "assets/photos/vietnam/hanoi1.webp", "city": "hanoi"},
        {"file": "assets/photos/vietnam/hanoi2.webp", "city": "hanoi"},
        {"file": "assets/photos/vietnam/halong.webp", "city": "halong"},
        {"file": "assets/photos/vietnam/generic.webp"},
    ]}


def test_도시_기사는_같은_도시_사진을_먼저_받는다():
    from src.photos import assign
    out = assign(_vn_manifest(), "vietnam", [_It("a", "하노이 구시가 카페거리")], {})
    assert out["a"] == "/img/vietnam/hanoi1.webp"


def test_다른_도시_사진은_절대_붙지_않는다():
    from src.photos import assign
    m = {"vietnam": [{"file": "assets/photos/vietnam/hanoi1.webp", "city": "hanoi"}]}
    out = assign(m, "vietnam", [_It("a", "호치민 책방거리 명소 5")], {})
    assert "a" not in out          # 차라리 사진 없이


def test_도시_기사는_태그_없는_사진은_받는다():
    from src.photos import assign
    m = {"vietnam": [{"file": "assets/photos/vietnam/hanoi1.webp", "city": "hanoi"},
                     {"file": "assets/photos/vietnam/generic.webp"}]}
    out = assign(m, "vietnam", [_It("a", "호치민 책방거리 명소 5")], {})
    assert out["a"] == "/img/vietnam/generic.webp"


def test_도시_없는_기사는_아무_사진이나_받는다():
    from src.photos import assign
    out = assign(_vn_manifest(), "vietnam", [_It("a", "베트남 항공권 15% 할인")], {})
    assert out["a"].startswith("/img/vietnam/")


def test_촬영지_낱말도_도시로_본다():
    from src.photos import assign
    out = assign(_vn_manifest(), "vietnam", [_It("a", "하롱베이 크루즈 요금 인상")], {})
    assert out["a"] == "/img/vietnam/halong.webp"


def test_잘못_붙어_있던_사진은_놓아준다():
    """이전 빌드에서 규칙 없이 붙은 사진은 유지하지 않는다."""
    from src.photos import assign
    used = {"/img/vietnam/hanoi1.webp": "a"}
    out = assign(_vn_manifest(), "vietnam", [_It("a", "호치민 책방거리 명소 5")], used)
    assert out["a"] == "/img/vietnam/generic.webp"
    assert "/img/vietnam/hanoi1.webp" not in used


def test_id_문자열도_예전처럼_된다():
    from src.photos import assign
    out = assign(_vn_manifest(), "vietnam", ["a", "b"], {})
    assert len(out) == 2


def test_캡션용_장소_이름():
    from src.photos import photo_places
    names = photo_places(_vn_manifest())
    assert names["/img/vietnam/hanoi1.webp"] == "하노이"
    assert names["/img/vietnam/halong.webp"] == "하롱베이"
    assert names["/img/vietnam/generic.webp"] == ""


# ── 공유 카드·치수 ─────────────────────────────────────────────────────

def test_og_path_maps_img_to_og_jpg():
    from src.photos import og_path
    assert og_path("/img/vietnam/x.webp") == "/og/vietnam/x.jpg"


def test_render_og_images_makes_1200x630_jpg(tmp_path, monkeypatch):
    from PIL import Image
    from src.photos import render_og_images, photo_dims
    src = tmp_path / "a.webp"; Image.new("RGB", (900, 900), (200, 50, 50)).save(src)
    manifest = {"guam": [{"file": str(src)}]}
    monkeypatch.setattr("src.photos.web_path", lambda f: "/img/guam/a.webp")
    out = tmp_path / "public"
    assert render_og_images(manifest, str(out), ["/img/guam/a.webp"]) == 1
    card = Image.open(out / "og" / "guam" / "a.jpg")
    assert card.size == (1200, 630)
    assert photo_dims(manifest, ["/img/guam/a.webp"])["/img/guam/a.webp"] == (900, 900)


def test_render_og_images_skips_unused_photos(tmp_path, monkeypatch):
    from PIL import Image
    from src.photos import render_og_images
    src = tmp_path / "a.webp"; Image.new("RGB", (300, 300)).save(src)
    monkeypatch.setattr("src.photos.web_path", lambda f: "/img/guam/a.webp")
    assert render_og_images({"guam": [{"file": str(src)}]}, str(tmp_path / "p"), []) == 0


def test_요약에만_나온_도시는_주제가_아니다():
    """제목이 나트랑이면 요약의 하노이로 하노이 사진을 붙이지 않는다."""
    from src.photos import assign, places_of
    it = _It("a", "주한 베트남관광청 \"한국인이 좋아하는 나트랑 관광 알려요\"",
             "하노이에서 열린 설명회에서 칸호아성 관광을 소개했다.")
    assert places_of(it) == {"nhatrang"}   # 제목이 나트랑을 말한다
    m = {"vietnam": [{"file": "assets/photos/vietnam/hanoi1.webp", "city": "hanoi"}]}
    assert "a" not in assign(m, "vietnam", [it], {})


def test_제목에_도시가_없으면_요약의_도시를_본다():
    from src.photos import places_of
    assert places_of(_It("a", "베트남 침대열차 요금 인하", "하노이-다낭 노선이 80만 동부터")) == {"hanoi", "danang"}


def test_영문_제목의_다른_나라_도시는_태그된_사진을_받지_못한다():
    """도쿄 신주쿠 기사에 다낭 사진이 붙었다. 다른 도시를 말하면 태그 사진은 안 준다."""
    from src.photos import assign, places_of
    it = _It("a", "World's 'most favorite destination' bans vacation rentals in Tokyo hotspot Shinjuku", "")
    assert "tokyo" in places_of(it)
    m = {"vietnam": [{"file": "assets/photos/vietnam/danang1.webp", "city": "danang"}]}
    assert "a" not in assign(m, "vietnam", [it], {})
    # 우리 도시를 영문으로 말하면 그 도시 사진은 받는다
    it2 = _It("b", "Da Nang beach named among Asia's best", "")
    assert places_of(it2) == {"danang"}
    assert assign(m, "vietnam", [it2], {}).get("b")


def test_지역_단위_촬영지도_캡션에_이름이_나온다():
    from src.photos import photo_places
    m = {"kota": [{"file": "assets/photos/kota/a.webp", "city": "kota"}],
         "jeju": [{"file": "assets/photos/jeju/b.webp", "city": "jeju"}],
         "vietnam": [{"file": "assets/photos/vietnam/c.webp", "city": "hue"}]}
    names = photo_places(m)
    assert names["/img/kota/a.webp"] == "코타키나발루"
    assert names["/img/jeju/b.webp"] == "제주"
    assert names["/img/vietnam/c.webp"] == "후에"


def test_하와이는_섬을_가린다():
    """카우아이 허리케인 기사에 오아후 사진을 붙이지 않는다."""
    from src.photos import assign, places_of
    it = _It("a", "Kauai County outlines critical safety plans as Hurricane Lowell nears", "")
    assert places_of(it) == {"kauai"}
    m = {"hawaii": [{"file": "assets/photos/hawaii/waikiki.webp", "city": "oahu"},
                    {"file": "assets/photos/hawaii/any.webp"}]}
    got = assign(m, "hawaii", [it], {})
    assert got.get("a") == "/img/hawaii/any.webp"          # 태그 없는 사진만
    assert places_of(_It("b", "와이키키 호텔 신축…호놀룰루 관광 회복", "")) == {"oahu"}


def test_영문_낱말은_단어_경계로_본다():
    from src.photos import places_of
    assert "bigisland" not in places_of(_It("a", "A philosophy of slow travel", ""))
    assert "bigisland" in places_of(_It("b", "Kona airport runway crack", ""))


def test_목록에_없는_낡은_기록도_규칙에_어긋나면_놓아준다():
    """태그를 고치거나 사진을 뺀 뒤 남은 기록이 사진을 영영 묶어두면 안 된다."""
    from src.photos import assign
    it = _It("a", "나트랑 해변 물놀이", "")
    m = {"vietnam": [{"file": "assets/photos/vietnam/nt.webp", "city": "nhatrang"}]}
    used = {"/img/vietnam/사라진사진.webp": "a", "/img/vietnam/dn.webp": "a"}
    got = assign(m, "vietnam", [it], used)
    assert got["a"] == "/img/vietnam/nt.webp"
    assert "/img/vietnam/사라진사진.webp" not in used and "/img/vietnam/dn.webp" not in used


def test_미케_해변은_다낭이다():
    from src.photos import places_of
    assert places_of(_It("a", "From Nha Trang to My Khe: best Vietnamese beaches", "")) == {"nhatrang", "danang"}


def test_번역이_지운_지명을_원제에서_읽는다():
    """태국 무비자 기사에 하노이 사진이 붙었다. 번역 제목엔 도시가 없었다."""
    from src.photos import assign, places_of
    it = _It("a", "태국, 60개국 무비자 체류기간 30일로 절반 단축", "")
    it.title_orig = "Southeast Asia's second most visited country shortens visa-free stays for 60 countries including Singapore"
    assert "singapore" in places_of(it)
    m = {"vietnam": [{"file": "assets/photos/vietnam/hanoi.webp", "city": "hanoi"}]}
    assert "a" not in assign(m, "vietnam", [it], {})


def test_우리말_나라이름도_읽는다():
    from src.photos import places_of
    assert "thailand_kr" in places_of(_It("a", "태국 무비자 30일로 단축", ""))
    assert not places_of(_It("c", "일본 관광객 증가", ""))   # 나라는 도시가 아니다
    assert "danang" in places_of(_It("b", "다낭 신규 호텔 개장", ""))
