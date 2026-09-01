#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""와플트립 전체 상태를 한 화면에 보여준다.

이 도구의 목적은 **무엇이 막혀 있고 그게 누구 손에 있는지**를 분명히 하는 것이다.
"진행 상황이 어떻게 되나"를 물어볼 필요가 없게 만드는 것이 목표다.

    python3 tools/status.py
    python3 tools/status.py --no-net    네트워크 조회 없이(빠름)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAS = "/Volumes/GUAMPLAY"
PAGES_IPS = {"185.199.108.153", "185.199.109.153",
             "185.199.110.153", "185.199.111.153"}

OK, WAIT, BLOCK = "✓", "…", "✗"


def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def read_json(path, default):
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def head(title):
    print(f"\n\033[1m{title}\033[0m")
    print("─" * 66)


def line(mark, label, detail="", owner=""):
    tag = f"  [{owner}]" if owner else ""
    print(f"  {mark} {label:<26} {detail}{tag}")


# ── 1. 배포 ────────────────────────────────────────────────────
def section_deploy(net: bool):
    head("배포")
    blocked = []

    if net:
        gh = os.path.expanduser("~/bin/gh")
        vis = run([gh, "repo", "view", "peoplay-k/waffletrip",
                   "--json", "visibility", "--jq", ".visibility"])
        line(OK if vis else BLOCK, "저장소", vis or "확인 실패")

        pages = run([gh, "api", "repos/peoplay-k/waffletrip/pages",
                     "--jq", ".cname"])
        line(OK if pages else BLOCK, "Pages", f"도메인 {pages}" if pages else "미설정")

        conclusion = run([gh, "run", "list", "--repo", "peoplay-k/waffletrip",
                          "--limit", "1", "--json", "conclusion",
                          "--jq", ".[0].conclusion"])
        line(OK if conclusion == "success" else WAIT, "최근 자동 실행",
             conclusion or "기록 없음")

        a_records = set(run(["dig", "+short", "waffletrip.com", "A"]).split())
        if a_records & PAGES_IPS:
            line(OK, "DNS", "GitHub Pages 로 연결됨")
        elif a_records:
            line(BLOCK, "DNS", f"다른 곳을 가리킴: {', '.join(sorted(a_records))}")
            blocked.append(("DNS 를 GitHub Pages 로 바꾼다", "대표님"))
        else:
            line(BLOCK, "DNS", "A레코드 없음 — 사이트가 아직 안 열린다")
            blocked.append(("카페24 로그인 → DNS 레코드 입력", "대표님 → 그다음 나"))
    else:
        line(WAIT, "네트워크 조회 생략", "--no-net")
    return blocked


# ── 2. 파이프라인 ──────────────────────────────────────────────
def section_pipeline():
    head("파이프라인")
    blocked = []

    health = read_json("data/health.json", {}).get("history", [])
    if health:
        last = health[-1]
        recent = health[-3:]
        empty = all(h.get("published", 0) == 0 for h in recent) and len(recent) >= 3
        line(BLOCK if empty else OK, "건강검진",
             f"{last['date']} 수집 {last['collected']}건 · 발행 {last['published']}건")
        if empty:
            blocked.append(("3일 연속 발행 0건 — 중복 가드 점검", "나"))
    else:
        line(WAIT, "건강검진", "아직 기록 없음")

    sources = 0
    try:
        import yaml
        with open(os.path.join(ROOT, "sources.yaml"), encoding="utf-8") as f:
            data = yaml.safe_load(f)
        sources = sum(1 for s in data.get("sources", []) if s.get("enabled"))
    except Exception:
        pass
    line(OK if sources else BLOCK, "활성 소스", f"{sources}개")

    review = os.path.join(ROOT, "content/review")
    drafts = approved = 0
    if os.path.isdir(review):
        import yaml
        for name in os.listdir(review):
            if not name.endswith(".md"):
                continue
            try:
                with open(os.path.join(review, name), encoding="utf-8") as f:
                    front = yaml.safe_load(f.read().split("---")[1]) or {}
            except Exception:
                continue
            status = front.get("status")
            if status == "draft":
                drafts += 1
            elif status == "approved":
                approved += 1
    line(OK if approved else WAIT, "해설 초안",
         f"대기 {drafts}건 · 승인 {approved}건")
    if drafts and not approved:
        blocked.append((f"해설 초안 {drafts}건에 본문을 채운다 (재료 필요)",
                        "재료는 대표님 · 집필은 나"))
    return blocked


