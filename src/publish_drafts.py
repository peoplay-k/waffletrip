"""승인된 해설 초안을 발행 대상으로 내보낸다.

지금까지 검수 초안은 쌓이기만 하고 나가는 길이 없었다. 이 모듈이 그 길이다.
파이프라인 순서: collect → edit → **publish_drafts** → build

세 가지를 지킨다.

1. **해설 기사는 원본과 다른 id 를 갖는다.** 초안 파일명이 원본 기사 id 라
   그대로 쓰면 원본이 이미 발행 이력에 있어서 승인해도 중복으로 막힌다.
   `c-` 접두사를 붙인다 — 원본 id 는 순수 16진수라 접두사가 있으면 절대 겹치지 않는다.
2. **본문이 비면 발행하지 않는다.** status 만 approved 로 바꾸고 본문을 안 쓴
   초안이 빈 기사로 나가는 것을 막는다.
3. **내보낸 초안은 status 를 published 로 바꾼다.** 다음 실행에서 또 나가지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import yaml

from src.guards.dup_guard import PublishedIndex
from src.guards.privacy_guard import find_violations
from src.models import Item, item_to_dict, title_hash

KST = timezone(timedelta(hours=9))

# 초안 본문에서 안내 주석을 걷어낸다. 이게 남아 있으면 본문이 있다고 오판한다.
_COMMENT_PREFIX = "<!--"


def commentary_id(source_id: str, day: str) -> str:
    """해설 기사의 id. 원본 id(순수 16진수)와 절대 겹치지 않는다."""
    digest = hashlib.sha1(f"{day}:{source_id}".encode("utf-8")).hexdigest()
    return f"c-{digest}"


def _split(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    return (yaml.safe_load(parts[1]) or {}), parts[2]


def _body_text(body: str) -> str:
    """안내 주석을 뺀 실제 본문."""
    return "\n".join(
        line for line in body.splitlines()
        if not line.strip().startswith(_COMMENT_PREFIX)
    ).strip()


def _summary_of(front: dict, body: str) -> str:
    """요약. 직접 쓴 게 있으면 그걸, 없으면 첫 문단을 쓴다.

    우리가 쓴 글이므로 저작권 가드의 인용 길이 제한을 적용하지 않는다.
    """
    written = (front.get("summary") or "").strip()
    if written:
        return written
    for block in body.split("\n\n"):
        text = block.strip()
        if text and not text.startswith(("#", ">", "|", "-", "*")):
            return text[:200]
    return ""


def collect_approved(review_dir: str, day: str) -> list[tuple[str, Item]]:
    """승인됐고 본문이 있는 초안을 Item 으로 만든다. (경로, Item) 목록."""
    if not os.path.isdir(review_dir):
        return []
    now = datetime.now(KST).isoformat(timespec="seconds")
    out: list[tuple[str, Item]] = []
    for name in sorted(os.listdir(review_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(review_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                front, body = _split(f.read())
        except Exception as e:
            print(f"  초안을 읽지 못했다: {name} — {type(e).__name__}: {e}",
                  file=sys.stderr)
            continue

        if front.get("status") != "approved":
            continue
        text = _body_text(body)
        if not text:
            print(f"  본문이 비어 있어 건너뛴다: {name}", file=sys.stderr)
            continue

        # 개인정보·거래단가는 발행 경로에서 막는다. 해설 기사는 여행사 운영
        # 기록에서 나오므로 원천에 고객 정보와 계약 숫자가 섞여 있다.
        violations = find_violations(f"{front.get('title', '')}\n{text}")
        if violations:
            print(f"  발행 차단 {name}:", file=sys.stderr)
            for kind, found in violations:
                print(f"    [{kind}] {found}", file=sys.stderr)
            continue

        source_id = str(front.get("id") or name)
        title = str(front.get("title") or "").strip()
        if not title:
            print(f"  제목이 없어 건너뛴다: {name}", file=sys.stderr)
            continue

        out.append((path, Item(
            id=commentary_id(source_id, day),
            grade="C",
            region=str(front.get("region") or ""),
            section=str(front.get("section") or "news"),
            title=title,
            summary=_summary_of(front, text),
            source_name=str(front.get("source_name") or ""),
            source_url=str(front.get("source_url") or ""),
            published_at=now,
            collected_at=now,
            status="published",
            title_hash=title_hash(title),
            body_md=text,
            photo=(str(front.get("photo") or "") or None),
        )))
    return out


def _mark_published(path: str, item_id: str) -> None:
    with open(path, encoding="utf-8") as f:
        front, body = _split(f.read())
    front["status"] = "published"
    front["published_id"] = item_id
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n")
        f.write(body.lstrip("\n"))


def main(data_dir: str = "data", review_dir: str = "content/review") -> int:
    today = datetime.now(KST).date().isoformat()
    approved = collect_approved(review_dir, today)
    if not approved:
        print("발행할 승인 초안이 없다.")
        return 0

    index_path = os.path.join(data_dir, "published_index.json")
    index = PublishedIndex.load(index_path)

    published: list[tuple[str, Item]] = []
    for path, item in approved:
        if item.id in index.ids:
            print(f"  이미 발행됨, 건너뛴다: {os.path.basename(path)}")
            continue
        published.append((path, item))

    if not published:
        print("새로 낼 해설 기사가 없다.")
        return 0

    out_dir = os.path.join(data_dir, "items")
    os.makedirs(out_dir, exist_ok=True)
    # edit.py 가 같은 파일을 'w' 로 먼저 쓴다. 반드시 이어쓴다.
    with open(os.path.join(out_dir, f"{today}.jsonl"), "a", encoding="utf-8") as f:
        for _, item in published:
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")

    for path, item in published:
        index.add(item, today)
        _mark_published(path, item.id)
    index.save(index_path)

    print(f"해설 기사 발행: {len(published)}건")
    for _, item in published:
        print(f"  [{item.region}] {item.title[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
