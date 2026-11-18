"""해설 기사 본문을 HTML 로 바꾼다.

**이스케이프를 먼저 하고 구조를 나중에 넣는다.** 순서를 뒤집으면 본문에 들어온
`<script>` 가 살아난다. 해설 기사는 우리가 쓰지만, 인용문이 남의 텍스트일 수 있고
초안 파일은 사람이 손으로 고치는 파일이라 신뢰 경계 밖으로 본다.

markdown 패키지를 쓰지 않는 이유: 의존성을 늘리지 않으려는 것이고, 지원 문법을
좁게 고정해 두는 편이 이스케이프 순서를 지키기 쉽다.
"""
from __future__ import annotations

import html
import re

_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE = re.compile(r"`([^`]+)`")
_HEAD = re.compile(r"^(#{2,4})\s+(.*)$")
_LIST = re.compile(r"^([-*·]|\d+\.)\s+")
# 한 줄 전체가 사진일 때만 사진으로 본다. 캡션 자리에 출처를 쓴다 — "사진: KBS 1TV".
# 방송사 공식 유튜브 예고편(2026-10-17). 영상 id 는 11자 고정 문자만 받는다.
_YOUTUBE = re.compile(r"^@youtube\s+([\w-]{11})$")
_IMAGE = re.compile(r"^!\[([^\]]*)\]\((https://[^)\s]+)\)$")
# 여행 카툰 컷(2026-11-18 사장님: "이미지 4장 이상, 스토리 있게"). 우리가 그린 카툰 그림
# (/img/cartoon/ 아래 파일 하나)만 받는다. 남의 주소·상위 폴더(..)는 받지 않고 줄째 버린다.
_PANEL = re.compile(r"^@panel\s+(/img/cartoon/[A-Za-z0-9_-]+\.webp)(?:\s+(.{1,200}))?$")
# 지도(2026-11-16 사장님: "관련된 곳 지도 첨부 필수"). 본문 어디에 써도 기사 끝에 모아 붙인다.
_MAP = re.compile(r"^@map\s+(.{2,80})$")
_BARE_URL = re.compile(r"https?://[^\s<>\"']+")
# 기사 끝 'AI 로 썼다' 안내 — 작은 글씨로(2026-11-16 사장님)
_AI_NOTE = re.compile(r"AI\s*(?:로|가|를|와)?\s*.{0,30}(?:그렸|작성|썼|만들|생성)")
# 문장 끝. 소수점(3.5)·약어 안의 점은 뒤에 빈칸이 없어 걸리지 않는다.
_SENT_END = re.compile(r"(?<=[.!?…])\s+(?=[^\s])")


def _safe_href(url: str) -> str:
    """http/https 만 링크로 만든다. javascript: 스킴을 막는 것과 같은 이유다."""
    return url if url.lower().startswith(("http://", "https://", "/")) else ""


def _inline(text: str) -> str:
    out = html.escape(text, quote=True)          # ← 반드시 먼저
    keep: list[str] = []                          # 만든 링크는 맨 끝에 되돌린다(주소 자동 링크와 겹치지 않게)

    def stash(a: str) -> str:
        keep.append(a)
        return f"\x00{len(keep) - 1}\x00"

    def link(m):
        href = _safe_href(html.unescape(m.group(2)))
        label = m.group(1)
        if not href:
            return label
        # 링크 글자가 주소 그대로면 '바로가기'로 바꾼다 — 주소는 지면에 드러내지 않는다
        # (2026-11-16 사장님: "링크 삽입하고 링크 주소는 지워").
        if _BARE_URL.fullmatch(html.unescape(label)):
            label = "바로가기"
        # 우리 쪽 링크에는 nofollow·새 창을 붙이지 않는다. nofollow 는 남의
        # 사이트로 신뢰를 넘기지 않으려는 표시인데 우리 쪽에 붙이면 우리
        # 지면끼리 연결이 검색엔진에 전달되지 않는다. 새 창도 같은 사이트
        # 안에서는 성가시기만 하다.
        if href.startswith("/"):
            return stash('<a href="%s">%s</a>' % (html.escape(href, quote=True), label))
        return stash('<a href="%s" rel="nofollow noopener" target="_blank">%s</a>' % (
            html.escape(href, quote=True), label))

    def bare(m):
        url = m.group(0).rstrip(".,)")
        tail = m.group(0)[len(url):]
        href = _safe_href(html.unescape(url))
        if not href:
            return m.group(0)
        return stash('<a class="go" href="%s" rel="nofollow noopener" target="_blank">바로가기</a>'
                     % html.escape(href, quote=True)) + tail

    out = _LINK.sub(link, out)
    out = _BARE_URL.sub(bare, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _CODE.sub(r"<code>\1</code>", out)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], out)


