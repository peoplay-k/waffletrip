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
SILENT_AFTER_DAYS = 2          # 우리 기사 0편이 이만큼 이어지면 경보(배포 뒤 실패로 알린다)
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
    ours = 0
    if os.path.exists(items_path):
        with open(items_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                published += 1
                try:
                    # 해설·보도자료 정리 — 초안에서 나간 우리 기사는 id 가 c- 로 시작한다
                    ours += json.loads(line).get("id", "").startswith("c-")
                except ValueError:
                    pass

    return {
        "date": day,
        "collected": collected,
        "published": published,
        "ours": ours,
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


def own_silence(history: list[dict], today: str,
                days: int = SILENT_AFTER_DAYS) -> bool:
    """지난 days 일 연속 우리 기사가 0편이었나.

    2026-10-02 부터 남의 기사 인용은 지면에 안 나간다. 그래서 해설 에이전트(매일
    12:17)가 멈추면 지면은 환율·날씨만 남는데, 위 '발행 0건' 검사는 인용까지 세서
    울리지 않는다. 오늘은 빼고 센다 — 아침 실행 때는 에이전트가 아직 안 돌았다.
    'ours' 가 없는 옛 기록은 모르는 날이라 세지 않는다.
    """
    done = [h for h in history
            if h.get("date", "") < today and h.get("ours") is not None]
    tail = done[-days:]
    return len(tail) >= days and all(h["ours"] == 0 for h in tail)


def video_age_days(src: str = os.path.join("static", "video")) -> float | None:
    """홈에 걸린 롱폼이 며칠 묵었나. 영상이 아예 없으면 None.

    2026-09-15 에 사장님이 지적하셨다 — 홈 영상이 9월 6일에 멈춰 있었다.
    아흐레 동안 아무 검사도 울지 않았다. 매일 나오는 신문에서 "이번 주
    여행 뉴스" 가 아흐레 묵은 것은 그냥 틀린 화면이다. 그 사이 화면에
    박힌 환율도 9월 3일 값(855원)이었고 그날 실제 값은 871원이었다.
    """
    meta = os.path.join(src, "peopleroad-week.json")
    if not os.path.exists(meta):
        return None
    try:
        with open(meta, encoding="utf-8") as fh:
            built = json.load(fh).get("built_at")
        if not built:
            return 999.0          # 언제 만든 것인지 안 적혀 있으면 묵은 것으로 본다
        made = datetime.fromisoformat(built)
    except (ValueError, OSError, json.JSONDecodeError):
        return 999.0
    return (datetime.now(KST) - made).total_seconds() / 86400


def main(data_dir: str = "data") -> int:
    day = datetime.now(KST).date().isoformat()
    today = snapshot(data_dir, day)
    history = update_history(os.path.join(data_dir, "health.json"), today)
    fatal, warn = diagnose(history)

    print(f"건강검진 {day}: 수집 {today['collected']}건 · "
          f"발행 {today['published']}건(우리 기사 {today['ours']}편) · "
          f"소스실패 {len(today['failed_sources'])}개")
    age = video_age_days()
    if age is None:
        warn.append("홈 영상이 없다 — 영상 단계가 실패했는지 본다.")
    elif age >= 3:
        fatal.append(f"홈 영상이 {age:.0f}일 묵었다. 매일 다시 구워야 한다.")
    elif age >= 2:
        warn.append(f"홈 영상이 {age:.1f}일 묵었다.")

    # 배포를 막지 않으려고 여기서 죽지 않는다. 워크플로가 배포 뒤 notify 잡에서
    # 이 값을 보고 실패로 끝내 알림 메일을 띄운다.
    if own_silence(history, day):
        warn.append(f"{SILENT_AFTER_DAYS}일 연속 우리 기사(해설·보도자료) 0편이다 — "
                    "12:17 해설 에이전트가 멈췄을 수 있다. 인용이 지면에 안 나가므로 지면이 비어 간다.")
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a", encoding="utf-8") as f:
                f.write("own_silent=true\n")

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
