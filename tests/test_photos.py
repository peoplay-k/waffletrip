"""사진 연결. 승인을 통과한 것만 사이트에 나가야 한다."""
from __future__ import annotations

import json
import os

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


def test_고른_번호는_시트_목록_없이는_굽지_않는다(tmp_path, monkeypatch):
    """번호는 폴더 순서일 뿐이라 파일이 하나만 늘어도 통째로 밀린다.

    2026-09-10 실측: 코타 폴더가 굽는 사이 190 → 261 장이 됐고 고른 번호가
    편의점 진열대와 인물 사진을 가리켰다. 지면에 나갈 뻔했다.
    """
    import subprocess
    import sys

    import pytest
    from PIL import Image

    # 사진 도구는 얼굴 검사에 opencv 를 쓴다. CI 에는 깔지 않는다 — 사진은
    # 사람이 눈으로 보고 고르는 로컬 작업이라 클라우드에서 돌 일이 없다.
    pytest.importorskip("cv2")
    src = tmp_path / "a.jpg"
    Image.new("RGB", (200, 200)).save(src)
    out = subprocess.run(
        [sys.executable, "tools/photo_prepare.py", "--region", "guam",
         "--from", str(tmp_path), "--approve", "1", "--commit"],
        capture_output=True, text=True)
    assert out.returncode == 2
    assert "--sheet" in out.stderr


