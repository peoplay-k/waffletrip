"""기사가 여행자에게 쓸모 있는가.

현지 종합지는 그 지역 **주민**을 위한 신문이다. 선거·범죄·행정 기사가 대부분이고,
그대로 실으면 여행 신문 1면에 살인 사건이 올라간다(실제로 그랬다).

이 필터는 완벽하지 않다. 키워드 방식이라 양방향 오류가 난다. 그래서 **1차 방어선은
소스 선정**이고 이건 그 뒤를 받는 그물이다. 놓치는 쪽(기사를 버리는 쪽)으로 틀리게
만들었다 — 여행 신문에 살인 기사가 실리는 것보다 여행 기사 몇 건을 놓치는 게 낫다.
"""
from __future__ import annotations

import re

TRAVEL_KEYWORDS: tuple[str, ...] = (
    # 이동·항공
    "항공", "취항", "노선", "증편", "감편", "직항", "공항", "비행", "결항",
    "수하물", "항공권",
    "flight", "airline", "airport", "airfare", "nonstop", "aviation", "route",
    # 숙박
    "호텔", "리조트", "숙소", "숙박", "펜션", "게스트하우스", "객실",
    "hotel", "resort", "accommodation", "lodging", "hostel",
    # 여행 일반
    "여행", "관광", "투어", "패키지", "명소", "여행객", "관광객", "입국",
    "비자", "여권", "성수기",
    "travel", "tourism", "tourist", "vacation", "holiday", "itinerary",
    "destination", "visa", "passport", "sightseeing",
    # 활동·현지
    "해변", "해수욕", "스노클", "다이빙", "크루즈", "요트", "골프", "면세",
    "맛집", "레스토랑", "카페", "축제",
    "beach", "snorkel", "diving", "cruise", "yacht", "golf", "duty-free",
    "festival", "dining", "restaurant", "attraction", "museum",
    # 여행에 영향을 주는 정보
    "환율", "날씨", "태풍", "수온", "여행경보",
    "weather", "typhoon", "forecast", "advisory",
    # 재난·교통 경보. 2026-09-09 실측: 허리케인 로웰로 카우아이 고속도로가 막히고 3만 3천 가구가 정전된 보도가 여행 키워드가 없어 전부 탈락했다. 여행자에게 이것보다 급한 뉴스는 없다.
    "hurricane", "storm", "tsunami", "earthquake", "eruption", "volcanic", "flood", "evacuation", "power outage", "highway", "road closure", "ferry", "terminal", "허리케인", "폭풍", "쓰나미", "지진", "화산", "홍수", "대피", "정전", "페리", "여객선", "도로 통제",
)

# 일부러 넣지 않은 것: "park"(주차된 차 사고·공원 민원이 통과했다),
# "trip"(외교 순방 "a 10-day trip" 이 통과했다), "fair"(공정성 기사).

# 여행 단어를 품고 있지만 여행 기사가 아닌 표현. 세기 전에 지운다.
# 실측 오탐: "여권통문"(1898년 여성인권선언)이 여권으로, "제2공항"·"한국공항공사"가
# 공항으로 잡혀 정치·행정 기사가 통과했다.
TRAVEL_EXCLUSIONS: tuple[str, ...] = ("여권통문", "제2공항", "한국공항공사", "공항공사")

# 영문 키워드에 붙여 허용할 어미. travel/travels/traveled 뿐 아니라 겹자음 형태인
# travelled·travelling 도 잡아야 한다 — 영국식 철자가 말레이시아·싱가포르·호주
# 영어권 소스의 표준이라, 안 잡으면 그쪽 기사를 통째로 놓친다.
_INFLECTION = r"(?:l?e?[sd]|l?ing)?"


