"""최근 항목을 모아 정적 사이트를 만든다.

두 가지를 지킨다.
- 수집이 0건인 날에는 사이트를 만들지 않고 0이 아닌 종료 코드로 멈춘다.
  (public/ 은 gitignore 라 러너 체크아웃에 없으므로 "기존 사이트가 있으면
  건너뛴다"는 판정 자체가 CI 에서 불가능하다.) 워크플로가 여기서 멎으면
  Pages 배포 단계가 실행되지 않아 직전 배포가 그대로 유지된다 — 빈 사이트를
  올려 어제까지 색인된 페이지를 지우는 사고를 막는다.
- 발행 이력은 사이트를 실제로 만든 뒤에 갱신한다. 안 나간 것을
  발행됨으로 기록하면 그 기사는 영영 못 나간다.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from src.guards.dup_guard import PublishedIndex
from src.models import Item, item_from_dict
from src.render.feeds import (render_cname, render_robots, render_rss,
                              render_sitemap)
from src.render.site import render_site

SITE_WINDOW_DAYS = 14
KST = timezone(timedelta(hours=9))


def load_recent_items(items_dir: str, today: str,
                      days: int = SITE_WINDOW_DAYS) -> list[Item]:
    """최근 days 일치 항목을 모아 최신순으로 정렬한다."""
    if not os.path.isdir(items_dir):
        return []

    start = date.fromisoformat(today) - timedelta(days=days)
    items: list[Item] = []

    for name in sorted(os.listdir(items_dir)):
        if not name.endswith(".jsonl"):
            continue
        day = name[:-len(".jsonl")]
        try:
            if date.fromisoformat(day) < start:
                continue
        except ValueError:
            continue  # 우리가 만든 파일이 아니다

        with open(os.path.join(items_dir, name), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    items.append(item_from_dict(json.loads(line)))

    items.sort(key=lambda i: i.published_at, reverse=True)

    # 같은 기사가 여러 날 파일에 들어있을 수 있다 — 발행 이력이 초기화됐거나
    # 하루에 편집을 두 번 돌린 경우다. 목록에 같은 기사가 두 번 실리면 안 된다.
    # 정렬을 먼저 했으므로 남는 것은 가장 최근 판본이다.
    seen: set[str] = set()
    unique: list[Item] = []
    for item in items:
        if item.id in seen:
            continue
        seen.add(item.id)
        unique.append(item)
    return unique


def site_has_content(out_dir: str) -> bool:
    return os.path.exists(os.path.join(out_dir, "index.html"))


def build(items: list[Item], out_dir: str, today: str,
          built_at: str) -> list[str]:
    written = render_site(items, out_dir, today)
    written.append(render_rss(items, out_dir, built_at))
    written.append(render_sitemap(items, out_dir, today))
    written.append(render_robots(out_dir))
    written.append(render_cname(out_dir))
    return written


def main(data_dir: str = "data", out_dir: str = "public") -> int:
    built_at = datetime.now(KST).isoformat()
    today = built_at[:10]

    items = load_recent_items(os.path.join(data_dir, "items"), today)

    if not items:
        print("경고: 최근 항목이 0건이다. 사이트를 만들지 않고 멈춘다 — "
              "빈 사이트를 배포하면 색인된 페이지가 전부 사라진다.",
              file=sys.stderr)
        return 1

    written = build(items, out_dir, today, built_at)

    # 사이트가 실제로 나온 뒤에만 발행 이력을 갱신한다.
    index_path = os.path.join(data_dir, "published_index.json")
    index = PublishedIndex.load(index_path)
    todays = [i for i in items if i.collected_at[:10] == today]
    for item in todays:
        index.add(item, today)
    index.save(index_path)

    print(f"빌드 완료: 항목 {len(items)}건 → 파일 {len(written)}개, "
          f"발행이력 +{len(todays)}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
