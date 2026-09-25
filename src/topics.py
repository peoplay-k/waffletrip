"""기사를 편집 부문으로 가른다.

피플로드는 문화 전문 매체이고 그 아래 두 채널이 있다 — 여행과 연예.

  여행: 뉴스 · 업계·피플 · 기획·연재 · 통계·리포트
  연예: 영화·드라마 · 음악·공연 · 스타의 여행

2026-09-25 사장님: "카테고리가 너무 많아, 합칠 게 많다." 여행 일곱(여행BIZ·이슈·동향·
관광정책·기획·연재·국제·피플·오피니언·통계·리포트)을 넷으로, 연예 다섯(영화·드라마·방송·
음악·공연·인물·스타의 여행)을 셋으로 합쳤다. 옛 부문 id 는 TOPIC_ALIASES·ENT_ALIASES 로
새 부문에 붙고, 옛 주소(/issue/ /ent/drama/ …)는 새 주소로 넘어가는 쪽을 따로 낸다.

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

# (id, 이름, 설명) — 표시 순서가 곧 네비 순서다
TOPICS = (
    ("news", "뉴스", "지금 여행지에서 벌어지는 일, 관광청·정부 발표, 현지 매체가 전하는 해외 소식입니다."),
    ("biz", "업계·피플", "항공사·여행사·호텔·플랫폼 소식, 그리고 사람과 의견입니다."),
    ("feature", "기획·연재", "저희가 직접 취재하고 정리한 기사입니다."),
    ("data", "통계·리포트", "환율과 날씨. 매일 아침 저희가 직접 만드는 값입니다."),
)
TOPIC_NAMES = {tid: name for tid, name, _ in TOPICS}
TOPIC_DESCS = {tid: desc for tid, _, desc in TOPICS}
# 옛 부문 → 새 부문. 규칙과 옛 주소가 이 표를 거친다.
TOPIC_ALIASES = {"issue": "news", "world": "news", "policy": "news", "people": "biz"}

# 연예 부문. 여행 쪽 people(피플·오피니언)과 겹치지 않게 인물은 star 다.
# 경로는 /ent/<id>/ 라 여행 부문 id 와 같아도 충돌하지 않지만, 코드에서
# 부문 id 하나로 채널을 알 수 있게 겹치지 않는 이름을 골랐다.
ENT_TOPICS = (
    ("movie", "영화·드라마",
     "개봉·시사회·제작발표회, 드라마·예능·OTT. 배급사·제작사·방송사 발표와 현장 취재로 씁니다."),
    ("music", "음악·공연", "앨범·컴백·차트·콘서트·쇼케이스. 공연은 현장에서 봅니다."),
    ("startrip", "스타의 여행",
     "배우·가수의 소식과 스타가 간 곳 — 촬영지, 해외 공연·팬미팅, 로케이션. 여행과 연예가 만나는 자리입니다."),
)
ENT_TOPIC_NAMES = {tid: name for tid, name, _ in ENT_TOPICS}
ENT_TOPIC_DESCS = {tid: desc for tid, _, desc in ENT_TOPICS}
# 옛 연예 부문 → 새 부문. 편집실·소스·초안이 옛 id 를 써도 여기로 붙는다.
ENT_ALIASES = {"drama": "movie", "star": "startrip"}
ENT_DEFAULT = "startrip"


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

# 연예 기사에 category 가 비어 올 때만 쓰는 보조 규칙. 편집실이 고른 값이 늘 이긴다.
# 교차 부문(startrip)이 먼저다 — "촬영지"가 있으면 영화 기사여도 여행 쪽이 살아야 한다.
_ENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("startrip", ("촬영지", "로케이션", "로케", "여행", "다녀온", "원정", "성지순례",
                  "해외 팬미팅", "日 팬미팅", "美 팬미팅", "내한", "휴가", "괌", "사이판",
                  "하와이", "제주", "다낭", "도쿄", "방콕", "타이베이")),
    ("movie", ("영화", "개봉", "시사회", "제작발표회", "박스오피스", "관객", "감독", "영화제",
               "칸", "베니스", "베네치아", "토론토", "은사자")),
    ("star", ("에미상", "시상식", "수상", "후보", "인터뷰", "화보")),
    ("drama", ("드라마", "예능", "방송", "OTT", "넷플릭스", "시청률", "종영", "첫방")),
    ("music", ("앨범", "콘서트", "공연", "쇼케이스", "컴백", "음원", "투어 공연", "페스티벌",
               "뮤지컬", "빌보드", "차트", "신곡", "히트곡", "OST", "가곡", "월드투어 매출")),
)


def _hit(text: str, korean: tuple[str, ...], english: tuple[str, ...]) -> bool:
    if any(w in text for w in korean):
        return True
    lowered = text.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", lowered) for w in english)


def is_ent(item) -> bool:
    return getattr(item, "channel", "travel") == "ent"


def ent_category_of(item) -> str:
    """연예 기사의 부문. 편집실이 정한 category 가 있으면 그것, 없으면 제목으로 추정,
    그래도 모르면 인물."""
    cat = ent_canonical(getattr(item, "category", "") or "")
    if cat:
        return cat
    text = f"{getattr(item, 'title', '')} {getattr(item, 'summary', '')}"
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