# 여행 단어가 있어도 실을 수 없는 것. 사건 기사는 여행지 이름이나 "호텔"·"공항"·
# "식당"이 배경으로 나올 뿐 여행 정보가 아니다. 실측: 하와이 지면에 "호텔 직원
# 성범죄 유죄"가 hotel 로, "식당 살인미수"가 restaurant 로 통과해 실렸다.
#
# 대인 범죄 어휘로만 좁혔다. lawsuit·arrest 같은 넓은 말은 넣지 않는다 —
# "수하물 분실 소송"과 "기내 난동 승객 체포"는 여행자에게 쓸모 있는 기사다.
CRIME_KEYWORDS: tuple[str, ...] = (
    "convicted", "murder", "manslaughter", "homicide", "rape",
    "sexual assault", "sexually assaulted", "predator", "pervert",
    "stabbed", "stabbing", "shooting", "shot dead", "molest",
    "성폭행", "성추행", "강제추행", "살인", "살해", "흉기", "음주운전",
    # 2026-09-09 실측: '음주운전 기소된 식당 주인' 기사가 restaurant 로 통과했다.
    "dui", "drunk driving", "drunken driving", "robbery", "carjacking",
)


def is_crime_report(text: str) -> bool:
    """사건 기사인가. 여행 전용 매체에는 적용하지 않는다.

    VnExpress Travel 처럼 여행 지면이 낸 기사는 범죄를 다뤄도 여행 기사다
    ("문제 관광객 경고" 같은 것). 그래서 이 게이트는 종합지에만 건다.
    """
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in CRIME_KEYWORDS)

def is_travel_related(text: str) -> bool:
    """여행자에게 쓸모 있는 기사인가. 빈 문자열·None 은 아니다.

    영문 키워드는 단어 경계로 맞춘다 — 부분일치를 허용하면 "travel" 이
    "travelling" 을 넘어 엉뚱한 곳까지 걸린다. 한글은 조사가 붙어 오므로
    부분일치를 유지하되, 실측으로 확인된 오탐 표현만 미리 지운다.
    """
    if not text:
        return False

    lowered = text.lower()
    for phrase in TRAVEL_EXCLUSIONS:
        lowered = lowered.replace(phrase.lower(), " ")

    for keyword in TRAVEL_KEYWORDS:
        lowered_keyword = keyword.lower()
        if lowered_keyword.isascii():
            pattern = r"\b" + re.escape(lowered_keyword) + _INFLECTION + r"\b"
            if re.search(pattern, lowered):
                return True
        elif lowered_keyword in lowered:
            return True
    return False

# ── 스팸 ─────────────────────────────────────────────────────────────
# 구글뉴스 검색 피드에 "호텔" 을 넣으면 카지노 홍보 스팸이 섞여 온다. 2026-09-09
# 실측: "도쿄 호텔 카지노의 역사와 발전: 과거에서 현재까지 - 전문가의 관점에서",
# "오사카 호텔 카지노 완벽한 비교 가이드 (2025년 최신판)" 같은 틀에 박힌 제목이
# 하루 33건, 전부 og:site_name 이 "Histoire pour tous"(탈취된 프랑스 역사 사이트)로
# 풀렸다. '호텔' 키워드로 여행 필터를 통과해 지면에 실릴 뻔했다.
#
# 낱말 차단은 큐레이션(여행 전문지) 소스에는 걸지 않는다 — 인스파이어 리조트
# 카지노 개장 같은 업계 뉴스는 진짜 여행 뉴스다. 스팸은 검색 피드로만 들어온다.
SPAM_KEYWORDS: tuple[str, ...] = (
    "카지노", "casino", "바카라", "baccarat", "슬롯머신", "슬롯 머신", "토토",
    "먹튀", "온라인 도박", "사설 베팅", "betting site", "online gambling",
)
# 실측으로 확인된 스팸 출처. 이름이 이렇게 풀리면 내용과 무관하게 버린다.
SPAM_SOURCES: frozenset[str] = frozenset({"Histoire pour tous"})
# 블로그 플랫폼. 구글뉴스 검색 피드는 브런치·네이버 블로그 글도 기사처럼 돌려준다.
# 2026-09-09 실측: "하와이 호텔 추천 리스트 5선 총정리"(브런치)가 하와이면에 실렸다.
# 개인 글은 인용 매체가 아니다 — 출처 이름에 이 낱말이 있으면 버린다.
NON_NEWS_SOURCES: tuple[str, ...] = ("브런치", "네이버 블로그", "티스토리", "유튜브", "youtube")


