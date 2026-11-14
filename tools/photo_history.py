#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""영상·표지에 쓴 사진 기록 — 최근에 쓴 사진은 뒤로 미룬다.

2026-11-14 사장님: "같은 사진 쓰지 말고". 사진 고르는 순서가 고정이라 같은 곳이면
날마다 같은 첫 사진(=표지)이 나왔고, 주간 롱폼 표지와 다낭 쇼츠 표지가 같은 호이안
사진이었다.

기록은 `data/shorts_latest.json` 의 `photo_history` 칸에 둔다. 매일 발행 워크플로가
이 파일을 커밋하므로 다음 날에도 남는다(워크플로 파일은 이 저장소 토큰으로 못 고쳐
새 파일을 커밋 목록에 더할 수 없다). 다른 칸을 쓰는 곳은 write_latest 로 써야
기록이 지워지지 않는다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
LATEST = os.path.join("data", "shorts_latest.json")
KEEP = 600                      # 이만큼만 기억한다(파일이 끝없이 커지지 않게)


def _load(path: str = LATEST) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def history(path: str = LATEST) -> dict[str, str]:
    h = _load(path).get("photo_history") or {}
    return h if isinstance(h, dict) else {}


def fresh_first(paths: list[str], path: str = LATEST) -> list[str]:
    """안 쓴 사진 → 오래전에 쓴 사진 순. 같으면 받은 순서(장소 섞기)를 지킨다."""
    h = history(path)
    return sorted(paths, key=lambda p: (h.get(p, ""), paths.index(p)))


def remember(paths: list[str], path: str = LATEST, now: datetime | None = None) -> None:
    stamp = (now or datetime.now(KST)).isoformat(timespec="seconds")
    data = _load(path)
    h = data.get("photo_history") if isinstance(data.get("photo_history"), dict) else {}
    for p in paths:
        if p:
            h[p] = stamp
    if len(h) > KEEP:
        h = dict(sorted(h.items(), key=lambda kv: kv[1])[-KEEP:])
    data["photo_history"] = h
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def write_latest(fields: dict, path: str = LATEST) -> None:
    """shorts_latest.json 을 새로 쓰되 사진 기록은 이어 간다."""
    h = history(path)
    out = dict(fields)
    if h:
        out["photo_history"] = h
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
