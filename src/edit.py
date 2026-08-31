"""수집 원본을 발행 가능한 항목으로 만든다.

순서가 중요하다.
  등급 → 저작권 가드 → 배치 클러스터 → 발행이력 대조 → C후보 선정
저작권 가드를 클러스터보다 먼저 두는 이유: 위반 항목이 대표가 되면
클러스터 전체가 사라진다.

이 모듈은 발행 이력을 읽기만 하고 쓰지 않는다. 인덱스 갱신은 build 가
실제로 페이지를 만든 뒤에 한다 — 안 나간 것을 발행됨으로 기록하지 않기 위해서다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, timedelta

from src.grade import apply_grades, pick_c_candidates
from src.guards.copyright_guard import filter_items
from src.guards.dup_guard import (PublishedIndex, cluster_batch,
                                  filter_unpublished)
from src.models import Item, item_from_dict, item_to_dict

DRAFT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)\.md$")
DRAFT_MAX_AGE_DAYS = 2  # 48시간


def edit_items(raw_items: list[Item], index: PublishedIndex,
               trending: list[str]) -> dict:
    apply_grades(raw_items)
    kept, dropped = filter_items(raw_items)
    clustered = cluster_batch(kept)
    fresh, duplicates = filter_unpublished(clustered, index)
    candidates = pick_c_candidates(fresh, trending)
    return {"publish": fresh, "c_candidates": candidates,
            "dropped": dropped, "duplicates": duplicates}


def write_drafts(review_dir: str, candidates: list[tuple[Item, str]],
                 day: str) -> list[str]:
    """검수 대기 초안을 마크다운으로 남긴다.

    본문은 비워둔다. 사람(또는 클로드 예약작업)이 채우고 status 를 approved
    로 바꿔야 발행된다.
    """
    os.makedirs(review_dir, exist_ok=True)
    paths = []
    for item, reason in candidates:
        path = os.path.join(review_dir, f"{day}_{item.id}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                f"---\n"
                f"id: {item.id}\n"
                f"region: {item.region}\n"
                f"section: {item.section}\n"
                f"title: {item.title}\n"
                f"source_name: {item.source_name}\n"
                f"source_url: {item.source_url}\n"
                f"reason: {reason}\n"
                f"status: draft\n"
                f"---\n\n"
                f"<!-- 여기에 해설을 쓴 뒤 위 status 를 approved 로 바꾼다. -->\n"
                f"<!-- 48시간 안에 승인하지 않으면 자동 폐기된다. -->\n"
            )
        paths.append(path)
    return paths


def purge_stale_drafts(review_dir: str, today: str,
                       max_age_days: int = DRAFT_MAX_AGE_DAYS) -> list[str]:
    """48시간 지난 미승인 초안을 지운다.

    신선도가 지난 뉴스이기도 하고, 오래된 초안이 쌓이면 검수 자체를 안 하게 된다.
    """
    if not os.path.isdir(review_dir):
        return []

    cutoff = (date.fromisoformat(today) - timedelta(days=max_age_days)).isoformat()
    removed = []
    for name in sorted(os.listdir(review_dir)):
        m = DRAFT_NAME.match(name)
        if not m:
            continue  # 우리가 만든 초안이 아니다
        if m.group(1) < cutoff:
            path = os.path.join(review_dir, name)
            os.remove(path)
            removed.append(path)
    return removed


def load_trending(data_dir: str) -> list[str]:
    """검색 급상승 키워드를 읽는다. 없으면 빈 리스트.

    네이버 데이터랩은 Actions 러너에서 접근할 수 없으므로 파일 이음매로 받는다.
    없거나 깨져도 파이프라인을 멈추지 않는다 — 키워드는 후보 선정의 보조
    신호이지 발행의 전제조건이 아니다.
    """
    path = os.path.join(data_dir, "trending.json")
    try:
        with open(path, encoding="utf-8") as f:
            return list(json.load(f).get("keywords") or [])
    except Exception:
        return []


def main(data_dir: str = "data", review_dir: str = "content/review") -> int:
    today = date.today().isoformat()
    raw_path = os.path.join(data_dir, "raw", today, "items.json")
    if not os.path.exists(raw_path):
        print(f"수집 결과가 없다: {raw_path}. collect 를 먼저 돌려라.",
              file=sys.stderr)
        return 1

    with open(raw_path, encoding="utf-8") as f:
        raw_items = [item_from_dict(d) for d in json.load(f)]

    index = PublishedIndex.load(os.path.join(data_dir, "published_index.json"))
    result = edit_items(raw_items, index, load_trending(data_dir))

    out_dir = os.path.join(data_dir, "items")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{today}.jsonl"), "w",
              encoding="utf-8") as f:
        for item in result["publish"]:
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")

    purged = purge_stale_drafts(review_dir, today)
    drafts = write_drafts(review_dir, result["c_candidates"], today)

    print(f"편집 완료: 발행대상 {len(result['publish'])}건, "
          f"검수초안 {len(drafts)}건, 폐기 {len(result['dropped'])}건, "
          f"중복 {len(result['duplicates'])}건, 만료초안 삭제 {len(purged)}건")
    for item, reasons in result["dropped"]:
        print(f"  폐기 [{item.source_name}] {item.title[:40]} — "
              f"{'; '.join(reasons)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