# ── 연예 — 싣지 않는 것 ────────────────────────────────────────────
# 편집원칙 3번: 공식 발표되지 않은 열애·가족·건강·주거 정보, 확인되지 않은 소문,
# 악의적인 댓글을 옮긴 기사. 검색 피드는 이런 제목이 절반이다. 제목에 이 낱말이
# 있으면 사실이어도 우리 지면의 일이 아니다 — 놓치는 쪽으로 틀리게 만든다.
ENT_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    # 사건·폭력. 연예 헤드라인 섹션에 '소주병 위협 CCTV 공개' 가 실렸다(2026-09-25).
    "CCTV", "cctv", "소주병", "위협", "폭행", "협박", "흉기", "성폭력", "피소", "기소", "징역",
    "벌금", "재판", "법원", "경찰 조사", "체포",
    "열애", "결별", "이혼", "파경", "불화", "루머", "찌라시", "폭로", "저격", "논란",
    "해명", "사과문", "갑질", "학폭", "마약", "음주", "성추문", "성희롱", "송사",
    "고소", "고발", "소송", "법정", "구속", "입건", "송치", "실형", "집행유예",
    "비난", "악플", "댓글 테러", "몸매", "노출", "비키니", "속옷", "19금",
    "사망설", "위독", "응급실", "투병", "건강 이상", "임신설", "결혼설", "재혼설",
    # 2026-09-25 167번 실측: 구글뉴스 연예 헤드라인 섹션은 절반이 사생활이었다 — 재혼·이혼·
    # 가족사진·자녀 공개·재산·저택·빚·파산·출산·성형·체중·오열·누리꾼 반응. 편집원칙 3번이 금한다.
    "♥", "재혼", "전남편", "전 남편", "전처", "전 남친", "전 여친", "열애 인정", "결혼식", "웨딩",
    "득남", "득녀", "출산", "산모", "임신", "둘째", "셋째", "가족사진", "딸 공개", "아들 공개",
    "자녀", "子", "父", "母", "붕어빵", "재산", "저택", "건물 3채", "빚", "파산", "억 벌", "연봉",
    "쌍수", "성형", "kg", "체중", "다이어트", "뼈말라", "비주얼", "얼굴 좋아", "화들짝", "징그러워",
    "오열", "눈물", "폭풍", "누리꾼", "네티즌", "SNS 삭제", "게시물", "근황", "살림남", "제사",
    "로또", "당첨", "출근", "취업", "회사원", "[Oh!쎈", "[스타이슈]", "MHN:피드", "MHN:픽",
    "[세상읽기]", "디깅메이트", "소감문", "시의회", "초등생", "학생들,", "접수", "공모전",
    # 지역 행사·기관 행사성 영화제. 연예 소식이 아니라 지자체·공공기관 보도자료다.
    "지하철영화제", "환경영화제", "단편영화제", "특수영상", "문화원", "영화산업", "MOU",
    "성황리", "군, ", "군,'", "시, ", "구, ", "재단,", "공사 ", "협회 ",
    # 연예가 아닌데 검색어에 걸리는 것 — 게임 '출시', 자동차 PPL 보도자료, 증권·인수 기사
    "게임", "출시 전", "공식 출시", "얼리액세스", "스팀", "플레이스테이션", "닌텐도",
    "GV80", "GV70", "제네시스 ", "신차", "하이브리드", "모터스튜디오",
    "인수 눈앞", "지분", "주가", "증권", "투자 약속", "조선비즈",
)

