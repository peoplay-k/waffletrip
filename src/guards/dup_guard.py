"""같은 것을 두 번 내지 않는다.

두 가지 다른 일을 한다.
- cluster_batch: 오늘 들어온 것들 중 같은 사건을 묶는다. 버리지 않고 대표 1건 +
  나머지는 '관련 보도' 링크로 만든다. 여러 매체가 같은 사건을 보도한 것은
  중복이 아니라 그 사건이 중요하다는 신호다.
- filter_unpublished: 과거에 이미 낸 것을 버린다. 이건 진짜 중복이다.

인덱스 파일이 깨져 있으면 예외를 던진다. 읽기 실패를 '중복 없음'으로
해석하면 재발행 사고가 난다.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone

from src.models import Item, jaccard, title_tokens

SIMILARITY_THRESHOLD = 0.7
RECENT_DAYS = 30
# 러너는 UTC 로 돈다. date.today() 를 쓰면 하루 어긋난 컷오프가 생긴다.
KST = timezone(timedelta(hours=9))


class IndexUnavailable(Exception):
    """발행 이력을 읽을 수 없다. 발행을 중단해야 한다."""


class PublishedIndex:
    """발행 이력. id 는 영구 보관하고 제목은 최근 30일만 유지한다.

    id 를 영구 보관하는 이유: 오래된 기사라도 같은 URL 이 다시 들어오면
    재발행이다. 제목을 30일만 유지하는 이유: 유사도 비교 비용이 무한히
    커지는 것을 막기 위해서다.
    """

    def __init__(self, ids: set[str], recent: list[dict]):
        self.ids = ids
        self.recent = recent
        self._token_cache = [
            (r["id"], title_tokens(r["title"]), r.get("region")) for r in recent
        ]

    @classmethod
    def load(cls, path: str) -> "PublishedIndex":
        if not os.path.exists(path):
            return cls(set(), [])  # 최초 실행
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            ids = data.get("ids") or []
            recent = data.get("recent") or []
            # 타입이 틀리면 조용히 이상하게 해석된다. 문자열을 set() 에 넣으면
            # 글자 단위로 쪼개져 중복 판정이 무의미해진다. 발행을 멈춘다.
            if not isinstance(ids, list) or not isinstance(recent, list):
                raise TypeError("ids·recent 는 리스트여야 한다")
            return cls(set(ids), list(recent))
        except Exception as e:
            raise IndexUnavailable(
                f"발행 이력을 읽지 못했다 ({path}): {type(e).__name__}: {e}. "
                f"중복 판정이 불가능하므로 발행을 중단한다.") from e

    def contains(self, item: Item) -> bool:
        """이미 낸 것인가.

        A등급(사실 데이터)은 **id 로만** 판정한다. 제목이 매일 같기 때문이다
        ("오늘의 환율 — 1 USD"). 제목 유사도로 보면 2일차부터 전 지역 환율이
        중복 판정돼 데이터 패널이 영구히 빈다 — 실제로 그랬다.

        제목 비교는 같은 지역끼리만 한다. 다른 곳 이야기는 같은 사건일 수 없다.
        (지역이 기록되지 않은 옛 항목은 비교 대상에 그대로 둔다.)
        """
        if item.id in self.ids:
            return True
        if item.grade == "A":
            return False

        tokens = title_tokens(item.title)
        for _, known, region in self._token_cache:
            if region is not None and region != item.region:
                continue
            if jaccard(tokens, known) >= SIMILARITY_THRESHOLD:
                return True
        return False

    def add(self, item: Item, day: str) -> None:
        self.ids.add(item.id)
        self.recent.append({"id": item.id, "title": item.title, "date": day,
                            "region": item.region, "grade": item.grade})
        self._token_cache.append((item.id, title_tokens(item.title), item.region))

    def save(self, path: str) -> None:
        cutoff = (datetime.now(KST).date() - timedelta(days=RECENT_DAYS)).isoformat()
        # 같은 날 빌드를 두 번 돌리면 같은 id 가 recent 에 두 번 쌓인다. id 로 접는다.
        by_id = {r["id"]: r for r in self.recent if r.get("date", "") >= cutoff}
        pruned = list(by_id.values())
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"ids": sorted(self.ids), "recent": pruned}, f,
                      ensure_ascii=False, indent=2)


def cluster_batch(items: list[Item],
                  threshold: float = SIMILARITY_THRESHOLD) -> list[Item]:
    """배치 안의 같은 사건을 묶는다. 먼저 온 항목이 대표가 된다.

    두 가지는 묶지 않는다.
    - **A등급(사실 데이터)** — 우리가 공공데이터로 만든 값이지 남의 보도가 아니다.
      지역별 "오늘의 환율 — 1 USD" 는 제목이 같아도 서로 다른 항목이다. 실측에서
      이걸 묶는 바람에 사이판·하와이의 환율 패널이 통째로 사라졌다.
    - **지역이 다른 항목** — 다른 곳 이야기는 같은 사건일 수 없다.

    새 항목은 대표의 원제목뿐 아니라 그 클러스터에 이미 흡수된 제목들과도 비교한다
    (연쇄 비교). 대표하고만 비교하면 A~B 유사·B~C 유사인데 A~C 는 임계값 미만인
    사슬형 사건을 놓친다.
    """
    representatives: list[Item] = []
    # None 은 '이 대표는 클러스터를 받지 않는다'(A등급)는 뜻이다.
    cluster_tokens: list[list[set[str]] | None] = []

    for item in items:
        if item.grade == "A":
            representatives.append(item)
            cluster_tokens.append(None)
            continue

        tokens = title_tokens(item.title)
        for rep, known_list in zip(representatives, cluster_tokens):
            if known_list is None or rep.region != item.region:
                continue
            if any(jaccard(tokens, known) >= threshold for known in known_list):
                rep.related.append(item.id)
                known_list.append(tokens)
                break
        else:
            representatives.append(item)
            cluster_tokens.append([tokens])

    return representatives


def filter_unpublished(items: list[Item],
                       index: PublishedIndex) -> tuple[list[Item], list[Item]]:
    fresh: list[Item] = []
    seen: list[Item] = []
    for item in items:
        (seen if index.contains(item) else fresh).append(item)
    return fresh, seen
