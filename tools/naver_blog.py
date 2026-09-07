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
    # 주간 브리핑만 올린다. 환율·날씨 데이터 기사는 블로그 글이 아니다 —
    # 표 하나로 끝나 검색에서도 걸리지 않고 읽을 것도 없다.
    pool = [i for i in items
            if i.get("grade") == "C"
            and (i.get("title") or "").startswith("이번 주 ")
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


# 도시·지역마다 사람들이 실제로 치는 말. 제목과 태그에 쓴다.
SEARCH_WORDS = {
    "삿포로": ["삿포로여행", "홋카이도여행", "삿포로호텔", "삿포로가볼만한곳"],
    "도쿄": ["도쿄여행", "도쿄호텔", "도쿄가볼만한곳", "일본여행"],
    "오사카": ["오사카여행", "오사카호텔", "간사이여행", "일본여행"],
    "후쿠오카": ["후쿠오카여행", "후쿠오카호텔", "규슈여행", "일본여행"],
    "오키나와": ["오키나와여행", "오키나와호텔", "일본여행"],
    "방콕": ["방콕여행", "방콕호텔", "태국여행"],
    "타이베이": ["타이베이여행", "대만여행", "타이베이맛집"],
    "다낭": ["다낭여행", "다낭호텔", "베트남여행"],
    "나트랑": ["나트랑여행", "베트남여행"],
    "괌": ["괌여행", "괌호텔", "괌자유여행"],
    "사이판": ["사이판여행", "사이판호텔"],
    "하와이": ["하와이여행", "호놀룰루여행"],
    "제주": ["제주여행", "제주도여행", "제주가볼만한곳"],
    "베트남": ["베트남여행", "베트남자유여행"],
    "일본": ["일본여행", "일본자유여행"],
    "태국": ["태국여행", "태국자유여행"],
    "대만": ["대만여행", "대만자유여행"],
    "코타키나발루": ["코타키나발루여행", "코타키나발루호텔"],
    "라오스": ["라오스여행", "비엔티안여행"],
}


def _place(item: dict) -> str:
    return (item.get("title") or "").replace("이번 주 ", "").split("에서")[0]


def make_title(item: dict, facts: list[dict]) -> str:
    """검색되는 제목. "이번 주 삿포로에서 나온 소식 4건"으로는 아무도 찾지 않는다.

    사람들은 "삿포로 여행"을 치지 "이번 주 소식"을 치지 않는다. 앞에 검색어를
    두고 뒤에 그 주의 **가장 값어치 있는 소식**을 붙인다. 소식은 기사에서
    그대로 가져오므로 지어낸 제목이 아니다.

    무엇이 값어치 있는지는 여행자가 쓸 수 있느냐로 정한다. 새 호텔이 언제
    문을 여는지는 일정을 바꾸지만, 어느 매장 20주년 기획전은 그렇지 않다.
    """
    place = _place(item)
    # 앞쪽이 셀수록 여행 계획을 바꾸는 소식이다.
    STRONG = ("오픈", "개장", "취항", "증편", "신규", "운항", "할인", "특가")
    MEDIUM = ("축제", "행사", "출시", "예약", "페어")

    def score(fact: dict) -> tuple:
        text = _plain(fact["headline"])
        strong = next((len(STRONG) - i for i, w in enumerate(STRONG) if w in text), 0)
        medium = 1 if any(w in text for w in MEDIUM) else 0
        here = 1 if place in text else 0
        return (strong, medium, here, -len(text))

    best = max(facts, key=score) if facts else None
    head = _plain(best["headline"]) if best else ""
    # 제목 앞머리의 지명은 이미 앞에 썼으므로 지운다 — "삿포로 여행 | 삿포로 …"
    head = re.sub(rf"^{re.escape(place)}\s*[,·]?\s*", "", head)
    head = head.split("…")[0].split("...")[0].strip(" ,·-")
    if len(head) > 30:
        cut = head[:30].rsplit(" ", 1)[0]
        head = cut if len(cut) >= 18 else head[:30]
    return f"{place} 여행 소식 | {head}" if head else f"{place} 여행 소식"


def make_tags(item: dict, facts: list[dict]) -> list[str]:
    """네이버 태그. 검색 유입의 절반은 여기서 온다."""
    place = _place(item)
    tags = list(SEARCH_WORDS.get(place, [f"{place}여행"]))
    for fact in facts:
        text = _plain(fact["headline"])
        for word in ("호텔", "항공", "축제", "면세", "온천", "맛집", "리조트"):
            if word in text and f"{place}{word}" not in tags:
                tags.append(f"{place}{word}")
    tags.append("와플트립")
    return tags[:10]


def _facts_of(item: dict) -> list[dict]:
    body = item.get("body_md") or ""
    out = []
    for block in re.split(r"^### ", body, flags=re.M)[1:]:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if lines:
            out.append({"headline": re.sub(r"^\d+\.\s*", "", lines[0])})
    return out


def to_blog(item: dict) -> tuple[str, list[str]]:
    """블로그용 제목과 문단들. 마크다운 기호는 네이버에서 그대로 글자로 보인다."""
    title = make_title(item, _facts_of(item))
    body = item.get("body_md") or ""
    paras: list[str] = []

    lead = ""
    for line in body.splitlines():
        if line.startswith(">"):
            lead += line.lstrip("> ").strip() + " "
        elif lead:
            break
    place = _place(item)
    words = SEARCH_WORDS.get(place, [])
    if words:
        # 첫 문단이 검색 결과에 미리보기로 뜬다. 여기에 검색어가 없으면
        # 사람이 눌러야 할 이유를 못 찾는다.
        paras.append(f"{place} 여행 준비하시는 분들을 위해 이번 주 "
                     f"{place} 소식을 정리했습니다. "
                     f"{words[0].replace('여행', ' 여행')} 계획에 참고하세요.")
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


def post(blog_id: str, title: str, paras: list[str], commit: bool,
         tags: list[str] | None = None) -> str:
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

        page.get_by_role("button", name=re.compile(r"^발행$")).first.click()
        page.wait_for_timeout(2500)
        if tags:
            try:
                box = page.locator("input[id*=tag], input[placeholder*=태그]").first
                box.click()
                for tag in tags:
                    page.keyboard.type(tag, delay=25)
                    page.keyboard.press("Enter")
                    page.wait_for_timeout(250)
            except Exception as e:
                print(f"  태그 입력 실패: {e}", file=sys.stderr)
        page.locator("button[class*=confirm_btn]").first.click()
        page.wait_for_timeout(6000)
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

    tags = make_tags(item, _facts_of(item))
    print("태그:", " ".join("#" + t for t in tags))
    where = post(args.blog, title, paras, args.post, tags)
    print(f"결과: {where}")
    if args.post:
        posted[item["id"]] = {"blog": args.blog, "title": title, "url": where}
        save_posted(posted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
