"""우리 사진이 없는 지역에 자유 이용 풍경 사진을 들인다(2026-10-28)."""
import io

from PIL import Image

import tools.free_region_photos as frp


class _Resp:
    def __init__(self, data=None, content=b"", status_code=200):
        self._d, self.content, self.status_code, self.headers = data, content, status_code, {}

    def json(self):
        return self._d


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (20, 120, 200)).save(buf, "JPEG")
    return buf.getvalue()


class _Client:
    """위키데이터·공용 API 를 흉내 낸다. 도쿄는 CC BY-SA, 오사카는 저작권 있음.
    limited 만큼은 공용이 먼저 '요청 제한'으로 답한다(GitHub 러너에서 실제로 났다)."""
    def __init__(self, limited=0):
        self.limited = limited

    def get(self, url, params=None):
        p = params or {}
        if p.get("action") == "wbsearchentities":
            return _Resp({"search": [{"id": {"Tokyo": "Q1", "Osaka": "Q2"}.get(p["search"], "Q0")}]})
        if p.get("action") == "wbgetclaims":
            f = {"Q1": "Tokyo_tower.jpg", "Q2": "Osaka.jpg"}.get(p["entity"])
            return _Resp({"claims": {"P18": [{"mainsnak": {"datavalue": {"value": f}}}]}} if f else {})
        if p.get("action") == "query":
            if self.limited:
                self.limited -= 1
                return _Resp({"error": {"code": "ratelimited"}})
            pages, norm = {}, []
            for n, t in enumerate(p["titles"].split("|")):
                shown = t.replace("_", " ")
                if shown != t:
                    norm.append({"from": t, "to": shown})
                lic = "CC BY-SA 4.0" if "Tokyo" in t else "All rights reserved"
                pages[str(n)] = {"title": shown, "imageinfo": [{
                    "thumburl": "https://upload.wikimedia.org/x/960px-Tokyo.jpg",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:Tokyo.jpg",
                    "extmetadata": {"LicenseShortName": {"value": lic},
                                    "Artist": {"value": "<a>홍길동</a>"}}}]}
            return _Resp({"query": {"normalized": norm, "pages": pages}})
        return _Resp(content=_jpeg())


def test_only_free_licenses_come_in_with_credit(tmp_path, monkeypatch):
    monkeypatch.setattr(frp, "ROOT", str(tmp_path))
    monkeypatch.setattr(frp, "PLACES", {"japan": (("Tokyo", "도쿄", "tokyo"), ("Osaka", "오사카", "osaka"))})
    manifest = {}
    n = frp.fetch_region(_Client(), manifest, "japan", face_check=lambda img: False)
    assert n == 1
    e = manifest["japan"][0]
    assert e["free"] and e["place"] == "도쿄" and e["city"] == "tokyo" and e["license"] == "CC BY-SA 4.0" and e["artist"] == "홍길동"
    assert (tmp_path / e["file"]).exists()
    # 두 번 돌려도 다시 받지 않는다
    assert frp.fetch_region(_Client(), manifest, "japan", face_check=lambda img: False) == 0


def test_faces_keep_a_photo_out(tmp_path, monkeypatch):
    monkeypatch.setattr(frp, "ROOT", str(tmp_path))
    monkeypatch.setattr(frp, "PLACES", {"japan": (("Tokyo", "도쿄", "tokyo"),)})
    manifest = {}
    assert frp.fetch_region(_Client(), manifest, "japan", face_check=lambda img: True) == 0
    assert manifest["japan"] == []


def test_regions_with_enough_own_photos_are_left_alone():
    m = {"guam": [{"file": f"assets/photos/guam/{n}.webp"} for n in range(10)]}
    assert frp.own_count(m, "guam") >= frp.MIN_OWN
    assert frp.own_count({"japan": [{"file": "x", "free": True}]}, "japan") == 0


def test_rate_limit_is_retried_not_read_as_no_license(tmp_path, monkeypatch):
    """요청 제한 응답을 '자유 라이선스 아님'으로 읽어 82장을 버렸다(2026-10-28 첫 실행)."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(frp, "ROOT", str(tmp_path))
    monkeypatch.setattr(frp, "PLACES", {"japan": (("Tokyo", "도쿄", "tokyo"),)})
    manifest = {}
    assert frp.fetch_region(_Client(limited=2), manifest, "japan", face_check=lambda img: False) == 1
