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
REGION_EXCLUSIONS = ("제주항공", "하와이안항공")

# 국적 항공사(베트남항공·라오항공)는 일부러 넣지 않았다. 그 항공사 소식은 거의 항상
# 자국 관련이라 지우면 진짜 기사를 잃는다. 제주항공은 전 세계로 날아가는 한국 LCC 라,
# 하와이안항공은 일본 노선도 있어 각각 실측 오탐이 확인됐다.

# 한 글자 키워드는 오탐을 부르므로 여기 적힌 것만 허용한다.
# '괌'은 한국어에서 다른 단어의 부분문자열로 거의 나타나지 않아 안전하다
# (오사카·파리·도쿄·방콕·세부·유류할증료·여권·발리 에서 오탐 없음을 실측 확인).
SINGLE_CHAR_ALLOWED = frozenset({"괌"})

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

    lowered = text.lower()
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
    lowered = text.lower()
    for phrase in REGION_EXCLUSIONS:
        lowered = lowered.replace(phrase.lower(), " ")
    if any(k.lower() in lowered for k in REGION_KEYWORDS.get(region, ())):
        return True
    return any(p.search(text) for r, p in _HANJA_ABBR if r == region)
