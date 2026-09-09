"""이미 지면에 실린 도박 스팸을 걷어낸다. 한 번만 쓰는 도구.

2026-09-09 실측: 구글뉴스 "호텔" 검색 피드로 카지노 홍보 글이 들어와 9월 3일부터
14건이 B등급 기사로 실렸고 13쪽이 사이트맵에 올라가 있었다. 전부 og:site_name 이
"Histoire pour tous" 로 풀리는 탈취 사이트다. 여행 신문이 도박 스팸에 링크를
걸고 있었다. 스팸 게이트(src/relevance.is_spam)를 넣었지만 이미 쌓인 것은
파일에서 빼야 사라진다. 발행 이력에는 id 가 남으므로 다시 실리지 않는다.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.relevance import is_spam  # noqa: E402


def main() -> int:
    removed = 0
    for path in sorted(glob.glob("data/items/*.jsonl")):
        rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
        keep = [r for r in rows if r.get("grade") == "A" or not r.get("source_url")
                or not is_spam(f"{r.get('title','')} {r.get('summary','')}", r.get("source_name", ""))]
        if len(keep) != len(rows):
            for r in rows:
                if r not in keep:
                    print(f"  뺌 {os.path.basename(path)[:10]} {r.get('source_name','')[:18]:18} {r.get('title','')[:50]}")
            removed += len(rows) - len(keep)
            with open(path, "w", encoding="utf-8") as f:
                for r in keep:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  스팸 {removed}건을 지면에서 뺐다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
