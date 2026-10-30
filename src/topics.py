"""기사를 편집 부문으로 가른다.

피플로드는 문화 전문 매체이고 그 아래 두 채널이 있다 — 여행과 연예.

  여행: 뉴스 · 업계·피플 · 기획·연재 · 통계·리포트
  문화: 영화 · 방송·드라마 · 음악 · 공연·전시 · 스타의 여행

2026-09-25 사장님: "카테고리가 너무 많아, 합칠 게 많다." 여행 일곱(여행BIZ·이슈·동향·
관광정책·기획·연재·국제·피플·오피니언·통계·리포트)을 넷으로, 연예 다섯(영화·드라마·방송·
음악·공연·인물·스타의 여행)을 셋으로 합쳤다. 옛 부문 id 는 TOPIC_ALIASES·ENT_ALIASES 로
새 부문에 붙고, 옛 주소(/issue/ /ent/drama/ …)는 새 주소로 넘어가는 쪽을 따로 낸다.
2026-10-28 사장님: 연예 → 문화, 부문은 영화 · 방송·드라마 · 음악 · 공연·전시 · 스타의 여행.
옛 '영화·드라마'·'음악·공연'으로 저장된 기사는 ent_category_of 가 제목으로 다시 가른다.

"스타의 여행"은 두 채널이 만나는 자리다 — 촬영지, 스타가 간 곳, 드라마 로케이션,
해외 공연 원정. 여행 매체도 연예 매체도 잘 안 다루는 자리라 우리만 쓸 수 있는
기사가 여기서 나온다. (2026-09-16 편집국장: "여행은 배경, 엔터가 주인공".)

부문은 저장하지 않고 렌더 시점에 계산한다. Item 에 필드를 늘리면 기존 jsonl 을
전부 옮겨야 하는데, 분류 규칙은 앞으로도 손볼 것이라 그때마다 과거 데이터가
어긋난다. 규칙이 바뀌면 다음 빌드에 전체가 따라온다.
연예 기사만은 예외로 `category` 를 저장한다 — 편집실에서 사람이 고르는 값이라
규칙이 아니라 결정이고, 규칙으로는 영화 기사와 배우 인터뷰를 가를 수 없다.
"""
from __future__ import annotations

import re

from src import site_config as _sc

# (id, 이름, 설명) — 표시 순서가 곧 네비 순서다. 2026-10-30 부터 정본은 config/site.json
# (travel_sections) — 편집실에서 사장님이 이름·순서·숨김을 바꾸고 새 부문을 만든다.
# 숨긴 부문은 여기 없다. 그 부문으로 갈 기사는 첫 부문으로 간다(_travel).
TOPICS = _sc.travel_sections(_sc.CONFIG)
TOPIC_NAMES = {tid: name for tid, name, _ in TOPICS}
TOPIC_DESCS = {tid: desc for tid, _, desc in TOPICS}
# 옛 부문 → 새 부문. 규칙과 옛 주소가 이 표를 거친다.
TOPIC_ALIASES = {"issue": "news", "world": "news", "policy": "news", "people": "biz"}

# 연예 부문. 여행 쪽 people(피플·오피니언)과 겹치지 않게 인물은 star 다.
# 경로는 /ent/<id>/ 라 여행 부문 id 와 같아도 충돌하지 않지만, 코드에서
# 부문 id 하나로 채널을 알 수 있게 겹치지 않는 이름을 골랐다.
# 2026-10-30 부터 정본은 config/site.json(culture_sections). 숨긴 부문은 여기 없다.
ENT_TOPICS = _sc.culture_sections(_sc.CONFIG)
ENT_TOPIC_NAMES = {tid: name for tid, name, _ in ENT_TOPICS}
ENT_TOPIC_DESCS = {tid: desc for tid, _, desc in ENT_TOPICS}
# 옛 연예 부문 → 새 부문. 편집실·소스·초안이 옛 id 를 써도 여기로 붙는다.
# 2026-10-28 사장님: "문화 — 영화, 방송-드라마, 음악, 공연-전시, 스타의 여행".
# 옛 drama(드라마·방송)는 영화가 아니라 방송·드라마로 간다.
ENT_ALIASES = dict(_sc.CONFIG.get("culture_aliases") or {})
# 부문을 모를 때 가는 곳. 스타의 여행이 숨겨지거나 지워졌으면 첫 부문.
ENT_DEFAULT = "startrip" if "startrip" in ENT_TOPIC_NAMES else ENT_TOPICS[0][0]


