"""매체 이름·도메인·연락처. 한 곳에서만 정한다.

제호를 와플트립에서 피플로드로 바꿀 때 열일곱 파일에 흩어진 문자열을 찾아다녔다.
도메인을 옮길 때 또 그러지 않으려고 여기로 모은다. 이 모듈은 표준 라이브러리
말고 아무것도 import 하지 않는다 — models.py 와 같은 규칙이다.

도메인은 아직 waffletrip.com 이다(2026-09-25 사장님: "도메인은 그대로 해도 돼").
peopleroad.com·.kr 은 타인 소유. 옮기는 날 DOMAIN 한 줄과 tools/oauth-worker.js 의
ALLOWED_ORIGIN(자바스크립트라 여기서 못 읽는다)만 바꾸면 된다.
"""
from __future__ import annotations

import os

SITE_NAME = "피플로드"
SITE_NAME_EN = "PeopleRoad"
SITE_TAGLINE = "여행과 연예, 사람이 다니는 길"
# 인터넷신문 미등록 상태다. 스스로를 '신문'이라 부르는 공개 문장은 두지 않는다.
SITE_KIND = "여행·연예 문화 전문 매체"
OWNER = "피플레이"                      # 운영사. 여행사이자 마케팅 대행사

DOMAIN = os.environ.get("WAFFLE_SITE_DOMAIN", "waffletrip.com")
# 정식 주소. 커스텀 도메인이 붙기 전에는 실제로 열리는 곳을 가리켜야 한다 —
# canonical 이 안 열리는 도메인을 가리키면 검색엔진이 색인을 못 한다.
SITE_URL = os.environ.get("WAFFLE_SITE_URL", f"https://{DOMAIN}").rstrip("/")
CONTACT_EMAIL = "peoplay@thepeoplay.com"

# 수집 봇의 이름. 매체 소개 쪽이 이 이름을 밝히고, 소스 robots.txt 검토 기록도 이 이름을 쓴다.
BOT_UA = f"{SITE_NAME_EN}Bot/1.0 (+{SITE_URL}/about/)"

# 발행 정보. 신문법 시행령이 인터넷신문 지면에 밝히라고 하는 것들 — 발행인·편집인·
# 청소년보호책임자·등록번호·등록일·발행소. 정해지는 대로 여기만 채우면 푸터와
# 청소년보호정책 쪽에 나간다. 비어 있는 항목은 지면에 나가지 않는다.
# 등록번호·등록일은 2027년 1월 등록 뒤에 생긴다(docs/PEOPLEROAD.md §5).
PUBLISHER = ""        # 발행인
EDITOR = ""           # 편집인
YOUTH_OFFICER = ""    # 청소년보호책임자
REG_NO = ""           # 인터넷신문 등록번호
REG_DATE = ""         # 등록일 (예: 2027-01-15)
ADDRESS = ""          # 발행소 주소


def legal_lines() -> list[str]:
    """푸터에 넣을 "발행인 ○○○" 식 조각. 값이 있는 것만."""
    import sys
    me = sys.modules[__name__]
    pairs = (("발행인", me.PUBLISHER), ("편집인", me.EDITOR),
             ("청소년보호책임자", me.YOUTH_OFFICER),
             ("등록번호", me.REG_NO), ("등록일", me.REG_DATE), ("발행소", me.ADDRESS))
    return [f"{label} {value.strip()}" for label, value in pairs if value and value.strip()]
