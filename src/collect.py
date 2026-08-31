"""소스를 병렬로 두드려 원본 항목을 data/raw/ 에 남긴다.

설계 원칙: 개별 소스의 실패는 격리된다. 하나가 죽어도 나머지로 신문을 낸다.
실패는 삼키지 않고 _errors.json 에 남겨 3일 연속 실패를 감시할 수 있게 한다.
"""
from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from src.fetch import json_api, rss
from src.models import Item, item_to_dict
from src.sources import Source, load_sources

KST = timezone(timedelta(hours=9))


def now_kst() -> str:
    return datetime.now(KST).isoformat()


def collect_one(source: Source, client, collected_at: str) -> list[Item]:
    if source.type == "rss":
        return rss.fetch(source, client, collected_at)
    if source.type == "json":
        return json_api.fetch(source, client, collected_at)
    raise ValueError(f"알 수 없는 소스 타입 '{source.type}' (id={source.id})")


def collect_all(sources: list[Source], client, collected_at: str,
                max_workers: int = 8) -> tuple[list[Item], list[dict]]:
    items: list[Item] = []
    errors: list[dict] = []

    if not sources:
        return items, errors

    def run(source: Source):
        try:
            return source, collect_one(source, client, collected_at), None
        except Exception as e:  # 소스 하나의 실패로 전체를 멈추지 않는다
            return source, [], f"{type(e).__name__}: {e}"

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for source, fetched, error in pool.map(run, sources):
            if error:
                errors.append({"source_id": source.id, "url": source.url,
                               "error": error})
            else:
                items.extend(fetched)

    return items, errors


def write_raw(out_dir: str, items: list[Item], errors: list[dict]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump([item_to_dict(i) for i in items], f,
                  ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "_errors.json"), "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


def main(sources_path: str = "sources.yaml", data_dir: str = "data") -> int:
    collected_at = now_kst()
    day = collected_at[:10]
    sources = load_sources(sources_path)

    with httpx.Client() as client:
        items, errors = collect_all(sources, client, collected_at)

    out_dir = os.path.join(data_dir, "raw", day)
    write_raw(out_dir, items, errors)

    print(f"수집 완료: 소스 {len(sources)}개, 항목 {len(items)}건, "
          f"실패 {len(errors)}건 → {out_dir}")
    for e in errors:
        print(f"  실패 {e['source_id']}: {e['error']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