def maps_of(src: str) -> list[str]:
    """본문의 `@map 장소` 줄. 기사 끝 지도에 쓴다."""
    return [m.group(1).strip() for m in (_MAP.match(l.strip()) for l in (src or "").split("\n")) if m]


def _para(buf: list[str]) -> str:
    """문단 — 한 문장 한 줄. 폰에서 긴 문단이 한 덩어리로 보이지 않게 문장마다 줄을 바꾼다
    (2026-11-16 사장님: "호흡을 짧게, 문단이 안 보인다")."""
    text = " ".join(buf)
    sents = [x for x in _SENT_END.split(text) if x.strip()]
    inner = "<br>".join(_inline(x) for x in sents)
    if _AI_NOTE.search(text) and len(text) < 120:
        return '<p class="ai-note">%s</p>' % inner
    return "<p>%s</p>" % inner


_CREDIT_END = re.compile(r"^이 기사는 .*(?:정리|작성)했다\.?$")


def strip_credits(src: str) -> str:
    """기사 끝 `**출처**` 단락과 '이 기사는 … 피플로드가 정리했다' 줄을 지면에서 뺀다.

    2026-10-21 사장님: "출처 같은 거 다 지우고". 이미 나간 기사에도 같이 적용되도록
    그리는 단계에서 뺀다. 원문 주소는 초안 파일에 남는다(분쟁이 생기면 근거로 쓴다).
    """
    out, skipping = [], False
    for line in src.split("\n"):
        s = line.strip()
        if s.startswith("**출처**"):
            skipping = True
            continue
        if skipping and s:
            continue                      # 출처 단락이 이어지는 줄
        skipping = False
        if _CREDIT_END.match(s):
            continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)


