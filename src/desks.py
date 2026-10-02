"""기사 서명(byline)을 정한다.

**사람 이름을 지어내지 않는다.** 실존하지 않는 기자 이름을 서명으로 붙이면
독자는 그것을 실제 기자로 읽는다. 한 명이라도 "이 기자 누구냐"고 물으면
매체 신뢰가 한 번에 끝나고, 광고·제휴 협상에서도 치명적이다.

대신 **부서로 나눈다.** 지면이 한 사람 손에서 나온 것처럼 보이지 않으면서
거짓이 아니다 — 실제로 데이터는 파이프라인이 만들고, 해설은 지역별로 쓴다.

**2026-10-02 부터 실명 기자로 서명한다.** 2026-10-01 편집국장 미팅에서 정했다 —
"모든 기사는 각색해서 넣어서 진행하고 저희 회사 직원 이름으로 진행한다." 피플레이
직원 여섯 명이 지면을 나눠 맡는다(REPORTERS). 네이버 뉴스 제휴는 지어낸 이름이 아니라
실제로 일하는 사람의 이름을 본다(2026-09-16 편집국장).

그 전에 나간 기사는 데스크명 그대로 둔다 — 그때는 그 사람이 맡은 기사가 아니었다.

AI 가 초안을 쓴 기사도 담당 기자 이름으로 나간다. 서명은 '이 기사를 맡은 사람'이고,
정정 요청도 이 이름으로 온다. 그 사실은 매체 소개·편집원칙에 그대로 밝힌다.
"""
from __future__ import annotations

from src.brand import SITE_NAME as BRAND  # noqa: E402 — 정본은 brand.py

from src.models import ADAPT_FROM, REGION_NAMES  # noqa: E402

# 실명 기자 명부 — 2026-10-01 편집국장 미팅 회의록의 피플레이 직원 여섯 명.
# 이름 → 맡은 지면. 지면 키는 지역(models.REGIONS)·"ent"(연예)·"data"(환율·날씨).
#
# 나눈 기준: 2026-09 한 달 우리 기사 228편의 지역별 건수를 여섯이 비슷하게 갖도록
# (괌·사이판 49 · 일본 46 · 베트남·라오스 48 · 태국·코타·대만 45 · 하와이·제주 35 +
# 데이터 · 연예). 회의록에는 누가 무엇을 맡는지 없어 이 나눔은 임시다 — 바꿀 때는
# 여기만 고친다.
# ★지어내지 않는다. 회사에 실제로 있는 사람만 올린다.
REPORTERS: dict[str, tuple[str, ...]] = {
    "김태성": ("guam", "saipan"),
    "이병훈": ("japan",),
    "이우재": ("vietnam", "laos"),
    "장미화": ("thailand", "kota", "taiwan"),
    "이승훈": ("hawaii", "jeju", "data"),
    "이수비": ("ent",),
}
# 맡은 사람이 없는 지면(새로 연 지역 등)은 이 사람이 맡는다.
GENERAL_REPORTER = "이승훈"
# 실명 서명이 시작되는 날. 2026-10-01 미팅 결정과 같은 날이다.
REPORTERS_FROM = ADAPT_FROM
# 지면 → 기자
BEATS: dict[str, str] = {beat: name for name, beats in REPORTERS.items()
                         for beat in beats}
BEAT_NAMES: dict[str, str] = {**REGION_NAMES, "ent": "연예",
                              "data": "환율·날씨"}

# 기사 종류. 초안 앞머리의 `kind` 에 적는다. 네이버 제휴 심사는 자체 기사
# (취재·기획·인터뷰) 비중을 본다 — 편집국장: 50~70%, 적어도 50%(2026-10-01).
# 보도자료를 다시 쓴 것과 여러 보도를 묶은 해설은 자체 기사로 세지 않는다.
KINDS = ("취재", "기획", "인터뷰", "해설", "보도자료")
OWN_KINDS = ("취재", "기획", "인터뷰")

# 지역 해설 기사의 데스크
REGION_DESKS = {
    "guam": f"{BRAND} 괌 데스크",
    "saipan": f"{BRAND} 사이판 데스크",
    "hawaii": f"{BRAND} 하와이 데스크",
    "vietnam": f"{BRAND} 베트남 데스크",
    "kota": f"{BRAND} 코타키나발루 데스크",
    "laos": f"{BRAND} 라오스 데스크",
    "jeju": f"{BRAND} 제주 데스크",
    "japan": f"{BRAND} 일본 데스크",
    "thailand": f"{BRAND} 태국 데스크",
    "taiwan": f"{BRAND} 대만 데스크",
}
DATA_DESK = f"{BRAND} 데이터팀"
EDIT_DESK = f"{BRAND} 편집팀"
# 연예 채널의 기본 서명. 지역이 없으므로 데스크가 하나다.
ENT_DESK = f"{BRAND} 문화부"

