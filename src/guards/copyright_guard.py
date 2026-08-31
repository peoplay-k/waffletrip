"""인용 한도·출처·이미지 규칙을 검증한다.

이 가드는 자르지 않는다. 통과시키거나 폐기한다.
요약이 한도를 넘었다는 것은 우리가 요약을 못 했다는 뜻이고,
그 상태로 자르면 남의 글 앞부분을 그대로 싣는 것과 같기 때문이다.

이 모듈은 파일시스템을 모른다. 항목 하나만 보고 판정한다.
"""
from __future__ import annotations

import re

from src.models import Item

MAX_SUMMARY_CHARS = 200
MAX_SUMMARY_SENTENCES = 2

_SENTENCE_END = re.compile(r"(?<=[.!?。？！])\s+")
_IMAGE_PATTERNS = (
    re.compile(r"<img\b", re.I),
    re.compile(r"!\[[^\]]*\]\("),
    re.compile(r"https?://\S+\.(?:jpe?g|png|gif|webp|avif|bmp)\b", re.I),
)


def _sentence_count(text: str) -> int:
    stripped = text.strip()
    if not stripped:
        return 0
    return len([p for p in _SENTENCE_END.split(stripped) if p.strip()])


def _has_image(text: str) -> bool:
    return any(p.search(text or "") for p in _IMAGE_PATTERNS)


def violations(item: Item) -> list[str]:
    """위반 사유 목록. 빈 리스트면 통과."""
    reasons: list[str] = []

    # 출처는 등급을 가리지 않고 필요하다 — A는 공공기관, B는 원매체.
    if item.grade in ("A", "B"):
        if not item.source_name or not item.source_url:
            reasons.append("출처 누락 (source_name·source_url 둘 다 필요)")

    # 인용 한도는 남의 글을 옮기는 B등급에만 적용한다.
    if item.grade == "B":
        if len(item.summary) > MAX_SUMMARY_CHARS:
            reasons.append(
                f"인용 한도 초과: {len(item.summary)}자 > {MAX_SUMMARY_CHARS}자")
        n = _sentence_count(item.summary)
        if n > MAX_SUMMARY_SENTENCES:
            reasons.append(
                f"인용 한도 초과: {n}문장 > {MAX_SUMMARY_SENTENCES}문장")

    # 해설 기사인데 본문이 없으면 기사가 아니다.
    if item.grade == "C" and not (item.body_md or "").strip():
        reasons.append("C등급인데 본문(body_md)이 비었다")

    if _has_image(item.summary) or _has_image(item.body_md or ""):
        reasons.append("원문 이미지 임베드 금지 (자체 실사·공식 배포본만 허용)")

    return reasons


def filter_items(
    items: list[Item],
) -> tuple[list[Item], list[tuple[Item, list[str]]]]:
    kept: list[Item] = []
    dropped: list[tuple[Item, list[str]]] = []
    for item in items:
        reasons = violations(item)
        if reasons:
            dropped.append((item, reasons))
        else:
            kept.append(item)
    return kept, dropped
