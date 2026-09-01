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


def _safe_href(url: str) -> str:
    """http/https 만 링크로 만든다. javascript: 스킴을 막는 것과 같은 이유다."""
    return url if url.lower().startswith(("http://", "https://", "/")) else ""


def _inline(text: str) -> str:
    out = html.escape(text, quote=True)          # ← 반드시 먼저

    def link(m):
        href = _safe_href(html.unescape(m.group(2)))
        label = m.group(1)
        if not href:
            return label
        return '<a href="%s" rel="nofollow noopener" target="_blank">%s</a>' % (
            html.escape(href, quote=True), label)

    out = _LINK.sub(link, out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _CODE.sub(r"<code>\1</code>", out)
    return out


def render(src: str) -> str:
    """지원 문법: 소제목(##~####) · 문단 · 목록 · 표 · 인용 · 구분선."""
    if not src:
        return ""
    lines = src.split("\n")
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
            out.append("<blockquote>%s</blockquote>" % _inline(" ".join(buf)))
            continue

        if _LIST.match(stripped):
            tag = "ol" if re.match(r"^\d+\.", stripped) else "ul"
            buf = []
            while i < len(lines) and _LIST.match(lines[i].strip()):
                buf.append(_LIST.sub("", lines[i].strip()))
                i += 1
            out.append("<%s>%s</%s>" % (
                tag, "".join("<li>%s</li>" % _inline(b) for b in buf), tag))
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
            out.append("<p>%s</p>" % _inline(" ".join(buf)))
        else:
            out.append("<p>%s</p>" % _inline(stripped))
            i += 1
    return "\n".join(out)
