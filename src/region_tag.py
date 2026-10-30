"""기사 텍스트에서 우리가 다루는 7개 지역 중 하나를 추론한다.

국내 여행 전문 매체의 피드는 전 세계 목적지가 섞여 들어온다. 소스에 지역을
고정으로 붙일 수 없으므로 기사마다 판단해야 한다.

원칙은 재현율보다 **정확도**다. '말레이시아' 기사를 코타키나발루로 태깅하면
우리 신문이 사실을 틀리는 것이고, 그건 놓치는 것보다 나쁘다. 그래서 광역
지명이 아니라 도시·섬 이름으로만 매칭한다.
"""
from __future__ import annotations

import re

from src import site_config as _sc
from src.models import REGIONS

# 지역 이름을 품고 있지만 그 지역 기사가 아닌 표현. 세기 전에 먼저 지운다.
# '제주항공'은 제주가 아니라 전 세계로 날아가는 항공사고, '하와이안항공'도
# 나리타(일본) 등 하와이 밖 노선을 다닌다 — 실측에서 "제주항공, 부산~구이린
# 노선 취항"(중국 계림 기사), "노랑풍선 일본 나고야 상품", "하와이안항공, 나리타
# 노선 신규 취항"이 각각 제주 또는 하와이로 잘못 태깅됐다. 항공사명이 목적지를
# 뜻하지 않는다.
# '부곡하와이'는 경남 창녕의 온천 리조트다. 2026-09-09 실측: "폐조선소·부곡하와이까지…
# 경남도 관광개발" 이 하와이로 잡혔다.
REGION_EXCLUSIONS = ("제주항공", "하와이안항공", "부곡하와이", "에어부산")

# 국적 항공사(베트남항공·라오항공)는 일부러 넣지 않았다. 그 항공사 소식은 거의 항상
# 자국 관련이라 지우면 진짜 기사를 잃는다. 제주항공은 전 세계로 날아가는 한국 LCC 라,
# 하와이안항공은 일본 노선도 있어 각각 실측 오탐이 확인됐다.

# 한 글자 키워드는 오탐을 부르므로 여기 적힌 것만 허용한다.
# '괌'은 한국어에서 다른 단어의 부분문자열로 거의 나타나지 않아 안전하다
# (오사카·파리·도쿄·방콕·세부·유류할증료·여권·발리 에서 오탐 없음을 실측 확인).
SINGLE_CHAR_ALLOWED = frozenset({"괌"})

# 국내 공항 도시가 노선의 출발지로만 나오는 표현. "부산~다낭 취항"은 베트남 기사다.
# 국내 지명이 목적지가 아니라 출발지일 때는 세지 않는다.
# 국내 지명은 지자체 소식(의회·복지·행정)에 훨씬 많이 나온다. 지명만으로 국내 여행면에
# 올리면 "공주시의회 행정사무감사"가 여행 기사가 된다(2026-10-28 실측 116건 중 절반).
# 국내는 제목에 여행으로 읽히는 말이 함께 있을 때만 잡는다. 해외 지역은 지명만 본다 —
# 해외 지명이 한국 매체 제목에 나오면 거의 항상 여행·항공 기사다.
KOREA_TRAVEL_CUES = tuple(_sc.CONFIG.get("korea_travel_words") or ())
# 이 말이 있어야 잡히는 지역(site.json 의 require_travel_word — 지금은 국내)
TRAVEL_WORD_REGIONS = _sc.travel_word_regions(_sc.CONFIG)
_DEPARTURE = re.compile(r"(부산|김해|대구|청주|무안|양양|광주|인천|김포)\s*(~|-|–|→|발|출발|·김해)")

# 지명이 없어도 여행업계 기사로 읽히는 말. 제목에서만 본다(위 auto 판정과 같은 이유).
# 2026-10-30 사장님: "여행 기사 더 만들어 … 여기 기사들 많은데 뭐하는거야? 좀 챙겨서 가지고와서
# 좀 올려"(TTL뉴스·문화뉴스·ㅍㅍㅅㅅ). TTL뉴스는 종합 보도자료가 섞여 지명 없는 기사를 통째로
# 버렸는데(industry: false), 그 안에 "하나투어 겨울 패키지 출시"·"대한항공 기내식 개편" 같은
# 진짜 여행업계 기사가 같이 버려지고 있었다 — 하루 1~6건만 남았다. 지명이 없어도 이 말이
# 제목에 있으면 여행업계면으로 받는다. 금융·교육청·식품 보도자료에는 이 말이 없다.
# 회사 이름도 넣었다: 노랑풍선·진에어·야놀자처럼 이름에 여행·항공이 안 들어가는 업체는 말로는
# 못 잡는다. 일반 명사는 뺐다 — "체험"·"행사"·"출시"는 어느 보도자료에나 있다.
INDUSTRY_TRAVEL_CUES: tuple[str, ...] = (
    "여행", "관광", "투어", "항공", "취항", "노선", "증편", "직항", "운항", "공항", "항공권",
    "기내", "마일리지", "환승", "면세", "비자", "여권", "입국", "출국", "호텔", "리조트", "숙박",
    "숙소", "호캉스", "크루즈", "패키지", "에어텔", "휴양", "휴양지", "여행객", "관광객",
    "테마파크", "워터파크", "랜드사", "OTA", "예약 플랫폼",
    # 업체·기관 이름
    "노랑풍선", "참좋은", "인터파크", "야놀자", "여기어때", "아고다", "트립닷컴", "익스피디아",
    "부킹닷컴", "에어비앤비", "스카이스캐너", "마이리얼트립", "클룩", "트래블월렛",
    "대한항공", "아시아나", "진에어", "에어서울", "에어부산", "에어프레미아", "에어로케이",
    "이스타", "티웨이", "파라타", "아코르", "메리어트", "힐튼", "하얏트", "IHG", "샹그릴라",
)


