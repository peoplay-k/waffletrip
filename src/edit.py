"""수집 원본을 발행 가능한 항목으로 만든다.

순서가 중요하다.
  등급 → **여행 관련성 필터** → 저작권 가드 → 배치 클러스터 → 발행이력 대조 → C후보
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
from datetime import date, datetime, timedelta, timezone

import yaml

from src.grade import apply_grades, pick_c_candidates
from src.guards.copyright_guard import filter_items
from src.autowrite import build_daily, build_roundup
from src.guards.dup_guard import (PublishedIndex, cluster_batch,
                                  filter_unpublished)
from src.models import Item, item_from_dict, item_to_dict
from src.relevance import is_travel_related
from src.sources import load_sources

DRAFT_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)\.md$")
DRAFT_MAX_AGE_DAYS = 2  # 48시간

# 러너는 UTC 로 돈다. date.today() 를 쓰면 collect(KST)가 만든 디렉터리를 못 찾는다.
KST = timezone(timedelta(hours=9))


def edit_items(raw_items: list[Item], index: PublishedIndex,
               trending: list[str], curated_sources: set[str]) -> dict:
    apply_grades(raw_items)

    # 여행 전용 소스는 그대로 통과시킨다. 거기에 필터를 걸면 멀쩡한 기사를 잃는다.
    relevant: list[Item] = []
    off_topic: list[Item] = []
    for item in raw_items:
        keep = (item.grade == "A"
                or item.source_name in curated_sources
                or is_travel_related(f"{item.title} {item.summary}"))
        (relevant if keep else off_topic).append(item)

    kept, dropped = filter_items(relevant)
    clustered = cluster_batch(kept)
    fresh, duplicates = filter_unpublished(clustered, index)
    candidates = pick_c_candidates(fresh, trending)
    return {"publish": fresh, "c_candidates": candidates,
            "dropped": dropped, "duplicates": duplicates,
            "off_topic": off_topic}


def write_drafts(review_dir: str, candidates: list[tuple[Item, str]],
                 day: str) -> list[str]:
    """검수 대기 초안을 마크다운으로 남긴다.

    프런트매터는 f-string 이 아니라 yaml.safe_dump 로 쓴다. 제목에 콜론이 들어가면
    ("DPS: 76-year-old man died...") 직접 쓴 YAML 이 깨진다 — 실측 351건 중 37건이
    그런 제목이었다. 이 파일을 읽는 쪽(검수 워크플로)이 표준 파서를 쓸 것이므로
    쓰는 쪽도 표준으로 맞춘다.

    본문은 비워둔다. 사람(또는 클로드 예약작업)이 채우고 status 를 approved 로
    바꿔야 발행된다.
    """
    os.makedirs(review_dir, exist_ok=True)
    paths = []
    for item, reason in candidates:
        path = os.path.join(review_dir, f"{day}_{item.id}.md")
        front_matter = yaml.safe_dump(
            {
                "id": item.id,
                "region": item.region,
                "section": item.section,
                "title": item.title,
                "source_name": item.source_name,
                "source_url": item.source_url,
                "reason": reason,
                "status": "draft",
            },
            allow_unicode=True,      # 한글을 \uXXXX 로 깨뜨리지 않는다
            sort_keys=False,         # 사람이 읽는 파일이라 순서를 유지한다
            default_flow_style=False,
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(
                "---\n" + front_matter + "---\n\n"
                "<!-- 여기에 해설을 쓴 뒤 위 status 를 approved 로 바꾼다. -->\n"
                "<!-- 48시간 안에 승인하지 않으면 자동 폐기된다. -->\n"
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
            try:
                with open(path, encoding="utf-8") as f:
                    front = yaml.safe_load(f.read().split("---")[1]) or {}
            except Exception:
                front = {}
            # 승인·발행된 초안은 오래돼도 지우지 않는다. 지우는 것은 방치된 초안뿐이다.
            # published 를 함께 지키지 않으면 낸 기사의 원고가 48시간 뒤 사라진다.
            if front.get("status") in ("approved", "published"):
                continue
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


def load_recent_for_roundup(data_dir: str, today: str, days: int = 7) -> list[Item]:
    """지난 이레 발행분. 주간 브리핑의 재료다."""
    import glob as _g
    out: list[Item] = []
    for path in sorted(_g.glob(os.path.join(data_dir, "items", "*.jsonl")))[-(days + 1):]:
        try:
            with open(path, encoding="utf-8") as f:
                for raw in f:
                    if raw.strip():
                        out.append(item_from_dict(json.loads(raw)))
        except Exception:
            continue
    return out


def main(data_dir: str = "data", review_dir: str = "content/review",
         sources_path: str = "sources.yaml") -> int:
    today = datetime.now(KST).date().isoformat()
    raw_path = os.path.join(data_dir, "raw", today, "items.json")
    if not os.path.exists(raw_path):
        print(f"수집 결과가 없다: {raw_path}. collect 를 먼저 돌려라.",
              file=sys.stderr)
        return 1

    with open(raw_path, encoding="utf-8") as f:
        raw_items = [item_from_dict(d) for d in json.load(f)]

    index = PublishedIndex.load(os.path.join(data_dir, "published_index.json"))
    curated_sources = {s.name for s in load_sources(sources_path) if s.curated}
    result = edit_items(raw_items, index, load_trending(data_dir), curated_sources)

    # 오늘 받은 값으로 데이터 기사를 만든다. **여기서 만드는 이유** —
    # A등급(환율·날씨)은 하루 한 번만 발행되므로 재실행하면 중복 가드가
    # 걸러내 그날 파일에서 사라진다. 값 자체는 방금 받은 오늘 것이므로
    # 걸러지기 전인 이 자리에서 기사를 만드는 것이 옳다.
    publish = list(result["publish"])
    daily = build_daily(raw_items, today, data_dir)
    if daily and not index.contains(daily):
        publish.append(daily)
        print(f"데이터 기사: {daily.title}")

    # 주간 지역 브리핑. 지난 이레치 발행분에서 만든다.
    # 같은 주에 두 번 나가지 않도록 발행 이력이 막는다.
    recent = load_recent_for_roundup(data_dir, today)
    from src.models import REGIONS
    for region in REGIONS:
        art = build_roundup(recent, region, today)
        if art and not index.contains(art):
            publish.append(art)
            print(f"주간 브리핑: {art.title}")

    out_dir = os.path.join(data_dir, "items")
    os.makedirs(out_dir, exist_ok=True)
    day_path = os.path.join(out_dir, f"{today}.jsonl")

    # 오늘 파일을 덮어쓰지 않고 합친다.
    # 같은 날 두 번 돌리면 첫 실행분은 이미 발행이력에 있으므로 이번 publish
    # 에서 중복으로 걸러진다. 그대로 덮어쓰면 그 기사들이 통째로 사라지고,
    # 빌드는 이 파일로 지면을 만들므로 이미 나간 기사가 사이트에서 없어진다.
    # (실제로 도쿄 78건이 21건으로 줄었다.)
    existing: list[dict] = []
    kept: set[str] = set()
    if os.path.exists(day_path):
        with open(day_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    existing.append(row)
                    kept.add(row["id"])

    with open(day_path, "w", encoding="utf-8") as f:
        for row in existing:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        for item in publish:
            if item.id in kept:
                continue
            f.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")

    purged = purge_stale_drafts(review_dir, today)
    drafts = write_drafts(review_dir, result["c_candidates"], today)

    print(f"편집 완료: 발행대상 {len(result['publish'])}건, "
          f"검수초안 {len(drafts)}건, 폐기 {len(result['dropped'])}건, "
          f"중복 {len(result['duplicates'])}건, 주제밖 {len(result['off_topic'])}건, "
          f"만료초안 삭제 {len(purged)}건")
    for item, reasons in result["dropped"]:
        print(f"  폐기 [{item.source_name}] {item.title[:40]} — "
              f"{'; '.join(reasons)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
