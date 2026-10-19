#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""와플트립 유튜브 업로드용 refresh token 을 받는다 — 사장님 맥에서 한 번만 실행.

    python3 tools/youtube_auth.py

1. Google Cloud 콘솔에서 만든 OAuth 클라이언트(데스크톱 앱)의 ID·비밀값을 묻는다(화면에 안 보임)
2. 브라우저가 열리면 **@waffletrip 채널을 가진 구글 계정**으로 로그인해 허용한다
3. 받은 토큰으로 채널 핸들을 확인하고, GitHub Secrets 에 넣을 세 값을 출력한다

출력된 값은 GitHub → peoplay-k/waffletrip → Settings → Secrets and variables → Actions 에만
넣는다. 채팅·저장소·메신저에 붙여넣지 않는다. 표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import getpass
import http.server
import json
import secrets
import socket
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

SCOPES = ("https://www.googleapis.com/auth/youtube.upload "
          "https://www.googleapis.com/auth/youtube.readonly")
WANT = "@waffletrip"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    cid = input("OAuth 클라이언트 ID: ").strip()
    sec = getpass.getpass("OAuth 클라이언트 보안 비밀(입력해도 화면에 안 보임): ").strip()
    if not cid or not sec:
        print("둘 다 필요하다.")
        return 1
    port = _free_port()
    redirect = f"http://127.0.0.1:{port}/"
    state = secrets.token_urlsafe(16)
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("인증을 받았습니다. 이 창을 닫고 터미널로 돌아가세요.".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPES,
        "access_type": "offline", "prompt": "consent", "state": state})
    print("\n브라우저에서 @waffletrip 채널 계정으로 로그인해 허용하세요. 안 열리면 아래 주소를 직접 여세요:\n" + url)
    webbrowser.open(url)
    while "code" not in got and "error" not in got:
        threading.Event().wait(0.5)
    srv.server_close()
    if got.get("state") != state or "code" not in got:
        print(f"인증 실패: {got.get('error', 'state 불일치')}")
        return 1

    body = urllib.parse.urlencode({"code": got["code"], "client_id": cid, "client_secret": sec,
                                   "redirect_uri": redirect, "grant_type": "authorization_code"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", data=body, timeout=60) as r:
        tok = json.load(r)
    refresh = tok.get("refresh_token")
    if not refresh:
        print("refresh token 이 오지 않았다. 구글 계정 보안 설정에서 이 앱 권한을 지우고 다시 실행하세요.")
        return 1

    req = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                                 headers={"Authorization": f"Bearer {tok['access_token']}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.load(r).get("items") or []
    handle = (items[0]["snippet"].get("customUrl") if items else "") or "(채널 없음)"
    print(f"\n로그인한 채널: {handle}")
    if handle.lower().lstrip("@") != WANT.lstrip("@"):
        print(f"⚠ {WANT} 가 아니다. 이 토큰으로는 발행기가 아무것도 올리지 않는다. 다른 계정으로 다시 실행하세요.")
        return 1
    print("\nGitHub Secrets 에 아래 세 값을 넣으세요(이름 = 값):\n")
    print(f"  WAFFLETRIP_YT_CLIENT_ID     = {cid}")
    print(f"  WAFFLETRIP_YT_CLIENT_SECRET = (방금 입력한 보안 비밀)")
    print(f"  WAFFLETRIP_YT_REFRESH_TOKEN = {refresh}")
    print("\n넣고 나면 다음 매일 발행부터 쇼츠가 올라갑니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