# ── 3. 콘텐츠 ──────────────────────────────────────────────────
def section_content():
    head("지면")
    items_dir = os.path.join(ROOT, "data/items")
    counts: dict[str, dict[str, int]] = {}
    if os.path.isdir(items_dir):
        for name in sorted(os.listdir(items_dir))[-14:]:
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(items_dir, name), encoding="utf-8") as f:
                for raw in f:
                    if not raw.strip():
                        continue
                    try:
                        d = json.loads(raw)
                    except Exception:
                        continue
                    counts.setdefault(d.get("region", "?"), {}).setdefault(
                        d.get("grade", "?"), 0)
                    counts[d["region"]][d["grade"]] += 1

    sys.path.insert(0, ROOT)
    from src.models import REGIONS
    names = {"guam": "괌", "saipan": "사이판", "hawaii": "하와이",
             "vietnam": "베트남", "kota": "코타키나발루", "laos": "라오스",
             "jeju": "제주"}
    manifest = read_json("assets/photos/manifest.json", {})

    print("  지역            A(데이터)  B(큐레이션)  C(해설)   사진")
    print("  " + "─" * 56)
    thin = []
    for region in REGIONS:
        g = counts.get(region, {})
        photos = len(manifest.get(region) or [])
        b, c = g.get("B", 0), g.get("C", 0)
        if b + c < 3:
            thin.append(names.get(region, region))
        pad = 16 - sum(2 if ord(ch) > 0x2E80 else 1 for ch in names.get(region, region))
        print(f"  {names.get(region, region)}{' ' * pad}"
              f"{g.get('A', 0):>4}{b:>11}{c:>10}{photos:>8}")
    if thin:
        print(f"\n  지면이 얇은 곳: {', '.join(thin)} — 해설 기사로 메워야 한다")
    return []


# ── 4. 사진 ────────────────────────────────────────────────────
def section_photos():
    head("사진")
    blocked = []
    mounted = os.path.isdir(NAS)
    line(OK if mounted else BLOCK, "NAS", NAS if mounted else "마운트 안 됨")
    if not mounted:
        blocked.append((f"Finder → 서버 연결 → smb://PEOPLAY ({NAS})", "대표님"))

    index = read_json("data/photos/index.json", {})
    if index:
        root = index.get("root", "")
        is_nas = root.startswith(NAS)
        # 어디를 훑은 인덱스인지 반드시 밝힌다. 로컬 시험 결과를 NAS 보유량으로
        # 착각하면 "사진 충분하다"고 잘못 판단하게 된다.
        line(OK if is_nas else WAIT, "인덱스",
             f"{index.get('total', 0)}장 · {root}"
             + ("" if is_nas else "  ← NAS 아님(로컬 시험)"))
    else:
        line(WAIT, "인덱스", "아직 없음 — NAS 연결 후 nas_index.py")

    manifest = read_json("assets/photos/manifest.json", {})
    total = sum(len(v or []) for v in manifest.values())
    line(OK if total else WAIT, "승인된 사진", f"{total}장")
    if mounted and not total:
        blocked.append(("사진 선별 → 콘택트시트 검토 → 승인", "내가 선별 · 대표님 확인"))
    return blocked


def main() -> int:
    net = "--no-net" not in sys.argv
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    print(f"\n\033[1m와플트립 상태\033[0m  {now} KST")

    blocked = []
    blocked += section_deploy(net)
    blocked += section_pipeline()
    blocked += section_content()
    blocked += section_photos()

    head("지금 막혀 있는 것")
    if not blocked:
        print("  없다. 매일 05시에 알아서 나간다.")
    else:
        for i, (what, owner) in enumerate(blocked, 1):
            print(f"  {i}. {what}")
            print(f"     └ {owner}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
