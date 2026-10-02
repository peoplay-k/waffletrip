"""기사 내역. 자체 기사 비중을 부풀리지 않고 센다."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
from article_ledger import load_articles, report  # noqa: E402

from src.models import Item, item_to_dict  # noqa: E402


def ours(item_id, day, region="guam", source_name=""):
    stamp = f"{day}T09:00:00+09:00"
    return Item(id=item_id, grade="C", region=region, section="news",
                title=f"기사 {item_id}", summary="", source_name=source_name,
                source_url="", published_at=stamp, collected_at=stamp,
                status="published", title_hash="h")


def test_ledger_counts_kinds_and_own_ratio(tmp_path):
    items = tmp_path / "data" / "items"
    items.mkdir(parents=True)
    rows = [ours("c-1", "2026-10-02"), ours("c-2", "2026-10-03"),
            ours("c-3", "2026-10-03"), ours("d-1", "2026-10-03", source_name="피플로드 데이터팀")]
    (items / "2026-10-03.jsonl").write_text(
        "\n".join(json.dumps(item_to_dict(i), ensure_ascii=False) for i in rows),
        encoding="utf-8")
    review = tmp_path / "review"
    review.mkdir()
    for pid, kind in (("c-1", "취재"), ("c-2", "해설")):
        (review / f"{pid}.md").write_text(
            f"---\npublished_id: {pid}\nkind: {kind}\n---\n본문\n", encoding="utf-8")

    got = load_articles(str(tmp_path / "data"), str(review), "2026-10", "2026-10")
    # 종류가 없는 기사는 자체 기사로 치지 않는다(미분류)
    assert sorted(r["kind"] for r in got) == ["미분류", "자동", "취재", "해설"]
    assert all(r["byline"].endswith("기자") for r in got)
    text = report(got)
    assert "| 2026-10 | 4 | 1 |" in text
    assert "25%" in text
