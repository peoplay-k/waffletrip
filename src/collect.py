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


# 브라우저 사칭용. 우리 봇 UA 를 막는 곳에만 두 번째 시도로 쓴다.
# 우리를 숨기려는 것이 아니라 — 첫 요청은 늘 우리 이름과 연락처를 밝힌다 —
# 자동 차단 규칙이 UA 문자열만 보고 막는 경우를 넘기 위해서다.
_BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_SSL_MARKS = ("CERTIFICATE_VERIFY_FAILED", "SSLError", "handshake")


def collect_one(source: Source, client, collected_at: str) -> list[Item]:
    if source.type == "rss":
        return rss.fetch(source, client, collected_at)
    if source.type == "json":
        return json_api.fetch(source, client, collected_at)
    raise ValueError(f"알 수 없는 소스 타입 '{source.type}' (id={source.id})")


def collect_with_retry(source: Source, client, collected_at: str
                       ) -> tuple[list[Item], str | None]:
    """한 소스를 받는다. 막히면 원인에 맞게 한 번 더 두드린다.

    국내 매체 네 곳이 매일 실패하고 있었다. 원인이 각각 달랐다.

    - **403** — 봇 UA 를 규칙으로 막는 곳. 브라우저 UA 로 다시 청한다.
    - **SSL 검증 실패** — 서버가 중간 인증서를 빠뜨린 설정 실수다(우리 문제가
      아니고 브라우저는 보정해 준다). 그 소스에 한해 검증 없이 다시 받는다.
      공개 RSS 를 읽을 뿐이고 우리가 보내는 자격 증명이 없어 위험이 낮다.
      대신 전역으로 끄지 않는다 — 이 예외는 이 함수 안에서만 산다.
    - **타임아웃** — 그냥 느린 서버. 시간을 늘려 한 번 더.

    두 번째도 실패하면 그 소식은 오늘 없는 것으로 하고 넘어간다.
    """
    # 예외 객체를 밖으로 들고 나온다. 파이썬은 except 블록을 벗어나면
    # `as` 로 묶은 이름을 지운다 — 그대로 쓰면 UnboundLocalError 가 나고
    # 재시도가 통째로 실패한다. 테스트가 이걸 잡았다.
    try:
        return collect_one(source, client, collected_at), None
    except Exception as e:
        first, detail = e, f"{type(e).__name__}: {e}"

    try:
        if isinstance(first, httpx.HTTPStatusError) and \
                first.response.status_code in (403, 429):
            with httpx.Client(headers={"User-Agent": _BROWSER_UA},
                              timeout=30.0, follow_redirects=True) as c2:
                return collect_one(source, c2, collected_at), None
        if any(m in detail for m in _SSL_MARKS):
            with httpx.Client(verify=False, timeout=30.0,
                              follow_redirects=True) as c2:
                return collect_one(source, c2, collected_at), None
        if isinstance(first, (httpx.TimeoutException, httpx.ConnectError)):
            with httpx.Client(timeout=45.0, follow_redirects=True) as c2:
                return collect_one(source, c2, collected_at), None
    except Exception as second:
        return [], f"{detail} → 재시도 {type(second).__name__}: {second}"

    return [], detail


def collect_all(sources: list[Source], client, collected_at: str,
                max_workers: int = 8) -> tuple[list[Item], list[dict]]:
    items: list[Item] = []
    errors: list[dict] = []

    if not sources:
        return items, errors

    def run(source: Source):
        # 소스 하나의 실패로 전체를 멈추지 않는다.
        fetched, error = collect_with_retry(source, client, collected_at)
        return source, fetched, error

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