# 연예 기사가 만들어지는 방식. 수집·자동 생성 경로가 없다 — 편집실에서 사람이
# 보도자료·현장 소스를 받아 쓰고 승인해야 나간다. 그래서 자동이 아니다.
ENT_HOW = "편집실 작성 · 사람 승인"

# 각 데스크가 맡는 일. 편집국 소개에 그대로 쓴다 —
# 독자가 "누가 이걸 만드나"를 알 수 있어야 한다.
#
# 만드는 방식은 **실제와 같아야 한다.** 2026-09-09 점검에서 지역 데스크가
# "사람" 으로 적혀 있었는데, 해설은 사람이 정한 취재 지침(docs/DAILY_COMMENTARY.md)
# 을 읽고 예약된 AI 가 쓰고 자동 발행한다. 신뢰도를 말하는 페이지에서 이걸
# 틀리면 페이지 전체가 무너진다. 사람이 쓰기 시작하면 그때 라벨을 바꾼다.
DESK_DUTIES = (
    (DATA_DESK, "환율·날씨를 매일 아침 직접 수집해 정리합니다. 데이터 기사도 여기서 만듭니다.",
     "자동"),
    (EDIT_DESK, "다른 매체의 보도를 골라 제목과 두 문장 요약에 원문 링크를 답니다.",
     "자동"),
    (REGION_DESKS["guam"], "괌 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["saipan"], "사이판 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["hawaii"], "하와이 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["vietnam"], "베트남 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["kota"], "코타키나발루 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["laos"], "라오스 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["jeju"], "제주 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["japan"], "일본 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["thailand"], "태국 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (REGION_DESKS["taiwan"], "대만 지역의 해설·답사 기사를 맡습니다.", "AI 작성 · 사람 지침"),
    (ENT_DESK, "영화·드라마, 음악·공연, '스타의 여행' 기사를 맡습니다. "
               "소속사·배급사 보도자료와 현장 취재로 씁니다.", ENT_HOW),
)


def reporter_for(item) -> str:
    """이 기사를 맡는 기자. 연예는 연예 담당, 환율·날씨는 데이터 담당, 나머지는 지역 담당."""
    if getattr(item, "channel", "travel") == "ent":
        return BEATS["ent"]
    if getattr(item, "grade", "") == "A" or getattr(item, "source_name", "") == DATA_DESK:
        return BEATS["data"]
    return BEATS.get(getattr(item, "region", ""), GENERAL_REPORTER)


# 사람 이름이 아닌 서명. 초안에 이게 적혀 있으면 '안 적힌 것'으로 본다.
DESK_NAMES = set(REGION_DESKS.values()) | {DATA_DESK, EDIT_DESK, ENT_DESK, BRAND}


def _named(item) -> str:
    """초안에 적힌 필자. '김태성 기자'·'김태성' 둘 다 받는다."""
    raw = (getattr(item, "source_name", "") or "").strip()
    if raw.endswith(" 기자"):
        raw = raw[: -len(" 기자")].strip()
    return "" if raw in DESK_NAMES else raw


def byline_for(item) -> str:
    """이 기사의 서명.

    B등급(큐레이션)은 원문 매체 이름을 그대로 둔다 — 그게 쓴 사람이다.
    바꾸면 남의 기사를 우리가 쓴 것처럼 보이게 만드는 것이라 하면 안 된다.
    (2026-10-02 부터 B등급은 지면에 나가지 않는다. 그 전에 실린 것만 남는다.)

    2026-10-02 부터 나간 우리 기사는 실명 기자다. 초안에 명부의 이름이 적혀 있으면
    그 사람, 비어 있거나 데스크명이면 그 지면 담당이다. 명부 밖의 이름(외부 필자·
    기고)이 적혀 있으면 적힌 그대로 둔다. 같은 기사에 두 번 불러도 결과가 같다.
    """
    grade = getattr(item, "grade", "")
    if grade == "B":
        return getattr(item, "source_name", "") or EDIT_DESK
    day = (getattr(item, "published_at", "") or "")[:10]
    if day >= REPORTERS_FROM:
        named = _named(item)
        if named in REPORTERS:
            return f"{named} 기자"
        if named:
            return named
        return f"{reporter_for(item)} 기자"
    if grade == "A":
        return DATA_DESK
    # C등급 — 우리가 쓴 글. 이미 필자가 적혀 있으면 존중한다.
    written_by = getattr(item, "source_name", "") or ""
    if written_by and written_by != BRAND:
        return written_by
    if getattr(item, "channel", "travel") == "ent":
        return ENT_DESK
    return REGION_DESKS.get(getattr(item, "region", ""), EDIT_DESK)


def staff_table() -> list[tuple[str, str]]:
    """매체 소개의 편집국 표. (서명, 맡는 지면)."""
    return [(f"{name} 기자", " · ".join(BEAT_NAMES.get(b, b) for b in beats))
            for name, beats in REPORTERS.items()]