def ent_canonical(cat: str) -> str:
    """부문 id 를 정본으로. 옛 id 는 새 id 로, 모르는 값은 빈 문자열."""
    cat = (cat or "").strip()
    cat = ENT_ALIASES.get(cat, cat)
    return cat if cat in ENT_TOPIC_NAMES else ""
# 교차 부문 id. 홈·문서에서 이름으로 부르지 않게 한 곳에 둔다.
STARTRIP = "startrip"

ALL_TOPIC_NAMES = {**TOPIC_NAMES, **ENT_TOPIC_NAMES}

# 한글은 조사가 붙어 오므로 부분일치, 영문은 단어 경계로 본다.
# 영문을 부분일치로 두면 air 가 chair 에, eat 가 great 에 걸린다.
_RULES: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("policy",
     ("관광청", "관광공사", "지자체", "정부", "부처", "정책", "협약", "조례",
      "인허가", "규제", "비자", "입국"),
     ("tourism board", "government", "authority", "ministry", "policy",
      "regulation", "visa", "immigration")),
    ("people",
     ("인터뷰", "대표", "사장", "취임", "선임", "칼럼", "기고", "오피니언", "인사"),
     ("interview", "opinion", "column", "appointed", "ceo")),
    ("biz",
     ("항공사", "여행사", "랜드사", "호텔", "리조트", "취항", "노선", "증편",
      "감편", "운항", "예약", "플랫폼", "실적", "매출", "제휴", "출시", "판매"),
     ("airline", "airlines", "hotel", "hotels", "resort", "resorts", "route",
      "routes", "flight", "flights", "booking", "revenue", "partnership",
      "launch", "operator")),
    ("issue",
     ("태풍", "기상", "경보", "주의보", "안전", "사고", "지진", "폐쇄", "통제",
      "혼잡", "축제", "행사", "개장", "재개"),
     ("storm", "hurricane", "typhoon", "alert", "warning", "closed", "closure",
      "festival", "reopen", "quake", "crowd")),
)

_MOVIE_WORDS = ("영화", "개봉", "시사회", "제작발표회", "박스오피스", "관객", "감독", "영화제",
                "칸", "베니스", "베네치아", "토론토", "은사자", "극장")
_DRAMA_WORDS = ("드라마", "예능", "방송", "OTT", "넷플릭스", "티빙", "디즈니+", "웨이브",
                "시청률", "종영", "첫방", "회차", "시즌")
_STAGE_WORDS = ("뮤지컬", "연극", "오페라", "발레", "무용", "오케스트라", "교향악", "클래식",
                "전시", "展", "미술관", "박물관", "갤러리", "비엔날레", "아트페어")
_MUSIC_WORDS = ("앨범", "컴백", "음원", "신곡", "차트", "빌보드", "콘서트", "쇼케이스", "가수",
                "아이돌", "밴드", "OST")

# 연예 기사에 category 가 비어 올 때만 쓰는 보조 규칙. 편집실이 고른 값이 늘 이긴다.
# 교차 부문(startrip)이 먼저다 — "촬영지"가 있으면 영화 기사여도 여행 쪽이 살아야 한다.
# 2026-10-30 부터 정본은 config/site.json(culture_rules) — 순서대로, 먼저 걸리는 줄이 이긴다.
_ENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = _sc.culture_rules(_sc.CONFIG)

def _hit(text: str, korean: tuple[str, ...], english: tuple[str, ...]) -> bool:
    if any(w in text for w in korean):
        return True
    lowered = text.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", lowered) for w in english)


