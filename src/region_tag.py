"""기사 텍스트에서 우리가 다루는 7개 지역 중 하나를 추론한다.

국내 여행 전문 매체의 피드는 전 세계 목적지가 섞여 들어온다. 소스에 지역을
고정으로 붙일 수 없으므로 기사마다 판단해야 한다.

원칙은 재현율보다 **정확도**다. '말레이시아' 기사를 코타키나발루로 태깅하면
우리 신문이 사실을 틀리는 것이고, 그건 놓치는 것보다 나쁘다. 그래서 광역
지명이 아니라 도시·섬 이름으로만 매칭한다.
"""
from __future__ import annotations

import re

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
KOREA_TRAVEL_CUES = ("관광", "여행", "축제", "명소", "해변", "해수욕", "호텔", "리조트",
                     "숙박", "투어", "단풍", "둘레길", "산행", "국립공원", "정원", "박람회",
                     "캠핑", "미식", "맛집", "체험", "야경", "케이블카", "온천", "섬 ",
                     "트레킹", "걷기", "방문객", "관람객", "나들이", "가볼 만한", "가볼만한",
                     "카약", "서핑", "레저", "여행객", "관광객", "로컬", "문화유산", "세계유산")
_DEPARTURE = re.compile(r"(부산|김해|대구|청주|무안|양양|광주|인천|김포)\s*(~|-|–|→|발|출발|·김해)")

# 순서가 동점 처리 순서다. REGIONS 와 같은 순서로 유지한다.
REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "guam": ("괌", "guam", "투몬", "tumon", "하갓냐", "데데도"),
    "saipan": ("사이판", "saipan", "티니안", "tinian", "북마리아나",
               "마나가하", "managaha", "마리아나"),
    "hawaii": ("하와이", "hawaii", "호놀룰루", "honolulu", "와이키키",
               "waikiki", "마우이", "maui", "오아후", "oahu", "빅아일랜드"),
    "vietnam": ("베트남", "vietnam", "다낭", "danang", "da nang", "호이안",
                "hoi an", "나트랑", "냐짱", "nha trang", "푸꾸옥", "phu quoc",
                "하노이", "hanoi", "호치민", "ho chi minh", "달랏"),
    "kota": ("코타키나발루", "코타키나바루", "코타 키나발루", "kota kinabalu"),
    "laos": ("라오스", "laos", "비엔티안", "vientiane", "루앙프라방",
             "luang prabang", "방비엥", "vang vieng"),
    "jeju": ("제주", "jeju", "서귀포"),
    # 한국인 해외 도시 TOP10 에 일본 4곳·대만 1곳·태국 1곳이 들어 있다.
    # 독자를 부르는 지역이라 늦게 넣었을 뿐 규모는 가장 크다.
    "japan": ("일본", "japan", "도쿄", "tokyo", "오사카", "osaka",
              "후쿠오카", "fukuoka", "삿포로", "sapporo", "교토", "kyoto",
              "오키나와", "okinawa", "나고야", "nagoya", "규슈", "kyushu",
              "홋카이도", "hokkaido", "간사이", "kansai", "벳푸",
              # 공항 이름만 쓴 제목이 많다. "나리타 노선 주 7회→10회 증편"은
              # 일본 기사인데 '일본'이라는 말이 한 번도 안 나온다.
              "나리타", "narita", "하네다", "haneda", "신치토세", "하카타",
              "간사이공항", "니세코", "구마모토", "가고시마", "나가사키",
              "히로시마", "센다이", "다카마쓰", "시즈오카", "엔저"),
    "thailand": ("태국", "thailand", "방콕", "bangkok", "푸껫", "phuket",
                 "치앙마이", "chiang mai", "파타야", "pattaya",
                 "수완나품", "끄라비", "krabi", "사무이", "samui", "후아힌"),
    "taiwan": ("대만", "taiwan", "타이베이", "taipei", "타이완",
               "가오슝", "kaohsiung", "타이중", "taichung",
               "타오위안", "taoyuan", "지우펀", "화롄", "타이난", "臺灣", "台灣"),
    # 국내(제주 제외). 서울·인천은 넣지 않는다 — 업계 행사·공항 기사가 대부분이라
    # 여행지 기사가 아닌데 국내로 잡힌다. 여행지로 읽히는 도시·군·섬 이름만 둔다.
    # 동점이면 앞선 해외 지역이 이긴다("강릉~다낭"은 없지만 "여수·다낭"은 베트남).
    "korea": ("국내여행", "국내 여행", "국내관광", "국내 관광", "강원", "강릉", "속초",
              "양양", "춘천", "평창", "정선", "삼척", "인제", "가평", "양평", "강화도",
              "경주", "안동", "포항", "울릉", "독도", "부산", "해운대", "통영", "거제",
              "남해", "하동", "진주", "창녕", "여수", "순천", "담양", "목포", "보성",
              "전주", "군산", "남원", "단양", "제천", "충주", "공주", "부여", "태안",
              "보령", "DMZ", "비무장지대"),
}


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
        if region == "korea" and hits and not any(c in text for c in KOREA_TRAVEL_CUES):
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
    if region == "korea" and not any(c in text for c in KOREA_TRAVEL_CUES):
        return False
    if any(k.lower() in lowered for k in REGION_KEYWORDS.get(region, ())):
        return True
    return any(p.search(text) for r, p in _HANJA_ABBR if r == region)
