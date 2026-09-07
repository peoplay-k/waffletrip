#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""와플트립 기사를 네이버 블로그에 올린다.

**계정과 블로그는 인자로만 받는다.** 회사 채널과 개인 채널이 같은 브라우저에
떠 있어서, 기본값을 두면 언젠가 엉뚱한 곳에 올라간다. 실제로 상주 브라우저에
서로 다른 계정의 블로그 탭이 네 개 열려 있었다.

로그인은 하지 않는다. 사람이 로그인해 둔 상주 브라우저(CDP 9222)에 붙어
그 세션을 쓴다. 비밀번호를 다루지 않는 것이 이 도구의 전제다.

    python3 tools/naver_blog.py --blog hannyndannys --dry-run
    python3 tools/naver_blog.py --blog hannyndannys --post
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

CDP = "http://127.0.0.1:9222"
HISTORY = "data/naver_blog_posted.json"
CATEGORY_HINT = "자유여행"


def load_items(data_dir: str = "data") -> list[dict]:
    items, seen = [], set()
    for path in sorted(glob.glob(os.path.join(data_dir, "items", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row["id"] not in seen:
                        seen.add(row["id"])
                        items.append(row)
    return items


def load_posted() -> dict:
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_posted(d: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def pick(items: list[dict], posted: dict) -> dict | None:
    """아직 안 올린 주간 브리핑 하나. 우리가 쓴 글만 올린다.

    인용 기사(B등급)는 남의 취재다. 그것을 우리 블로그에 옮기면 원문을
    베끼는 것이 되고, 네이버는 그런 글을 유사문서로 걸러낸다.
    """
    pool = [i for i in items
            if i.get("grade") == "C"
            and (i.get("body_md") or "").strip()
            and i["id"] not in posted
            and _korean_ratio(i["body_md"]) >= 0.5]
    # 한국 독자가 보는 블로그다. 코타키나발루 브리핑이 현지 영자지 기사로만
    # 채워져 올라갈 뻔했다 — 고속도로 정체와 마약 단속 기사였다.
    pool.sort(key=lambda i: i.get("published_at") or "", reverse=True)
    return pool[0] if pool else None


_HANGUL = re.compile(r"[가-힣]")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _korean_ratio(body: str) -> float:
    """본문에서 한글이 든 줄의 비율. 영어 기사만 묶인 브리핑을 거른다."""
    lines = [l for l in body.splitlines() if l.strip() and not l.startswith(">")]
    if not lines:
        return 0.0
    return sum(1 for l in lines if _HANGUL.search(l)) / len(lines)


def _plain(text: str) -> str:
    """마크다운 기호를 걷어낸다. 네이버에서는 그대로 글자로 보인다."""
    text = _MD_LINK.sub(lambda m: m.group(1), text)
    text = text.replace("**", "").replace("`", "")
    return text.strip(" *_")


def to_blog(item: dict) -> tuple[str, list[str]]:
    """블로그용 제목과 문단들. 마크다운 기호는 네이버에서 그대로 글자로 보인다."""
    title = item["title"]
    body = item.get("body_md") or ""
    paras: list[str] = []

    lead = ""
    for line in body.splitlines():
        if line.startswith(">"):
            lead += line.lstrip("> ").strip() + " "
        elif lead:
            break
    if lead:
        paras.append(_plain(lead))

    blocks = re.split(r"^### ", body, flags=re.M)[1:]
    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        head = _plain(re.sub(r"^\d+\.\s*", "", lines[0]))
        paras.append("")
        paras.append(f"◆ {head}")
        for line in lines[1:]:
            if line.startswith("*") and "·" in line:
                paras.append(_plain(line))
            elif not line.startswith(("#", "-", ">", "|")):
                paras.append(_plain(line))

    paras.append("")
    paras.append("─" * 20)
    paras.append("기사 원문과 매일 갱신되는 환율·날씨는 와플트립에서 보실 수 있습니다.")
    paras.append("https://waffletrip.com")
    return title, [p for p in paras]


def post(blog_id: str, title: str, paras: list[str], commit: bool) -> str:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.goto(f"https://blog.naver.com/{blog_id}/postwrite",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        # 글쓰기 화면은 iframe 안에 있다. 없으면 그대로 페이지를 쓴다.
        frame = next((f for f in page.frames if "postwrite" in (f.url or "")),
                     None) or page.main_frame

        # 이전 글 이어쓰기 팝업. 뜨면 취소해야 빈 화면에서 시작한다.
        for label in ("취소", "닫기"):
            try:
                btn = frame.get_by_role("button", name=label)
                if btn.count() and btn.first.is_visible():
                    btn.first.click()
                    page.wait_for_timeout(800)
            except Exception:
                pass

        frame.click(".se-section-documentTitle .se-text-paragraph", timeout=30000)
        page.keyboard.type(title, delay=12)
        page.keyboard.press("Enter")
        for para in paras:
            if para:
                page.keyboard.type(para, delay=6)
            page.keyboard.press("Enter")

        if not commit:
            page.wait_for_timeout(1500)
            return "초안까지만 채웠다(--post 를 붙여야 발행한다)"

        frame.get_by_role("button", name=re.compile("발행")).first.click()
        page.wait_for_timeout(1500)
        frame.get_by_role("button", name=re.compile("발행")).last.click()
        page.wait_for_timeout(5000)
        return page.url


def main() -> int:
    ap = argparse.ArgumentParser(description="와플트립 → 네이버 블로그")
    ap.add_argument("--blog", required=True, help="블로그 아이디 (blog.naver.com/<여기>)")
    ap.add_argument("--post", action="store_true", help="실제로 발행한다")
    ap.add_argument("--dry-run", action="store_true", help="글만 만들어 보여준다")
    args = ap.parse_args()

    posted = load_posted()
    item = pick(load_items(), posted)
    if not item:
        print("올릴 자체 생산 기사가 없다.", file=sys.stderr)
        return 1
    title, paras = to_blog(item)

    print(f"블로그: blog.naver.com/{args.blog}")
    print(f"제목: {title}")
    print("-" * 56)
    for p in paras:
        print(f"  {p}")
    print("-" * 56)
    if args.dry_run:
        return 0

    where = post(args.blog, title, paras, args.post)
    print(f"결과: {where}")
    if args.post:
        posted[item["id"]] = {"blog": args.blog, "title": title, "url": where}
        save_posted(posted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
