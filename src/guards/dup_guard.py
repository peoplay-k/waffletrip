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
import re
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
        # C(해설)도 id 로만 본다. 해설은 원본 사건을 **일부러** 다시 다루므로
        # 제목이 겹치는 것이 정상이다. 유사도로 보면 우리가 쓴 글이 우리가 실은
        # 원문에 막혀 영원히 못 나간다.
        if item.grade in ("A", "C"):
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


# 포함 판정에 필요한 최소 토큰 수. 두세 단어짜리 제목은 우연히 포함될 수 있다.
CONTAIN_MIN_TOKENS = 4


def contained(a: set[str], b: set[str]) -> bool:
    """짧은 제목이 긴 제목에 통째로 들어 있으면 같은 사건이다.

    "오키나와, 숙박세 도입 확정" 과 "오키나와, 숙박세 도입 확정…전국 첫 '정률제'
    적용" 은 자카드로는 0.5 밖에 안 나와 따로 실렸다. 같은 보도자료를 받은
    매체들이 제목 길이만 달리한 것이다.
    """
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return len(short) >= CONTAIN_MIN_TOKENS and short <= long_


# ── 같은 사건 판정 ─────────────────────────────────────────────────
# 자카드로는 못 잡는 중복이 있다. 같은 보도자료를 매체마다 다른 각도로 뽑으면
# 겹치는 단어 비율이 떨어진다. 실측(2026-09-08): "에어로케이 39만 명 수송" 과
# "에어로케이 대만인 승객 비중 32%" 는 같은 취항 3주년 발표인데 자카드 0.286
# 이었다. 그 결과 대한항공·일본항공 한진칼 기사가 지면에 6건, 다낭 국경절
# 기사가 6건, 진주남강유등축제가 4건 따로 실렸다.
#
# 그래서 비율 대신 **고유한 말이 몇 개나 겹치는지**를 센다. 회사·지명·금액처럼
# 그 사건에만 나오는 말이 넷 이상 겹치면 같은 사건이다.
EVENT_MIN_SHARED = 4

# 날짜는 사건을 가리지 못한다. "9월 2일 연휴" 는 그 주 베트남 기사 전부에
# 들어 있어서, 세지 않으면 서로 다른 기사가 날짜만으로 묶인다.
_CALENDAR = re.compile(r"^\d+[월일년]$")

# 여행 기사면 어디에나 나오는 말. 이것만으로 묶이면 안 된다.
# "first alert forecast" 는 하와이 방송사의 고정 코너명이라 매일 나온다 —
# 실측에서 서로 다른 날의 태풍 예보 두 건이 이 이름 때문에 묶일 뻔했다.
_COMMON_WORDS = frozenset({
    "여행", "관광", "관광객", "관광객들", "항공", "노선", "취항", "운항", "공항",
    "호텔", "예약", "확대", "증편", "신규", "오픈", "운영", "시작", "추진", "도입",
    "한국", "국내", "해외", "연휴", "기간", "동안", "이상의", "수익을", "방문객",
    "first", "alert", "forecast", "travel", "tourism", "hawaii",
    "the", "for", "is", "to", "and", "of", "in", "on", "with", "new",
})


def event_tokens(title: str) -> set[str]:
    """사건을 가리는 말만 남긴다. 날짜와 흔한 여행 낱말은 뺀다."""
    return {t for t in title_tokens(title)
            if t not in _COMMON_WORDS and not _CALENDAR.match(t)}


def _matches(a: str, b: str) -> bool:
    """같은 말로 볼 것인가. 조사가 붙은 형태까지 같이 본다.

    한국어 제목은 "대한항공" 과 "대한항공과" 가 다른 낱말로 잡힌다. 조사를 떼는
    방법은 쓰지 않는다 — "홋카이도"→"홋카이", "고양이"→"고양" 처럼 이름을
    망가뜨린다. 대신 한 글자 차이의 앞부분 일치만 같은 말로 본다.

    한 글자로 제한한 이유: 두 글자까지 허용하면 "제주" 와 "제주항공" 이 같은
    말이 되어 제주 지역 기사와 항공사 기사가 붙는다.
    """
    if a == b:
        return True
    return (abs(len(a) - len(b)) <= 1 and min(len(a), len(b)) >= 2
            and (a.startswith(b) or b.startswith(a)))


def shared_event_words(a: str, b: str) -> int:
    """두 제목이 같은 사건을 가리키는 말을 몇 개나 공유하는가."""
    left, right = event_tokens(a), sorted(event_tokens(b))
    used: set[str] = set()
    count = 0
    for token in sorted(left):
        for other in right:
            if other not in used and _matches(token, other):
                used.add(other)
                count += 1
                break
    return count


def same_event(a: str, b: str) -> bool:
    """제목 둘이 같은 사건을 가리키는가.

    문턱을 넷으로 잡은 근거: 9일치 실측에서 셋으로 낮추면 "일본 소도시 이야기
    ①/②" 같은 연재물과 태풍 순차 속보가 섞였다. 넷에서는 78쌍이 남았고 그중
    남의 보도끼리 잘못 묶인 쌍은 없었다.
    """
    return shared_event_words(a, b) >= EVENT_MIN_SHARED


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
    # 제목을 같이 들고 다니는 이유: same_event 는 비율이 아니라 겹치는 낱말
    # 개수를 세므로 원제목이 필요하다.
    clusters: list[list[tuple[set[str], str]] | None] = []

    for item in items:
        # A등급(우리 사실 데이터)과 출처 없는 글(우리가 쓴 요약)은 클러스터를
        # 받지 않는다. 실측에서 "이번 주 오사카에서 나온 소식 4건" 과 "이번 주
        # 후쿠오카에서 나온 소식 4건" 이 같은 사건으로 잡혔다 — 넣었으면 도시별
        # 요약 페이지가 통째로 사라진다. 지금은 요약을 클러스터링 뒤에 만들어
        # 여기까지 오지 않지만, 순서가 바뀌어도 안전하도록 막아둔다.
        if item.grade == "A" or not item.source_url:
            representatives.append(item)
            clusters.append(None)
            continue

        tokens = title_tokens(item.title)
        for rep, known_list in zip(representatives, clusters):
            if known_list is None or rep.region != item.region:
                continue
            if any(jaccard(tokens, known) >= threshold
                   or contained(tokens, known)
                   or same_event(item.title, known_title)
                   for known, known_title in known_list):
                rep.related.append(item.id)
                known_list.append((tokens, item.title))
                break
        else:
            representatives.append(item)
            clusters.append([(tokens, item.title)])

    return representatives


def filter_unpublished(items: list[Item],
                       index: PublishedIndex) -> tuple[list[Item], list[Item]]:
    fresh: list[Item] = []
    seen: list[Item] = []
    for item in items:
        (seen if index.contains(item) else fresh).append(item)
    return fresh, seen