def is_industry_story(title: str) -> bool:
    """지명 없는 제목이 여행업계 기사로 읽히는가."""
    if not title:
        return False
    lowered = title.lower()
    return any(c.lower() in lowered for c in INDUSTRY_TRAVEL_CUES)

# 순서가 동점 처리 순서다. REGIONS 와 같은 순서로 유지한다.
# 2026-10-30 부터 정본은 config/site.json(regions[].keywords) — 편집실에서 사장님이 고친다.
# 숨긴 지역은 키워드를 주지 않아 새로 수집하지 않는다. 고르는 원칙은 이 파일 맨 위 설명 그대로:
# 광역 지명이 아니라 도시·섬 이름, 한 글자 키워드는 SINGLE_CHAR_ALLOWED 만.
REGION_KEYWORDS: dict[str, tuple[str, ...]] = _sc.region_keywords(_sc.CONFIG)


# 국내 매체는 제목에서 나라를 한 글자 한자로 줄여 쓴다 — "日항공사",
# "泰 관광청". 숫자 뒤(30日)는 날짜이므로 제외하고, 뒤에 한글이 올 때만
# 나라 이름으로 본다. 이 표기를 놓쳐서 "나리타 노선 증편" 같은 진짜 일본
# 기사가 통째로 버려지고 있었다.
_HANJA_ABBR: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("japan", re.compile(r"(?<!\d)日(?!\d)")),
    ("thailand", re.compile(r"(?<!\d)泰(?!\d)")),
    ("taiwan", re.compile(r"(?<!\d)[臺台](?!\d)")),
)


def tag_region(text: str) -> str | None:
    """가장 많이 언급된 지역을 돌려준다. 하나도 없으면 None.

    None 은 오류가 아니라 '우리가 다루지 않는 목적지'라는 정상 판정이다.
    호출자는 그 항목을 버린다.
    """
    if not text:
        return None

    lowered = _DEPARTURE.sub(" ", text).lower()
    for phrase in REGION_EXCLUSIONS:
        lowered = lowered.replace(phrase.lower(), " ")

    best_region: str | None = None
    best_hits = 0

    # REGIONS 순서로 도므로 동점이면 항상 앞선 지역이 이긴다 (결정적).
    for region in REGIONS:
        # .get 으로 받는다. 지역을 늘리고 키워드를 잊어도 빌드가
        # 통째로 죽으면 안 된다 — 그 지역만 안 잡힐 뿐이다.
        hits = sum(lowered.count(k.lower())
                   for k in REGION_KEYWORDS.get(region, ()))
        for abbr_region, pattern in _HANJA_ABBR:
            if abbr_region == region:
                hits += len(pattern.findall(text))
        if region in TRAVEL_WORD_REGIONS and hits and not any(c in text for c in KOREA_TRAVEL_CUES):
            hits = 0
        if hits > best_hits:
            best_region, best_hits = region, hits

    return best_region


def mentions_region(text: str, region: str) -> bool:
    """제목이 그 지역을 말하고 있나. tag_region 과 달리 승부를 가리지 않는다.

    "추석 연휴 제주·후쿠오카 인기"는 제주 기사이면서 일본 기사다.
    tag_region 은 하나만 고르므로 이걸로 걸러내면 두 지역 다 다루는 기사를
    통째로 버리게 된다. 목적지 피드를 검증할 때는 '언급했나'만 물으면 된다.
    """
    if not text:
        return False
    lowered = _DEPARTURE.sub(" ", text).lower()
    for phrase in REGION_EXCLUSIONS:
        lowered = lowered.replace(phrase.lower(), " ")
    if region in TRAVEL_WORD_REGIONS and not any(c in text for c in KOREA_TRAVEL_CUES):
        return False
    if any(k.lower() in lowered for k in REGION_KEYWORDS.get(region, ())):
        return True
    return any(p.search(text) for r, p in _HANJA_ABBR if r == region)
