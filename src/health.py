"""파이프라인이 조용히 죽는 것을 막는다.

인수인계 문서가 "운영하다 터진다면 여기서 터진다" 1순위로 꼽은 곳이다 —
05시에 아무 일도 안 일어나도 아무도 모른다. GitHub Actions 는 잡이 **실패해야**
메일을 보내므로, 이상을 발견하면 조용히 넘어가지 않고 exit 1 로 죽는다.

세 가지를 본다.

1. **오늘 수집 0건** — 즉시 실패. 전 소스가 막혔거나 네트워크가 죽은 것이다.
2. **N일 연속 발행 0건** — 실패. 수집은 되는데 편집이 전부 걷어내는 상태이고,
   증상이 "에러"가 아니라 "기사가 점점 안 실린다"로 나타나 눈치채기 어렵다.
3. **같은 소스가 N일 연속 실패** — 경고만. 소스 하나가 죽어도 신문은 나가야 한다.

기록은 data/health.json 에 남기고 최근 30일만 유지한다.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

FAIL_AFTER_EMPTY_DAYS = 3      # 발행 0건이 이만큼 이어지면 실패
WARN_AFTER_SOURCE_FAILS = 3    # 소스 연속 실패 경고 기준
KEEP_DAYS = 30


def _read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def snapshot(data_dir: str, day: str) -> dict:
    """오늘 하루가 어땠는지 한 줄로 요약한다."""
    raw_dir = os.path.join(data_dir, "raw", day)
    collected = len(_read_json(os.path.join(raw_dir, "items.json"), []))
    errors = _read_json(os.path.join(raw_dir, "_errors.json"), [])

    items_path = os.path.join(data_dir, "items", f"{day}.jsonl")
    published = 0
    if os.path.exists(items_path):
        with open(items_path, encoding="utf-8") as f:
            published = sum(1 for line in f if line.strip())

    return {
        "date": day,
        "collected": collected,
        "published": published,
        "failed_sources": sorted(
            {e.get("source_id", "?") for e in errors if isinstance(e, dict)}),
    }


def update_history(path: str, today: dict) -> list[dict]:
    history = [h for h in _read_json(path, {}).get("history", [])
               if isinstance(h, dict) and h.get("date") != today["date"]]
    history.append(today)
    history.sort(key=lambda h: h.get("date", ""))
    cutoff = (datetime.now(KST).date() - timedelta(days=KEEP_DAYS)).isoformat()
    history = [h for h in history if h.get("date", "") >= cutoff]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"history": history}, f, ensure_ascii=False, indent=2)
    return history


def diagnose(history: list[dict],
             empty_days: int = FAIL_AFTER_EMPTY_DAYS,
             source_days: int = WARN_AFTER_SOURCE_FAILS) -> tuple[list[str], list[str]]:
    """(치명, 경고) 를 돌려준다. 치명이 하나라도 있으면 잡을 죽인다."""
    fatal: list[str] = []
    warn: list[str] = []
    if not history:
        return fatal, warn

    today = history[-1]
    if today["collected"] == 0:
        fatal.append("오늘 수집이 0건이다. 전 소스가 막혔거나 네트워크가 죽었다.")

    recent = history[-empty_days:]
    if len(recent) >= empty_days and all(h.get("published", 0) == 0 for h in recent):
        fatal.append(
            f"{empty_days}일 연속 발행 0건이다. 수집은 되는데 편집이 전부 걷어내고 "
            f"있을 수 있다 — 중복 가드가 과하게 잡는지 본다.")

    tail = history[-source_days:]
    if len(tail) >= source_days:
        common = set(tail[0].get("failed_sources") or [])
        for h in tail[1:]:
            common &= set(h.get("failed_sources") or [])
        for source_id in sorted(common):
            warn.append(f"소스 '{source_id}' 가 {source_days}일 연속 실패했다.")

    return fatal, warn


def main(data_dir: str = "data") -> int:
    day = datetime.now(KST).date().isoformat()
    today = snapshot(data_dir, day)
    history = update_history(os.path.join(data_dir, "health.json"), today)
    fatal, warn = diagnose(history)

    print(f"건강검진 {day}: 수집 {today['collected']}건 · "
          f"발행 {today['published']}건 · 소스실패 {len(today['failed_sources'])}개")
    for w in warn:
        print(f"  경고 {w}", file=sys.stderr)
    for f in fatal:
        print(f"  치명 {f}", file=sys.stderr)
    if fatal:
        print("\n파이프라인이 정상이 아니다. 잡을 실패로 끝내 알림을 띄운다.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