# 기계 번역 티가 나는 제목. 2026-09-25 실측: 구글뉴스 한국어판에 베트남 매체의 자동 번역
# 기사가 섞여 왔다("…영화가 인기를 끄는 이유를 분석해 봅시다", "…리뷰를 읽어보세요",
# "…VOD로 시청 가능합니다", "…150억 VND 수익"). 남의 매체의 번역문은 우리 지면이 아니다.
ENT_TRANSLATED_MARKS: tuple[str, ...] = (
    "봅시다", "읽어보세요", "확인해 보세요", "알아보세요", "가능합니다", "습니다.",
    "VND", "동(", "하노이 극장", "호치민 극장",
)
# 연예 지면에 싣지 않는 출처(번역·해외 종합지). 여행 쪽 SKIP_OUTLETS 와 별개다.
# 2026-09-25 165번 실행 실측: vietnam.vn 4건, sortiraparis.com(프랑스) 2건, newsinstar.com(뉴스인스타 — 연예 매체라 남긴다),
# 레디앙(정치)·에너지경제신문·인천투데이(지역 행정) 각 1건이 연예면에 들어왔다.
ENT_SKIP_OUTLETS: tuple[str, ...] = (
    "VnExpress", "Vietnam.vn", "VietnamPlus", "Báo", "Tuoi Tre", "Thanh Nien",
    "Kenh14", "Zing", "조선비즈", "Histoire pour tous",
    "sortiraparis", "레디앙", "에너지경제", "인천투데이",
    "뉴닉",  # 뉴스레터 말투("…한 사연 👀🎧")가 지면 제목으로 안 맞는다
)


# 부문을 지정하지 않은 일반 피드(연예 헤드라인·시상식)는 **공식 발표성** 낱말이 제목에 있어야
# 싣는다. 개봉·컴백·공연·수상·캐스팅·공개처럼 소속사·배급사·방송사가 발표한 일. 이게 없으면
# 화제성 기사다 — 우리 지면의 일이 아니다.
ENT_NEWSWORTHY: tuple[str, ...] = (
    "개봉", "시사회", "제작발표회", "박스오피스", "관객", "영화제", "내한", "감독",
    "컴백", "앨범", "신곡", "음원", "차트", "빌보드", "콘서트", "공연", "투어", "쇼케이스",
    "페스티벌", "뮤지컬", "OST", "데뷔",
    "첫 방송", "첫방", "종영", "방영", "공개", "시즌", "출연", "캐스팅", "합류", "확정",
    "시상식", "수상", "대상", "후보", "노미네이트", "심사위원",
    "팬미팅", "화보", "촬영", "촬영지", "로케이션", "한류", "K팝", "K-팝",
    "에미", "그래미", "아카데미", "골든글로브", "청룡", "백상", "대종상",
)


def is_ent_newsworthy(title: str) -> bool:
    """일반 연예 피드에서 실을 만한 공식 발표성 제목인가."""
    return bool(title) and any(k in title for k in ENT_NEWSWORTHY)


def is_ent_excluded(text: str, source_name: str = "") -> bool:
    """연예 기사 가운데 우리 지면에 싣지 않는 것인가 — 가십·사건·비연예·기계번역·해외 번역 매체."""
    if source_name and any(k.lower() in source_name.lower() for k in ENT_SKIP_OUTLETS):
        return True
    # 매체 이름이 깨져 왔으면(EUC-KR 페이지를 잘못 읽은 것) 누가 썼는지 밝힐 수 없다. 싣지 않는다.
    if source_name and "\ufffd" in source_name:
        return True
    if not text:
        return False
    if any(k in text for k in ENT_EXCLUDE_KEYWORDS):
        return True
    title = text.split("\n", 1)[0]
    return any(k in title for k in ENT_TRANSLATED_MARKS)


def is_spam(text: str, source_name: str = "") -> bool:
    """검색 피드에 섞여 오는 도박 홍보 글인가."""
    if source_name and source_name in SPAM_SOURCES:
        return True
    if source_name and any(k in source_name.lower() for k in NON_NEWS_SOURCES):
        return True
    if not text:
        return False
    lowered = text.lower()
    return any(k.lower() in lowered for k in SPAM_KEYWORDS)
