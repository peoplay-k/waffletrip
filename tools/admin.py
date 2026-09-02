#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""와플트립 편집실 — 이 맥에서 도는 글쓰기 화면.

    python3 tools/admin.py        →  http://localhost:8080

계정이 하나도 필요 없다. Decap CMS 는 GitHub OAuth 앱과 중개 서버가 있어야
하고 Node 도 필요한데, 이 맥에는 Node 가 없다. 그래서 같은 일을 파이썬
기본 라이브러리만으로 한다.

하는 일
  · 초안 목록 (작성중 / 발행대기 / 발행됨)
  · 새 기사 만들기
  · 제목·지역·부문·요약·필자·상태·본문 편집
  · 저장하면 content/review/*.md 에 그대로 쓴다

사진은 여기서 올리지 않는다. CMS 업로드는 얼굴 검사(person_scan)를
건너뛰기 때문이다. 사진은 tools/photo_prepare.py 로만 들여온다.
"""
from __future__ import annotations

import html
import http.server
import os
import re
import socketserver
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(ROOT, "content/review")
KST = timezone(timedelta(hours=9))
PORT = 8080

REGIONS = [("guam", "괌"), ("saipan", "사이판"), ("hawaii", "하와이"),
           ("vietnam", "베트남"), ("kota", "코타키나발루"),
           ("laos", "라오스"), ("jeju", "제주")]
SECTIONS = [("news", "일반 소식·해설"), ("flight", "항공·노선"),
            ("data", "데이터·통계"), ("promo", "안내")]
STATUSES = [("draft", "작성중 — 지면에 안 나감"),
            ("approved", "발행대기 — 다음 발행 때 나감"),
            ("published", "발행됨")]

CSS = """
:root{--ink:#0E0E0F;--muted:#6E6E73;--line:#EAEAE7;--coral:#F04E37;--paper:#FAFAF9}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--ink);font-size:15px;line-height:1.6;
 font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
 letter-spacing:-.015em}
.wrap{max-width:900px;margin:0 auto;padding:0 24px}
header{border-bottom:2px solid var(--ink);margin-bottom:26px}
header .wrap{display:flex;align-items:baseline;justify-content:space-between;
 padding:22px 24px 16px;flex-wrap:wrap;gap:12px}
h1{font-size:26px;font-weight:800;letter-spacing:-.05em;margin:0}
h1 span{color:var(--coral)}
.sub{font-size:13px;color:var(--muted)}
a{color:inherit;text-decoration:none}
a:hover{color:var(--coral)}
.btn{display:inline-block;background:var(--ink);color:#fff;padding:9px 16px;
 border:none;border-radius:3px;font:inherit;font-weight:700;font-size:14px;cursor:pointer}
.btn.ghost{background:#fff;color:var(--ink);border:1px solid var(--line)}
.btn:hover{opacity:.86}
table{width:100%;border-collapse:collapse;font-size:14.5px}
th{text-align:left;font-size:11.5px;letter-spacing:.08em;color:var(--muted);
 padding:0 0 9px;border-bottom:1px solid var(--line);font-weight:700}
td{padding:13px 0;border-bottom:1px solid var(--line);vertical-align:top}
td.t{font-weight:600}
.pill{display:inline-block;font-size:11px;font-weight:700;padding:2px 8px;border-radius:3px}
.s-draft{background:#F3F3F1;color:#6E6E73}
.s-approved{background:#FFF0EC;color:var(--coral)}
.s-published{background:#EAF5EE;color:#2F6B45}
form.edit{margin:0 0 40px}
label{display:block;font-size:12.5px;font-weight:700;margin:20px 0 6px}
label .hint{display:block;font-weight:400;color:var(--muted);font-size:12px;margin-top:3px}
input[type=text],select,textarea{width:100%;padding:11px 13px;font:inherit;font-size:15px;
 border:1px solid var(--line);border-radius:3px;background:#fff;color:var(--ink)}
input:focus,select:focus,textarea:focus{outline:2px solid var(--coral);outline-offset:-1px;border-color:transparent}
textarea{min-height:460px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
 font-size:14px;line-height:1.7}
.row{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}
.bar{position:sticky;bottom:0;background:#fff;border-top:1px solid var(--line);
 padding:16px 0;margin-top:24px;display:flex;gap:10px;align-items:center}
.note{font-size:12.5px;color:var(--muted);margin:6px 0 0}
.flash{background:#EAF5EE;border-left:3px solid #2F6B45;padding:12px 16px;margin:0 0 22px;font-size:14px}
.empty{color:var(--muted);padding:40px 0}
"""


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · 와플트립 편집실</title><style>{CSS}</style></head><body>
<header><div class="wrap">
  <h1><a href="/">와플트립 편집실<span>.</span></a></h1>
  <div class="sub">이 맥에서만 도는 화면입니다</div>
</div></header>
<div class="wrap">{body}</div></body></html>""".encode("utf-8")


def read(path: str) -> tuple[dict, str]:
    raw = open(path, encoding="utf-8").read()
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return (yaml.safe_load(parts[1]) or {}), parts[2].lstrip("\n")
    return {}, raw


def write(path: str, front: dict, body: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n\n" + body.replace("\r\n", "\n").strip() + "\n")


def drafts() -> list[dict]:
    if not os.path.isdir(REVIEW):
        return []
    out = []
    for name in sorted(os.listdir(REVIEW), reverse=True):
        if not name.endswith(".md"):
            continue
        try:
            front, _ = read(os.path.join(REVIEW, name))
        except Exception:
            continue
        out.append({"file": name, **front})
    order = {"approved": 0, "draft": 1, "published": 2}
    return sorted(out, key=lambda d: (order.get(d.get("status"), 9), d["file"]))


def sel(name: str, opts, cur: str) -> str:
    o = "".join(
        f'<option value="{html.escape(v)}"{" selected" if v == cur else ""}>'
        f'{html.escape(lb)}</option>' for v, lb in opts)
    return f'<select name="{name}">{o}</select>'


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, content: bytes, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _redirect(self, to: str) -> None:
        self.send_response(303)
        self.send_header("Location", to)
        self.end_headers()

    def log_message(self, *a):  # 조용히
        pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)

        if u.path == "/":
            rows = drafts()
            flash = ('<div class="flash">저장했습니다. 발행대기로 두면 다음 '
                     '발행 때 지면에 나갑니다.</div>') if "saved" in q else ""
            if not rows:
                body = flash + '<p class="empty">아직 초안이 없습니다.</p>'
            else:
                trs = ""
                for d in rows:
                    st = d.get("status", "draft")
                    label = dict((v, l.split(" —")[0]) for v, l in STATUSES).get(st, st)
                    rg = dict(REGIONS).get(d.get("region"), d.get("region", "-"))
                    trs += (f'<tr><td><span class="pill s-{st}">{html.escape(label)}</span></td>'
                            f'<td>{html.escape(rg)}</td>'
                            f'<td class="t"><a href="/edit?f={urllib.parse.quote(d["file"])}">'
                            f'{html.escape(str(d.get("title") or d["file"]))}</a></td></tr>')
                body = (flash +
                        '<table><tr><th style="width:92px">상태</th>'
                        '<th style="width:110px">지역면</th><th>제목</th></tr>'
                        + trs + "</table>")
            body += ('<div class="bar"><a class="btn" href="/new">새 기사 쓰기</a>'
                     '<span class="note">사진은 여기서 올리지 않습니다 — '
                     'photo_prepare.py 의 얼굴 검사를 거쳐야 합니다.</span></div>')
            return self._send(page("기사 목록", body))

        if u.path == "/new":
            body = f"""<form class="edit" method="post" action="/create">
<label>제목<span class="hint">지면에 그대로 나갑니다.</span>
<input type="text" name="title" required autofocus></label>
<div class="row">
<label>지역면{sel("region", REGIONS, "guam")}</label>
<label>부문{sel("section", SECTIONS, "news")}</label>
</div>
<div class="bar"><button class="btn" type="submit">만들기</button>
<a class="btn ghost" href="/">취소</a></div></form>"""
            return self._send(page("새 기사", body))

        if u.path == "/edit":
            name = (q.get("f") or [""])[0]
            path = os.path.join(REVIEW, os.path.basename(name))
            if not os.path.isfile(path):
                return self._send(page("없음", '<p class="empty">그런 초안이 없습니다.</p>'), 404)
            front, body_md = read(path)
            body = f"""<form class="edit" method="post" action="/save">
<input type="hidden" name="file" value="{html.escape(name)}">
<label>제목<input type="text" name="title" value="{html.escape(str(front.get('title','')))}" required></label>
<div class="row">
<label>지역면{sel("region", REGIONS, front.get("region",""))}</label>
<label>부문{sel("section", SECTIONS, front.get("section","news"))}</label>
</div>
<label>요약<span class="hint">목록·검색·카톡 공유 카드에 나옵니다. 한두 문장.</span>
<input type="text" name="summary" value="{html.escape(str(front.get('summary') or ''))}"></label>
<div class="row">
<label>필자<span class="hint">비우면 지역 데스크가 붙습니다. 실제로 쓴 사람만 적습니다.</span>
<input type="text" name="source_name" value="{html.escape(str(front.get('source_name') or ''))}"></label>
<label>원문 링크<span class="hint">다른 매체 보도를 정리한 경우에만.</span>
<input type="text" name="source_url" value="{html.escape(str(front.get('source_url') or ''))}"></label>
</div>
<label>상태{sel("status", STATUSES, front.get("status","draft"))}</label>
<label>본문<span class="hint">표를 적극적으로 씁니다. 공개하는 가격은 소비자가와 실제 결제가뿐입니다.</span>
<textarea name="body">{html.escape(body_md)}</textarea></label>
<div class="bar"><button class="btn" type="submit">저장</button>
<a class="btn ghost" href="/">목록</a>
<span class="note">{html.escape(name)}</span></div></form>"""
            return self._send(page(str(front.get("title") or "편집"), body))

        return self._send(page("없음", '<p class="empty">없는 쪽입니다.</p>'), 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
        g = lambda k: (form.get(k) or [""])[0]
        u = urllib.parse.urlparse(self.path)

        if u.path == "/create":
            day = datetime.now(KST).date().isoformat()
            title = g("title").strip()
            slug = re.sub(r"[^\w가-힣\s-]", "", title).strip()
            slug = re.sub(r"\s+", "-", slug)[:40].strip("-") or "article"
            name = f"{day.replace('-', '')}_{slug}.md"
            os.makedirs(REVIEW, exist_ok=True)
            path = os.path.join(REVIEW, name)
            if not os.path.exists(path):
                write(path, {"id": f"art-{g('region')}-{day.replace('-', '')}",
                             "region": g("region"), "section": g("section"),
                             "title": title, "source_name": "", "source_url": "",
                             "summary": "", "status": "draft"},
                      "## 무엇을 확인했나\n\n\n\n## 실측\n\n| 항목 | 값 | 확인일 |\n|---|---|---|\n|  |  |  |\n\n## 정리\n")
            return self._redirect(f"/edit?f={urllib.parse.quote(name)}")

        if u.path == "/save":
            name = os.path.basename(g("file"))
            path = os.path.join(REVIEW, name)
            if not os.path.isfile(path):
                return self._redirect("/")
            front, _ = read(path)
            front.update({"region": g("region"), "section": g("section"),
                          "title": g("title"), "summary": g("summary"),
                          "source_name": g("source_name"),
                          "source_url": g("source_url"), "status": g("status")})
            write(path, front, g("body"))
            return self._redirect("/?saved=1")

        return self._redirect("/")


def main() -> int:
    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"  편집실  http://localhost:{PORT}")
        print("  (Ctrl+C 로 종료)\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  종료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