def test_신문_사진은_NAS_에서만_온다():
    """사장님 폰 사진(바탕화면 사진_정리완료)은 개인 블로그용이다. 신문 금지.

    2026-09-09 에 폰 사진 323장이 공개 사이트에 올라갔다가 사장님 지적으로
    전부 내렸다. 사람이 기억으로 막을 일이 아니라 여기서 막는다.
    """
    import json
    with open("assets/photos/manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)
    entries = [e for rows in manifest.values() for e in rows]
    assert entries, "매니페스트가 비었다"

    금지 = ("사진_정리완료", "stage_japan", "stage_taiwan", "Desktop/사진")
    for e in entries:
        src = e.get("src", "")
        for 말 in 금지:
            assert 말 not in src, f"폰 사진이 섞였다: {src}"
        # 출처를 밝히지 않은 사진은 두지 않는다. 나중에 감사할 수 없다.
        assert e.get("origin"), f"출처 표시가 없다: {src}"
        assert "NAS" in e["origin"] or "과미" in e["origin"], (src, e["origin"])


def test_허용되지_않은_폴더는_출처를_못_만든다():
    """도구가 출처를 스스로 판정한다. 목록에 없는 폴더면 None 이라 굽지 못한다.

    2026-09-14 까지는 `origin` 을 사람이 손으로 적었고, 굽는 도구는 그 칸을
    아예 만들지 않았다. 위의 매니페스트 검사는 **이미 지면에 나간 뒤**에야
    깨진다. 막는 자리를 굽기 전으로 옮긴다.
    """
    prepare = pytest.importorskip("tools.photo_prepare")

    NAS = "/Volumes/GUAMPLAY/네이버 블로그/#DSLR"
    assert prepare.origin_of(f"{NAS}/#괌/기타/풍경(낮)/a.jpg") == "NAS #DSLR/#괌"
    assert prepare.origin_of(f"{NAS}/#하노이/b.JPG") == "NAS #DSLR/#하노이"

    # 사장님 폰 사진. 그럴듯한 이름이어도 출처가 안 나온다 → 굽기가 멈춘다
    assert prepare.origin_of(os.path.expanduser("~/Desktop/사진_정리완료/제주/c.jpg")) is None
    assert prepare.origin_of("/tmp/nas_stage/d.jpg") is None
    assert prepare.origin_of("/tmp/stage_japan/e.jpg") is None


def test_한_지면에서_같은_장면이_연달아_붙지_않는다():
    """연사 사진이 위에서부터 나란히 깔리면 한 장짜리 신문처럼 보인다.

    2026-09-14 사이판면 실측: 네 기사가 `KakaoTalk_20250411_134734529` 의
    _01~_04 를 받았다. 파일은 다르지만 같은 해변을 같은 빛에 찍은 것이라
    독자 눈에는 같은 사진이다. 53장을 갖고 있었는데도 그랬다 — 배정이
    매니페스트 순서를 그대로 따라갔기 때문이다.
    """
    from src.models import Item
    from src.photos import assign, scene_of

    assert scene_of("assets/photos/saipan/A_134734529_03.webp") == "A_134734529"
    assert scene_of("/x/B_99_hi.webp") == "B"

    # 연사 4장이 앞에, 다른 장면 3장이 뒤에 있는 목록
    burst = [f"burst_20250411_01", "burst_20250411_02",
             "burst_20250411_03", "burst_20250411_04"]
    others = ["beach", "market", "sunset"]
    manifest = {"saipan": [{"file": f"assets/photos/saipan/{n}.webp",
                            "hero": True} for n in burst + others]}
    items = [Item(id=f"a{i}", grade="B", region="saipan", section="news",
                  title=f"사이판 소식 {i}", summary="", source_name="",
                  source_url="", published_at="", collected_at="",
                  status="published", title_hash=f"h{i}")
             for i in range(4)]

    got = assign(manifest, "saipan", items)
    scenes = [scene_of(p) for p in got.values()]
    assert len(got) == 4, got
    assert len(set(scenes)) == 4, f"같은 장면이 겹쳤다: {scenes}"


def test_한_지면은_장소를_돌아가며_쓴다():
    """같은 장소 사진이 여럿 있어도 지면에서는 한 바퀴 돌고 다시 온다.

    NAS 가 이미 장면별로 정리돼 있다 — `사이판 남부투어_마운트카멜 성당`,
    `_슈가 덕`, `_래더 비치`. 연번(PEO_1946·1950)으로는 남남이지만 폴더를
    보면 같은 성당이다. 2026-09-14 실측: 사이판면 일곱 자리 중 다섯 자리가
    그 성당이었다. 래더 비치 16장과 서프 클럽 12장은 한 번도 안 나갔다.

    장면(연사)과 달리 **장소는 피할 뿐 막지 않는다.** 다른 폴더가 동나면
    사진을 비우느니 같은 성당의 다른 컷을 싣는다.
    """
    from src.models import Item
    from src.photos import assign

    def entry(folder, name):
        return {"file": f"assets/photos/saipan/{name}.webp",
                "src": f"/Volumes/GUAMPLAY/네이버 블로그/#DSLR/#사이판/{folder}/{name}.JPG"}

    manifest = {"saipan": [entry("성당", f"PEO_1{n}") for n in range(940, 948)]
                          + [entry("래더비치", f"PEO_2{n}") for n in range(77, 80)]
                          + [entry("슈가덕", f"PEO_3{n}") for n in range(10, 13)]}
    items = [Item(id=f"a{i}", grade="B", region="saipan", section="news",
                  title=f"사이판 소식 {i}", summary="", source_name="",
                  source_url="", published_at="", collected_at="",
                  status="published", title_hash=f"h{i}")
             for i in range(3)]

    got = assign(manifest, "saipan", items)
    folders = [p.split("/")[-1][:5] for p in got.values()]   # PEO_1 / PEO_2 / PEO_3
    assert len(got) == 3, got
    assert len(set(folders)) == 3, f"한 장소만 썼다: {folders}"


def test_긁어온_후보_이미지는_NAS_안에_있어도_못_쓴다():
    """`#대만` 8,679장은 우리 사진이 아니라 검색 결과를 받아둔 것이다.

    2026-09-14 실측: 대만·라오스·일본 폴더의 이미지가 전부
    `_STI_OUT/…/clusters/…/candidates/` 안에 있었고, 옆의
    `candidate_manifest.json` 의 `image_url` 이 `lookaside.fbsbx.com`·
    `encrypted-tbn0.gstatic.com` 이었다. 다른 블로그 파이프라인이 시안을
    고르려고 구글·페이스북에서 받아둔 **남의 사진**이다.

    폴더 수만 보면 "일본 지면에도 사진을 줄 수 있겠다"고 착각하기 쉽다.
    편집원칙이 "직접 찍은 것만 쓴다"고 적혀 있으므로 경로에서 막는다.
    """
    prepare = pytest.importorskip("tools.photo_prepare")
    NAS = "/Volumes/GUAMPLAY/네이버 블로그/#DSLR"

    나쁨 = (f"{NAS}/#대만/기타/사용사진/여행스타일링/260903_대만 지우펀/"
            "_STI_OUT/20260901_181126/clusters/shilin_night_market/candidates/q1-005.jpg")
    assert prepare.origin_of(나쁨) is None

    # 같은 NAS 의 우리 촬영본은 그대로 통과해야 한다
    좋음 = f"{NAS}/#괌/액티비티/괌 남부 택시투어/솔레다드 요새/PEO_3153.JPG"
    assert prepare.origin_of(좋음) == "NAS #DSLR/#괌"


def test_큰_폴더는_나눠_돌릴_수_있다(tmp_path):
    """1,658장을 한 번에 검사하면 세 시간이 걸린다.

    400장씩 나눠 돌리려면 "앞 400장 다음"을 가리킬 수 있어야 한다.
    정렬이 고정이라 같은 폴더면 같은 순서가 나오고, 건너뛴 만큼이 곧
    다음 묶음이다 — 겹치거나 빠지는 장이 있으면 안 된다.
    """
    prepare = pytest.importorskip("tools.photo_prepare")

    for i in range(10):
        (tmp_path / f"p{i:02d}.jpg").write_bytes(b"x")
    앞 = prepare.gather(str(tmp_path), 4, 0)
    뒤 = prepare.gather(str(tmp_path), 4, 4)
    끝 = prepare.gather(str(tmp_path), 0, 8)

    assert len(앞) == 4 and len(뒤) == 4 and len(끝) == 2
    assert not set(앞) & set(뒤), "겹치면 같은 사진을 두 번 본다"
    assert len(set(앞) | set(뒤) | set(끝)) == 10, "빠지는 장이 있으면 안 된다"
