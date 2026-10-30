"""사장님이 편집실에서 구조를 바꾸면 지면이 그대로 따라오나 — 다른 프로세스로 사이트를 만들어 본다.

모듈들이 import 할 때 config/site.json 을 읽으므로, 바꾼 설정으로 새 파이썬을 띄워 본다(2026-10-30).
"""
import json
import os
import subprocess
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "site.json")


def _edited_config(tmp_path):
    cfg = json.load(open(FIXTURE, encoding="utf-8"))
    cfg["culture_sections"][0]["name"] = "시네마"                       # 이름 바꾸기
    cfg["travel_sections"].append({"id": "cruise", "name": "크루즈", "desc": "배 여행", "visible": True})
    cfg["travel_sections"] = [s for s in cfg["travel_sections"] if s["id"] != "data"] + \
        [{**next(s for s in cfg["travel_sections"] if s["id"] == "data"), "visible": False}]   # 숨기기
    cfg["regions"].insert(0, {"id": "philippines", "name": "필리핀", "keywords": ["필리핀", "세부"],
                              "desk_duty": "필리핀 기사를 맡습니다.", "visible": True})       # 새 지역, 맨 앞
    for r in cfg["regions"]:
        if r["id"] == "laos":
            r["visible"] = False                                         # 지역 숨기기
    cfg["reporters"].append({"name": "박새봄", "beats": ["philippines"]})
    cfg["home"].update({"hero_count": 2, "order": ["latest", "culture", "travel", "culture_sections"],
                        "pinned_lead": "c-pin", "show_photo_row": False})
    path = tmp_path / "site.json"
    path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return path


def test_site_follows_the_owner_edits(tmp_path):
    cfg_path = _edited_config(tmp_path)
    out = tmp_path / "out"
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {ROOT!r})
        from src.models import Item, title_hash
        from src.render.site import render_site
        def it(i, title, region="guam", channel="travel", category="", topic="", photo=None, when="2026-10-29T09:00:00+09:00"):
            return Item(id=i, grade="C", region=region, section="news", title=title, summary="요약",
                        source_name="", source_url="", published_at=when, collected_at=when,
                        status="published", title_hash=title_hash(title), body_md="본문 문단.",
                        channel=channel, category=category, topic=topic, photo=photo)
        items = [it("c-pin", "고정 머리기사", when="2026-10-20T09:00:00+09:00"),
                 it("c-ph", "세부 새 리조트", region="philippines"),
                 it("c-cr", "크루즈 신항로", topic="cruise"),
                 it("c-mv", "영화 ○○ 개봉", region="", channel="ent", category="movie")]
        render_site(items, {str(out)!r}, "2026-10-30")
    """)
    env = {**os.environ, "SITE_CONFIG": str(cfg_path)}
    r = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    home = (out / "index.html").read_text(encoding="utf-8")
    nav = home.split('class="gnb"', 1)[1].split("</nav>", 1)[0]
    assert "시네마" in nav and "크루즈" in nav                       # 이름·새 부문이 메뉴에
    assert 'href="/data/"' not in nav                               # 숨긴 부문은 메뉴에서 빠진다
    lead = home.split('class="lead-box"', 1)[1].split("</section>", 1)[0]
    assert "고정 머리기사" in lead                                    # 고정한 머리기사
    assert home.index("최신 기사") < home.index('class="block-title"><a href="/ent/">') \
        if "최신 기사" in home and 'class="block-title"><a href="/ent/">' in home else True
    assert (out / "philippines" / "index.html").exists()             # 새 지역면
    assert "박새봄 기자" in (out / "philippines" / "index.html").read_text(encoding="utf-8")
    assert (out / "cruise" / "index.html").exists()
    assert "크루즈 신항로" in (out / "cruise" / "index.html").read_text(encoding="utf-8")
    assert (out / "laos" / "index.html").exists()                    # 숨겨도 옛 주소는 산다
    side = home.split('class="col-side"', 1)[1]
    assert 'href="/laos/"' not in side                               # 길잡이에서는 빠진다
    assert 'class="block photo-row"' not in home                     # 포토 줄 끔
