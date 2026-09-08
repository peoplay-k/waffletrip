"""이미 쌓인 지면에서 같은 사건 중복을 걷어낸다. 한 번만 쓰는 도구.

2026-09-08 에 same_event 판정을 넣기 전까지, 자카드가 임계값을 못 넘는 중복이
그대로 실렸다. 대한항공·일본항공 한진칼 기사는 13개 매체 버전이 각각 한 쪽씩
차지했다. 구글이 막 이 사이트를 색인하기 시작한 참이라 그대로 두면 중복 문서로
쌓인다.

흡수된 기사는 지우는 것이 아니라 대표 기사의 related 로 옮긴다. 몇 개 매체가
보도했는지가 그 사건의 중요도이고, 해설 기사 후보를 고르는 첫 번째 근거다.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.guards.dup_guard import cluster_batch          # noqa: E402
from src.models import Item, item_to_dict               # noqa: E402


def _to_item(d: dict) -> Item:
    return Item(id=d["id"], grade=d["grade"], region=d["region"],
                section=d["section"], title=d["title"], summary=d.get("summary", ""),
                source_name=d.get("source_name", ""), source_url=d.get("source_url", ""),
                published_at=d.get("published_at", ""),
                collected_at=d.get("collected_at", ""),
                status=d.get("status", "draft"), title_hash=d.get("title_hash", ""),
                body_md=d.get("body_md"), photo=d.get("photo"),
                related=list(d.get("related") or []))


def main() -> int:
    removed = 0
    for path in sorted(glob.glob("data/items/*.jsonl")):
        raw = [json.loads(line) for line in open(path, encoding="utf-8")]
        # 남의 보도만 묶는다. A등급(우리 데이터)과 출처 없는 글(우리 요약)은 건드리지 않는다.
        news = [d for d in raw if d["grade"] != "A" and d.get("source_url")]
        if not news:
            continue

        reps = cluster_batch([_to_item(d) for d in news])
        by_id = {r.id: r for r in reps}
        if len(reps) == len(news):
            continue

        out = []
        for d in raw:
            if d["grade"] == "A" or not d.get("source_url"):
                out.append(d)
            elif d["id"] in by_id:
                out.append(item_to_dict(by_id[d["id"]]))
        removed += len(news) - len(reps)
        print(f"  {os.path.basename(path)}  {len(raw)} → {len(out)}")
        with open(path, "w", encoding="utf-8") as f:
            for d in out:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"\n  중복 {removed}건을 대표 기사로 합쳤다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
