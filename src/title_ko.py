"""영문 제목을 우리말로.

현지 영문 매체(Beat of Hawaii, VnExpress, NST…)에서 온 기사는 제목이 영문이다.
한국 독자에게 벽이다 — 2026-09-09 실측으로 하와이면 62개 중 57개가 영문이었다.

번역은 매일 해설 에이전트가 한다(docs/DAILY_COMMENTARY.md 5단계). 결과는
data/title_ko.json 에 {id: 한국어 제목} 으로 쌓이고, 빌드가 그것을 입힌다.
값이 "~" 면 "번역하지 않는다"(지역과 무관한 기사) 는 표시다.

주소는 원제목으로 만든다 — 번역이 붙어도 이미 색인된 주소가 안 바뀐다.
"""
from __future__ import annotations

import json
import os
import re
import sys

PATH = os.path.join("data", "title_ko.json")
SKIP = "~"                      # 번역하지 않기로 한 기사
_HANGUL = re.compile(r"[가-힣]")
MAX_LEN = 80


def is_english(title: str) -> bool:
    """알파벳의 7할 넘게가 ASCII 면 영문 제목이다. "KTX 증편" 은 아니다."""
    letters = [c for c in (title or "") if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isascii()) / len(letters) > 0.7


def check(title: str) -> str | None:
    """번역 제목이 쓸 만한가. 문제가 있으면 이유를, 없으면 None."""
    t = (title or "").strip()
    if t == SKIP:
        return None
    if not _HANGUL.search(t):
        return "한글이 없다"
    if "\n" in t:
        return "줄바꿈이 있다"
    if len(t) > MAX_LEN:
        return f"{MAX_LEN}자를 넘는다"
    return None


def load(path: str = PATH) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v.strip() for k, v in data.items() if isinstance(v, str) and v.strip()}


def save(table: dict[str, str], path: str = PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(table.items())), f, ensure_ascii=False, indent=1)
        f.write("\n")


def apply(items, table: dict[str, str]) -> int:
    """번역이 있는 항목의 제목을 바꾼다. 원제목은 title_orig 에 남긴다. 바꾼 개수."""
    n = 0
    for item in items:
        ko = (table.get(item.id) or "").strip()
        if not ko or ko == SKIP or ko == item.title or check(ko):
            continue
        item.title_orig = item.title
        item.title = ko
        n += 1
    return n


def todo(items, table: dict[str, str], limit: int | None = None) -> list[dict]:
    """번역이 필요한 영문 제목. 표에 있는 것(건너뛰기 포함)은 뺀다."""
    rows = []
    for item in items:
        if item.id in table or not is_english(item.title):
            continue
        rows.append({"id": item.id, "region": item.region, "title": item.title,
                     "summary": (item.summary or "")[:200],
                     "source": item.source_name})
    return rows[:limit] if limit else rows


def _resolve(key: str, items) -> str | None:
    """앞 8자만 적어도 된다. 유일하게 맞는 id 하나로 푼다."""
    if items is None:
        return key
    ids = [i.id for i in items if i.id == key or i.id.startswith(key)]
    if len(ids) == 1:
        return ids[0]
    return None


def merge(path_in: str, path: str = PATH, items=None) -> tuple[int, list[str]]:
    """새 번역 파일을 표에 합친다. 검사에 걸린 것은 빼고 이유를 돌려준다."""
    table = load(path)
    with open(path_in, encoding="utf-8") as f:
        new = json.load(f)
    added, errors = 0, []
    for key, value in new.items():
        err = check(value)
        if err:
            errors.append(f"{key[:8]}: {err}")
            continue
        full = _resolve(key, items)
        if not full:
            errors.append(f"{key[:8]}: 맞는 기사가 없거나 여럿이다")
            continue
        table[full] = value.strip()
        added += 1
    save(table, path)
    return added, errors


def _recent_items():
    from datetime import datetime
    from src.build import KST, load_recent_items, one_roundup_per_week
    today = datetime.now(KST).isoformat()[:10]
    return one_roundup_per_week(load_recent_items(os.path.join("data", "items"), today))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["todo"]:
        limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
        print(json.dumps(todo(_recent_items(), load(), limit), ensure_ascii=False, indent=1))
        return 0
    if argv[:1] == ["merge"] and len(argv) == 2:
        added, errors = merge(argv[1], items=_recent_items())
        print(f"합침 {added}건" + (f" · 거른 것 {len(errors)}건: " + "; ".join(errors) if errors else ""))
        return 1 if errors else 0
    print("쓰는 법: python -m src.title_ko todo [--limit N] | merge <파일.json>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
