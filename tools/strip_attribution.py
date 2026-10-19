"""기사 본문에서 매체 인용 문구를 걷어낸다 — 원고와 발행 기록을 함께.

    python tools/strip_attribution.py            # 무엇이 남는지 보고만 한다
    python tools/strip_attribution.py --apply    # 원고(content/review)와 발행 기록(data/items) 을 고친다

해설 본문은 발행 때 data/items/<날짜>.jsonl 로 복사되고 지면은 그쪽을 읽는다.
그래서 원고만 고치면 라이브가 안 바뀐다. 원고의 published_id 로 발행 기록을 찾아
같은 본문·요약으로 맞춘다. 출처 줄(**출처** · …)은 건드리지 않는다.
"""
from __future__ import annotations

import glob
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.attribution import find_media_attribution, media_names, strip_media_attribution  # noqa: E402
from src.publish_drafts import _body_text, _split, _summary_of  # noqa: E402


def _write_md(path: str, front: dict, body: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        yaml.safe_dump(front, f, allow_unicode=True, sort_keys=False)
        f.write("---\n")
        f.write(body.lstrip("\n"))


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    review = "content/review"
    fixed: dict[str, tuple[str, str]] = {}      # published_id → (body_md, summary)
    left = 0
    for path in sorted(glob.glob(os.path.join(review, "*.md"))):
        raw = open(path, encoding="utf-8").read()
        front, body = _split(raw)
        names = media_names(body)
        new_body = strip_media_attribution(body, names)
        summary = front.get("summary") or ""
        new_summary = strip_media_attribution(summary, names) if summary else summary
        if apply and (new_body != body or new_summary != summary):
            if summary:
                front["summary"] = new_summary
            _write_md(path, front, new_body.lstrip("\n"))
        pid = front.get("published_id")
        if pid:
            text = _body_text(new_body)
            fixed[pid] = (text, _summary_of({"summary": new_summary}, text))
        rest = find_media_attribution(new_body, names) + find_media_attribution(new_summary, names)
        if rest:
            left += len(rest)
            print(f"[남음] {os.path.basename(path)}")
            for s in rest:
                print(f"    {s[:160]}")

    changed = 0
    if apply:
        for jl in sorted(glob.glob("data/items/*.jsonl")):
            lines = open(jl, encoding="utf-8").read().splitlines()
            out, dirty = [], False
            for line in lines:
                try:
                    d = json.loads(line)
                except ValueError:
                    out.append(line)
                    continue
                if d.get("id") in fixed:
                    body_md, summary = fixed[d["id"]]
                    if d.get("body_md") != body_md or d.get("summary") != summary:
                        d["body_md"], d["summary"] = body_md, summary
                        dirty = True
                        changed += 1
                    line = json.dumps(d, ensure_ascii=False)
                out.append(line)
            if dirty:
                with open(jl, "w", encoding="utf-8") as f:
                    f.write("\n".join(out) + "\n")
    print(f"\n남은 매체 인용 문장 {left}개" + (f" · 발행 기록 {changed}건 갱신" if apply else ""))
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