def _any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def is_ent(item) -> bool:
    return getattr(item, "channel", "travel") == "ent"


def ent_category_of(item) -> str:
    """연예 기사의 부문. 편집실이 정한 category 가 있으면 그것, 없으면 제목으로 추정,
    그래도 모르면 인물."""
    raw = (getattr(item, "category", "") or "").strip()
    cat = ent_canonical(raw)
    text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}"
    # 옛 '영화·드라마'(movie)·'음악·공연'(music)으로 저장된 기사를 새 부문으로 가른다.
    # 제목이 분명히 다른 쪽일 때만 옮긴다 — 애매하면 편집실이 고른 값을 둔다.
    if cat == "movie" and _any(text, _DRAMA_WORDS) and not _any(text, _MOVIE_WORDS):
        return "tv"
    if cat == "music" and _any(text, _STAGE_WORDS) and not _any(text, _MUSIC_WORDS):
        return "stage"
    if cat:
        return cat
    for topic_id, korean in _ENT_RULES:
        if any(w in text for w in korean):
            return ent_canonical(topic_id) or ENT_DEFAULT
    return ENT_DEFAULT


def topic_of(item) -> str:
    """기사의 부문.

    연예 기사는 채널이 부문을 정한다 — 여행 규칙(항공·관광청…)을 태우지 않는다.
    여행 기사는 등급이 부문을 이긴다 — 우리가 만든 데이터(A)와 우리가 쓴 기사(C)는
    소재가 무엇이든 그 부문에 속한다.
    어디에도 안 걸리면 국제로 보낸다. 우리 기사는 전부 해외발이고,
    버리면 지면에서 통째로 빠진다.
    """
    if is_ent(item):
        return ent_category_of(item)
    # 편집실에서 부문을 직접 골랐으면 그것(2026-10-30). 사장님이 새로 만든 부문은 이 길로만 채워진다.
    chosen = getattr(item, "topic", "") or ""
    if chosen in TOPIC_NAMES:
        return chosen
    return _travel(_travel_rule(item))


def _travel(tid: str) -> str:
    """규칙이 고른 부문이 숨겨졌거나 지워졌으면 첫 부문으로 보낸다 — 기사가 지면에서 사라지지 않게."""
    return tid if tid in TOPIC_NAMES else TOPICS[0][0]


def _travel_rule(item) -> str:
    if getattr(item, "grade", "") == "A":
        return "data"
    # 우리가 만든 데이터 기사는 등급이 C(자체 생산)지만 성격은 통계·리포트다.
    # section 이 data 면 그쪽으로 보낸다.
    if getattr(item, "section", "") == "data":
        return "data"
    if getattr(item, "grade", "") == "C":
        return "feature"
    if getattr(item, "section", "") == "flight":
        return "biz"

    text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}"
    for topic_id, korean, english in _RULES:
        if _hit(text, korean, english):
            return TOPIC_ALIASES.get(topic_id, topic_id)
    return TOPIC_ALIASES["world"]


def group_by_topic(items) -> dict:
    """여행 기사를 여행 부문으로 묶는다. 연예 기사는 group_by_ent_topic 이 맡는다.

    두 채널을 한 사전에 넣지 않는 이유: 부문 페이지·네비가 채널별로 따로 그려지고,
    빈 연예 부문이 여행 네비에 섞이면 안 되기 때문이다.
    """
    out: dict[str, list] = {tid: [] for tid, _, _ in TOPICS}
    for item in items:
        if is_ent(item):
            continue
        out[topic_of(item)].append(item)
    return out


def group_by_ent_topic(items) -> dict:
    """연예 기사를 연예 부문으로 묶는다. 부문마다 칸이 있다 — 빈 칸은 그리는 쪽이 뺀다."""
    out: dict[str, list] = {tid: [] for tid, _, _ in ENT_TOPICS}
    for item in items:
        if is_ent(item):
            out[ent_category_of(item)].append(item)
    return out
