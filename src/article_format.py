"""기사 형식 점검 — 신문 기사(2026-10-28 사장님 기준 기사: 퍼블릭뉴스통신 TTL뉴스
「올마이투어, 메이크마이트립과 한국 숙박 상품 공급 계약 체결」).

본문은 문단만으로 쓴다. 소제목·목록·표·'알아둘 점'·굵은 글씨·모르는 것 목록·
독자에게 말 거는 문장·지역면 링크를 쓰지 않는다. 방송 회차 기사(category: tv)는
따로 정한 형식(정보 상자·소제목)을 쓰므로 이 점검에서 뺀다. [기획] 기사는 소제목만 허용한다.
"""
from __future__ import annotations

import re

MIN_LEN, MAX_LEN = 500, 1600          # 공백 포함 글자 수. 재료가 얇으면 짧게 끝내도 된다

_UNKNOWN = re.compile(r"(?:알려지지|나오지|공개되지|확인되지|밝혀지지|발표되지)\s*않(?:았|는)")
_ADDRESS = re.compile(r"확인해야 한다|확인하는 (?:편이|것이) (?:좋다|안전하다)|염두에 둘|참고하면 좋다|"
                      r"챙겨야 한다|서두르는 게 좋다|알아둘 점")


def body_text(body: str) -> str:
    """점검 대상 본문 — 출처 줄, 영상·사진 줄, HTML 주석은 뺀다."""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(("**출처**", "이 기사는 위 보도를", "@youtube", "![", "<!--")):
            continue
        out.append(line)
    return re.sub(r"<!--.*?-->", "", "\n".join(out), flags=re.S).strip()


def format_problems(body: str, *, tv: bool = False, feature: bool = False) -> list[str]:
    if tv:
        return []
    text = body_text(body)
    lines = text.splitlines()
    found = []
    heads = [l for l in lines if re.match(r"^#{1,6}\s", l)]
    if heads and not feature:
        found.append(f"소제목 {len(heads)}개")
    if any(re.match(r"^\s*(?:[-*]|\d+\.)\s+\S", l) for l in lines):
        found.append("목록")
    if any(re.match(r"^\s*\|.*\|\s*$", l) for l in lines):
        found.append("표")
    if "**" in text:
        found.append("굵은 글씨")
    if re.search(r"\]\(/", text):
        found.append("지역면 링크")
    if _UNKNOWN.search(text):
        found.append("모르는 것 문장")
    if _ADDRESS.search(text):
        found.append("독자에게 말 거는 문장")
    n = len(text)
    if n < MIN_LEN:
        found.append(f"짧다 {n}자")
    elif n > MAX_LEN:
        found.append(f"길다 {n}자")
    return found
