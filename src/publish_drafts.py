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
4. **채널을 지킨다.** 여행 초안은 region 이 지역 목록 안에 있어야 한다 — 예전엔 빈
   region 이 조용히 통과해 `//` 주소가 났다. 연예 초안(channel: ent)은 region 을
   무시하고 category(연예 부문)를 싣는다. 편집실 두 곳이 같은 프론트매터를 쓴다.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date as _date, datetime, timedelta, timezone

import yaml

from src.attribution import find_media_attribution, media_names, strip_media_attribution
from src.guards.dup_guard import PublishedIndex
from src.guards.privacy_guard import find_violations
from src.models import CHANNELS, REGIONS, Item, item_to_dict, title_hash
from src.topics import ent_canonical

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

        # 오늘 발행했는데 오늘 파일에서 사라진 기사는 다시 낸다.
        # edit 가 그날 jsonl 을 'w' 로 덮어쓰기 때문에, 로컬에서 발행한 뒤
        # CI 에서 edit 가 다시 돌면 해설 기사가 통째로 지워진다. 발행 이력에는
        # id 가 남아 있어 아래 중복 검사에도 걸리지 않아 조용히 사라졌다.
        status = front.get("status")
        if status == "published" and front.get("published_on") == day:
            pass                      # 아래에서 오늘 파일에 있는지 확인한다
        elif status != "approved":
            continue
        text = _body_text(body)
        if not text:
            print(f"  본문이 비어 있어 건너뛴다: {name}", file=sys.stderr)
            continue

        # 본문에 매체 인용("PDN은 17일 보도에서 …전했다", "같은 보도에 따르면")을 두지 않는다
        # (2026-10-19 사장님). 규칙으로 고칠 수 있는 건 고치고, 남으면 내보내지 않는다.
        # 참고한 매체와 원문 주소는 맨 끝 **출처** 줄에만 밝힌다.
        names = media_names(body)
        text = strip_media_attribution(text, names)
        front = dict(front)
        if front.get("summary"):
            front["summary"] = strip_media_attribution(str(front["summary"]), names)
        left = (find_media_attribution(text, names)
                + find_media_attribution(str(front.get("summary") or ""), names))
        if left:
            print(f"  발행 보류 {name}: 본문에 매체 인용 문장이 남았다 — 사실만 쓰고 매체는 출처 줄로", file=sys.stderr)
            for s in left[:5]:
                print(f"    · {s[:120]}", file=sys.stderr)
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

        channel = str(front.get("channel") or "travel").strip()
        if channel not in CHANNELS:
            print(f"  모르는 채널이라 건너뛴다: {name} — channel={channel!r}",
                  file=sys.stderr)
            continue
        region = str(front.get("region") or "").strip()
        category = str(front.get("category") or "").strip()
        if channel == "ent":
            region = ""                # 연예 기사는 지역면이 없다
            if category and not ent_canonical(category):
                print(f"  모르는 연예 부문이라 건너뛴다: {name} — category={category!r}",
                      file=sys.stderr)
                continue
            category = ent_canonical(category)
        else:
            category = ""
            if region not in REGIONS:
                print(f"  지역이 없거나 모르는 지역이라 건너뛴다: {name} — region={region!r}",
                      file=sys.stderr)
                continue

        out.append((path, Item(
            id=commentary_id(source_id, day),
            grade="C",
            region=region,
            channel=channel,
            category=category,
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
            # 편집실에서 직접 고른 여행 부문(2026-10-30). 비면 규칙으로 정한다.
            topic="" if channel == "ent" else str(front.get("topic") or "").strip(),
        )))
    return out


SAME_SOURCE_DAYS = 10


def _front(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return _split(f.read())[0] or {}
    except Exception:
        return {}


def _sources(front: dict) -> set[str]:
    src = front.get("sources") or []
    return {str(u).strip() for u in (src if isinstance(src, list) else [src]) if str(u).strip()}


def already_used_sources(review_dir: str, today: str, days: int = SAME_SOURCE_DAYS) -> dict[str, str]:
    """최근 days 일에 이미 낸 기사의 근거 주소 → 그 파일 이름.

    2026-10-28 실측: EBS 보도자료 하나('지식채널e 26~28일')를 10-25·10-26 에 거의 같은 글로
    두 번 냈다. 하루 네 번 쓰고 보도자료가 며칠씩 재료에 남으니, 근거가 같은 글을 발행에서 막는다.
    """
    since = (_date.fromisoformat(today) - timedelta(days=days)).isoformat()
    used: dict[str, str] = {}
    if not os.path.isdir(review_dir):
        return used
    for name in os.listdir(review_dir):
        if not name.endswith(".md"):
            continue
        front = _front(os.path.join(review_dir, name))
        if front.get("status") == "published" and str(front.get("published_on") or "") >= since:
            for u in _sources(front):
                used.setdefault(u, name)
    return used


def _mark_duplicate(path: str, dup_of: str) -> None:
    with open(path, encoding="utf-8") as f:
        front, body = _split(f.read())
    front["status"] = "duplicate"
    front["duplicate_of"] = dup_of
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n")
        f.write(body.lstrip("\n"))


def _mark_published(path: str, item_id: str, day: str) -> None:
    with open(path, encoding="utf-8") as f:
        front, body = _split(f.read())
    front["status"] = "published"
    front["published_id"] = item_id
    front["published_on"] = day
    # 발행한 본문과 원고가 같아야 다음에 고칠 때 어긋나지 않는다
    names = media_names(body)
    body = strip_media_attribution(body, names)
    if front.get("summary"):
        front["summary"] = strip_media_attribution(str(front["summary"]), names)
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

    # 오늘 파일에 이미 들어 있는 id
    items_path = os.path.join(data_dir, "items", f"{today}.jsonl")
    present: set[str] = set()
    if os.path.exists(items_path):
        with open(items_path, encoding="utf-8") as f:
            for raw in f:
                if raw.strip():
                    try:
                        present.add(json.loads(raw)["id"])
                    except Exception:
                        pass

    used = already_used_sources(review_dir, today)
    published: list[tuple[str, Item]] = []
    for path, item in approved:
        if item.id in present:
            print(f"  오늘 지면에 이미 있다, 건너뛴다: {os.path.basename(path)}")
            continue
        front = _front(path)
        if front.get("status") == "approved":
            same = [u for u in _sources(front) if u in used and used[u] != os.path.basename(path)]
            if same:
                print(f"  같은 근거로 이미 낸 기사가 있다, 내보내지 않는다: {os.path.basename(path)} "
                      f"← {used[same[0]]}")
                _mark_duplicate(path, used[same[0]])
                continue
            for u in _sources(front):
                used.setdefault(u, os.path.basename(path))   # 같은 회차의 두 초안끼리도 막는다
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
        if path:                      # 자동 생성 기사는 초안 파일이 없다
            _mark_published(path, item.id, today)
    index.save(index_path)

    print(f"해설 기사 발행: {len(published)}건")
    for _, item in published:
        print(f"  [{item.region or ('ent/' + (item.category or 'startrip'))}] {item.title[:50]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
