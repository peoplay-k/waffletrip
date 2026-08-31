"""기사 텍스트에서 우리가 다루는 7개 지역 중 하나를 추론한다.

국내 여행 전문 매체의 피드는 전 세계 목적지가 섞여 들어온다. 소스에 지역을
고정으로 붙일 수 없으므로 기사마다 판단해야 한다.

원칙은 재현율보다 **정확도**다. '말레이시아' 기사를 코타키나발루로 태깅하면
우리 신문이 사실을 틀리는 것이고, 그건 놓치는 것보다 나쁘다. 그래서 광역
지명이 아니라 도시·섬 이름으로만 매칭한다.
"""
from __future__ import annotations

from src.models import REGIONS

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
               "waikiki", "마우이", "maui", "오아부", "oahu", "빅아일랜드"),
    "vietnam": ("베트남", "vietnam", "다낭", "danang", "da nang", "호이안",
                "hoi an", "나트랑", "냐짱", "nha trang", "푸꾸옥", "phu quoc",
                "하노이", "hanoi", "호치민", "ho chi minh", "달랏"),
    "kota": ("코타키나발루", "코타키나바루", "코타 키나발루", "kota kinabalu"),
    "laos": ("라오스", "laos", "비엔티안", "vientiane", "루앙프라방",
             "luang prabang", "방비엥", "vang vieng"),
    "jeju": ("제주", "jeju", "서귀포"),
}


def tag_region(text: str) -> str | None:
    """가장 많이 언급된 지역을 돌려준다. 하나도 없으면 None.

    None 은 오류가 아니라 '우리가 다루지 않는 목적지'라는 정상 판정이다.
    호출자는 그 항목을 버린다.
    """
    if not text:
        return None

    lowered = text.lower()
    best_region: str | None = None
    best_hits = 0

    # REGIONS 순서로 도므로 동점이면 항상 앞선 지역이 이긴다 (결정적).
    for region in REGIONS:
        hits = sum(lowered.count(k.lower()) for k in REGION_KEYWORDS[region])
        if hits > best_hits:
            best_region, best_hits = region, hits

    return best_region
