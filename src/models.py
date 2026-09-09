"""파이프라인 전체가 주고받는 자료형.

이 모듈은 아무것도 import 하지 않는다(표준 라이브러리 제외).
수집·편집·렌더가 전부 여기에 의존하므로 의존성이 한 방향으로만 흐른다.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

GRADES = ("A", "B", "C")
SECTIONS = ("flight", "news", "data", "promo")
REGIONS = ("guam", "saipan", "hawaii", "vietnam", "kota", "laos", "jeju",
           "japan", "thailand", "taiwan")
STATUSES = ("draft", "approved", "published")

# 지역의 한글 이름. 여기가 정본이다 — 모듈마다 따로 적어두면 지역을 늘릴 때
# 한 곳만 고치게 되고, 그러면 지면에 "이번 주 japan에서 나온 소식"처럼
# 영문 키가 그대로 나간다. 실제로 그렇게 나갔다.
REGION_NAMES = {
    "guam": "괌", "saipan": "사이판", "hawaii": "하와이",
    "vietnam": "베트남", "kota": "코타키나발루", "laos": "라오스",
    "jeju": "제주", "japan": "일본", "thailand": "태국", "taiwan": "대만",
}

# 추적용 쿼리 파라미터 — 같은 기사인데 URL 만 달라 보이게 만드는 주범
_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "igshid", "ref", "ref_src", "spm"}

_PUNCT = re.compile(r"[^\w가-힣]+", re.UNICODE)


@dataclass
class Item:
    id: str
    grade: str
    region: str
    section: str
    title: str
    summary: str
    source_name: str
    source_url: str
    published_at: str
    collected_at: str
    status: str
    title_hash: str
    body_md: str | None = None
    photo: str | None = None          # /img/... 웹 경로. 승인된 사진만 들어온다
    title_orig: str | None = None     # 번역 전 원제목. 빌드 때만 채워진다(주소·병기용)
    related: list[str] = field(default_factory=list)


def normalize_url(url: str) -> str:
    """추적 파라미터와 프래그먼트를 떼고 호스트를 소문자로 만든다.

    같은 기사가 서로 다른 URL 로 두 번 들어오는 것을 막기 위한 것이므로,
    의미 있는 쿼리(id=7 등)는 남긴다.
    """
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_KEYS
        and not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)
    ]
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return urlunsplit((
        parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "",
    ))


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def make_id(source_url: str, title: str, published_at: str) -> str:
    """항목의 영구 식별자.

    URL 이 있으면 URL 만으로 정한다 — 같은 기사의 제목이 나중에 수정돼도
    같은 항목으로 인식해야 재발행을 막을 수 있다.
    """
    normalized = normalize_url(source_url)
    if normalized:
        return _sha1(normalized)
    return _sha1(f"{title}|{published_at}")


def title_hash(title: str) -> str:
    """공백·구두점을 무시한 제목 해시. 완전 동일 제목 판정용."""
    return _sha1(_PUNCT.sub("", title).lower())


# 회사명 꼬리. 매체마다 "에어로케이" 와 "에어로케이항공" 을 섞어 써서 같은
# 보도자료가 서로 다른 사건으로 갈렸다. 실측(2026-09-08): 청주~타이베이 취항
# 3주년 기사가 자카드 0.667 로 임계값 0.7 에 0.033 모자라 지면에 두 번 실렸다.
_ORG_SUFFIX = re.compile(r"(항공사|항공|그룹)$")
# 꼬리를 뗀 몸통이 두 글자 이하면 떼지 않는다. "제주항공"→"제주" 는 지역명과
# 겹쳐 제주 기사 전체를 한 건으로 삼켜버리고, "대한항공"→"대한", "일본항공"→
# "일본" 도 마찬가지다. 실측에서 세 글자 이상만 떼면 아시아나·이스타·에어로케이·
# 썬푸꾸옥·파라타·타이비엣젯이 정확히 잡히고 위 셋은 온전히 남는다.
_ORG_STEM_MIN = 3


def _strip_org_suffix(token: str) -> str:
    stem = _ORG_SUFFIX.sub("", token)
    return stem if len(stem) >= _ORG_STEM_MIN else token


def title_tokens(title: str) -> set[str]:
    """유사도 비교용 토큰. 조사·한 글자 단어는 잡음이라 버린다.

    ★한 자리 숫자는 예외로 남긴다. 버리면 "Update 1" 과 "Update 5" 의 토큰이
    완전히 같아져 순차 속보가 한 건으로 병합된다. 실측에서 태풍 속보 5·4·3·1호가
    하나로 묶였고, 두 자리인 11·12호는 멀쩡히 분리되는 비일관이 드러났다.
    """
    return {_strip_org_suffix(t) for t in _PUNCT.split(title.lower())
            if len(t) > 1 or t.isdigit()}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def item_to_dict(item: Item) -> dict:
    return {
        "id": item.id, "grade": item.grade, "region": item.region,
        "section": item.section, "title": item.title, "summary": item.summary,
        "source_name": item.source_name, "source_url": item.source_url,
        "published_at": item.published_at, "collected_at": item.collected_at,
        "status": item.status, "title_hash": item.title_hash, "photo": item.photo,
        "body_md": item.body_md, "related": list(item.related),
    }


def item_from_dict(d: dict) -> Item:
    return Item(
        id=d["id"], grade=d["grade"], region=d["region"], section=d["section"],
        title=d["title"], summary=d["summary"], source_name=d["source_name"],
        source_url=d["source_url"], published_at=d["published_at"],
        collected_at=d["collected_at"], status=d["status"],
        title_hash=d["title_hash"], body_md=d.get("body_md"),
        photo=d.get("photo"),
        related=list(d.get("related") or []),
    )