def render(src: str) -> str:
    """지원 문법: 소제목(##~####) · 문단 · 목록 · 표 · 인용 · 구분선 · 사진(한 줄) · 카툰 컷(@panel)."""
    if not src:
        return ""
    lines = strip_credits(src).split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue

        if set(stripped) == {"-"} and len(stripped) >= 3:
            out.append("<hr>")
            i += 1
            continue

        # 방송사 보도용 스틸(2026-10-16 사장님: 출처를 밝혀 쓴다). https 만 받는다.
        # 남의 서버에 걸린 사진이라 리퍼러를 보내지 않는다 — 핫링크 차단을 덜 맞고,
        # 독자가 어느 기사에서 왔는지 남의 서버에 넘기지 않는다.
        if _MAP.match(stripped):          # 지도는 기사 끝에 모아 붙인다(템플릿)
            i += 1
            continue

        yt = _YOUTUBE.match(stripped)
        if yt:
            # nocookie 도메인 — 독자가 재생하기 전에는 유튜브가 쿠키를 심지 않는다.
            out.append('<div class="yt"><iframe src="https://www.youtube-nocookie.com/embed/%s" '
                       'title="방송사 공식 예고 영상" loading="lazy" allowfullscreen '
                       'referrerpolicy="strict-origin-when-cross-origin" '
                       'allow="encrypted-media; picture-in-picture"></iframe></div>' % yt.group(1))
            i += 1
            continue

        if stripped.startswith("@panel"):
            panel = _PANEL.match(stripped)
            if panel:
                out.append('<figure class="panel"><img src="%s" alt="%s" loading="lazy" '
                           'decoding="async"></figure>'
                           % (html.escape(panel.group(1), quote=True),
                              html.escape(panel.group(2) or "", quote=True)))
            i += 1
            continue

        image = _IMAGE.match(stripped)
        if image:
            cap = html.escape(image.group(1), quote=True)
            out.append('<figure class="still"><img src="%s" alt="%s" loading="lazy" '
                       'referrerpolicy="no-referrer"><figcaption>%s</figcaption></figure>'
                       % (html.escape(image.group(2), quote=True), cap, cap))
            i += 1
            continue

        head = _HEAD.match(stripped)
        if head:
            level = min(len(head.group(1)), 4)
            out.append("<h%d>%s</h%d>" % (level, _inline(head.group(2)), level))
            i += 1
            continue

        # 표 — 실측값을 싣는 기사의 핵심 포맷이라 지원한다.
        if "|" in stripped and i + 1 < len(lines) and re.match(
                r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]
            header = cells(stripped)
            i += 2
            body = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                body.append(cells(lines[i]))
                i += 1
            parts = ['<div class="tw"><table><thead><tr>']
            parts += ["<th>%s</th>" % _inline(c) for c in header]
            parts.append("</tr></thead><tbody>")
            for row in body:
                parts.append("<tr>%s</tr>" % "".join(
                    "<td>%s</td>" % _inline(c) for c in row))
            parts.append("</tbody></table></div>")
            out.append("".join(parts))
            continue

        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            # 줄을 살린다 — 방송 기사의 '방송 정보' 상자가 여러 줄 인용이다(2026-10-16).
            out.append("<blockquote>%s</blockquote>" % "<br>".join(_inline(b) for b in buf))
            continue

        if _LIST.match(stripped):
            tag = "ol" if re.match(r"^\d+\.", stripped) else "ul"
            buf = []
            while i < len(lines) and _LIST.match(lines[i].strip()):
                buf.append(_LIST.sub("", lines[i].strip()))
                i += 1
            out.append('<%s class="%s">%s</%s>' % (
                tag, "nlist" if tag == "ol" else "slist",
                "".join("<li>%s</li>" % _inline(b) for b in buf), tag))
            continue

        buf = []
        while (i < len(lines) and lines[i].strip()
               and not _HEAD.match(lines[i].strip())
               and not _LIST.match(lines[i].strip())
               and not lines[i].strip().startswith(">")
               and "|" not in lines[i]):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(_para(buf))
        else:
            out.append(_para([stripped]))
            i += 1
    return "\n".join(out)



def summary_lines(summary: str, n: int = 3) -> list[str]:
    """요약을 세 줄로 — 문장마다 한 줄. 한두 문장뿐이면 쉼표에서 나눠 세 줄을 채운다."""
    text = re.sub(r"\s+", " ", (summary or "").strip())
    if not text:
        return []
    lines = [x.strip() for x in _SENT_END.split(text) if x.strip()]
    while len(lines) < n:
        # 긴 줄부터 쉼표·'~고'·'~며'·'~에서' 자리에서 나눠 본다. 나눈 토막이 너무 짧으면 다음 줄로.
        for k in sorted(range(len(lines)), key=lambda k: -len(lines[k])):
            parts = re.split(r"(?<=,)\s+|(?<=[고며])\s+(?=\S{2,})|(?<=에서)\s+(?=\S{2,})",
                             lines[k], maxsplit=1)
            if len(parts) == 2 and min(len(p) for p in parts) >= 10:
                lines[k:k + 1] = [parts[0].rstrip(","), parts[1]]
                break
        else:
            break
    return lines[:n] if len(lines) <= n else lines[:n - 1] + [" ".join(lines[n - 1:])]


# 형광펜은 '얼마나'를 말하는 숫자에만 — 날짜(월·일·년)까지 칠하면 줄이 얼룩덜룩해진다
_NUM = re.compile(r"(?<![\w.])(\d[\d,.]*\s?(?:%p|%|만\s?원|억\s?원|만|억|천|원|명|건|곳|배|개국|개|달러|바트|엔|km|㎞|위)(?![가-힣]{0,0}\d))")


def highlight(line: str) -> str:
    """세 줄 요약 한 줄 — 숫자는 형광펜, 따옴표 속 이름은 굵게."""
    out = html.escape(line, quote=False)          # 글 안이라 따옴표는 그대로 둬도 안전하다
    out = re.sub(r"('[^'<>]{1,30}'|‘[^’<>]{1,30}’|\"[^\"<>]{1,40}\"|“[^”<>]{1,40}”)",
                 r"<b>\1</b>", out)
    out = _NUM.sub(r"<mark>\1</mark>", out)
    return out
