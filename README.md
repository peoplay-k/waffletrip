# 피플로드 (PeopleRoad)

여행과 연예, 사람이 다니는 길 — **여행·연예 문화 전문 매체**. 옛 이름 와플트립(2026-09-25 전).
운영사 피플레이. 사이트 https://waffletrip.com (도메인은 그대로 씀).

전체 그림·결정·로드맵은 **[docs/PEOPLEROAD.md](docs/PEOPLEROAD.md)**, 파이프라인 인수인계는
[인수인계.md](인수인계.md), 매일 해설을 쓰는 예약 에이전트의 지침은
[docs/DAILY_COMMENTARY.md](docs/DAILY_COMMENTARY.md).

## 구조

```
피플로드
├─ 여행  /travel/   지역면 10곳(/guam/ …) × 부문 4개(뉴스 /news/ · 업계·피플 /biz/ · 기획·연재 /feature/ · 통계·리포트 /data/) + 도시면(/city/tokyo/ …)
├─ 연예  /ent/      영화·드라마 /ent/movie/ · 음악·공연 /ent/music/ · 스타의 여행 /ent/startrip/ (피플레이와 함께한 스타 표)
│                   옛 주소 /issue/ /world/ /policy/ /people/ /ent/drama/ /ent/star/ 는 새 부문으로 넘어간다
└─ 매체  /about/ /ethics/ /contact/ /privacy/ /youth/ /subscribe/ /search/
```

기사 세 등급: **A** 사실 데이터(환율·날씨, 자동) · **B** 큐레이션(제목 + 두 문장 + 원문 링크,
자동, 검색 색인 제외) · **C** 우리가 쓴 글(여행 해설은 AI 가 지침대로, 연예·취재는 편집실에서 사람이).

## 매일 도는 것 (`.github/workflows/daily.yml`, 08:00 KST)

```
수집(src.collect) → 원문 해결 → 급상승 → 편집(src.edit) → 사진 반입(tools/photo_intake.py)
→ 해설 발행(src.publish_drafts) → 기사거리(tools/story_material.py) → 영상 → 빌드(src.build)
→ 점검·건강검진 → 발행 이력 커밋 → Pages 배포 → 인스타 릴스 → IndexNow
```

## 로컬

```bash
pip install -r requirements.txt
python -m pytest -q                       # 629개. 전부 통과해야 한다
python -m src.build                       # public/ 에 사이트
python tools/admin.py                     # 편집실 http://localhost:8080 (저장 = 커밋·푸시)
python tools/new_article.py ent "제목" --category=movie   # 연예 초안
python tools/make_brand_images.py         # 로고·OG·파비콘 재생성 (src/brand.py 의 이름으로)
```

## 지키는 것

- 지어내지 않는다 — 기자 이름도, 사실도, 스타 명단도.
- 사진은 직접 찍은 것만. 얼굴이 보이면 안 나간다(자동 검사 + 사람 승인). 연예인은 동의가 먼저.
- 네이버 뉴스 제휴 심사까지 지면에 상품 링크·전화번호·광고를 두지 않는다(`site.COMMERCIAL_LINKS`).
- 남의 문장을 옮기지 않는다. 사실만 가져다 우리 문장으로 쓰고 원문 주소를 건다.
- `data/published_index.json` 은 재발행을 막는 유일한 장치다. 손대지 않는다.

이름·도메인·연락처의 정본은 `src/brand.py` 하나다.
