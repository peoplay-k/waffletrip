# 편집실 로그인 · 사진 업로드 · 채널(여행/연예) — 설계

2026-09-16. 사장님 지시: "지금 있는 것에서 수정한다. 구조를 살짝 바꾼다.
admin 에서 글쓰기·수정·사진 업로드·카테고리 수정이 되어야 한다."

같은 날 결정: 로그인은 **Decap + Cloudflare 워커**(원래 계획), 사진은
**웹 편집실 업로드도 허용**(원본이 공개 저장소 이력에 남는 것을 감수, 대신
CI 얼굴 검사로 지면에는 안 나감).

이름 변경(피플포스트 등)과 상품 링크 제거는 이 설계 밖이다 — 매체 방향
결정 ①②가 나오면 따로 한다.

## 0. 지금 상태

- 웹 편집실 `https://waffletrip.com/admin/` — Decap CMS. `static/admin/config.yml`,
  `static/admin/index.html`. 빌드가 `public/admin/` 으로 복사한다. **로그인
  중개기(`base_url`)가 `REPLACE-ME` 라 들어갈 수 없다.** 중개기 코드는
  `tools/oauth-worker.js` 에 완성돼 있다.
- 맥 편집실 `tools/admin.py` — localhost:8080. `content/review/*.md` 를 읽고
  쓴다. **저장만 하고 커밋·푸시는 안 한다.**
- 기사 = `content/review/*.md` (YAML 프론트매터 + 마크다운). `src/publish_drafts.py`
  가 `status: approved` 인 것을 C등급 Item 으로 내보낸다. 프론트매터 `photo`
  (`/img/...` 웹 경로)는 그대로 Item.photo 가 된다.
- 사진 = `assets/photos/<region>/*.webp` + `assets/photos/manifest.json`.
  `tools/photo_prepare.py`(OpenCV, 로컬 전용)만이 매니페스트에 쓴다. 두 편집실
  모두 업로드 금지(얼굴 검사 우회 때문). 테스트가 그걸 강제한다.
- 분류 = 지역 10곳(`models.REGIONS`) × 부문 7개(`topics.TOPICS`, 렌더 시점 계산).
  전부 여행이다.
- 워크플로 `daily.yml`: `content/review/**` 푸시 → 즉시 실행. 순서
  테스트 → 수집 → 편집 → **해설 발행** → 기사거리 → 영상 → 빌드 → 점검 →
  발행 이력 커밋 → 배포.

## 1. 로그인 (A)

바꾸는 것은 `static/admin/config.yml` 의 `base_url` 한 줄이다. 코드 변경 없음.

사장님이 하는 것(한 번, 10분) — `docs/P3-DECISIONS.md` §14 그대로:

1. Cloudflare → Workers → Create → `tools/oauth-worker.js` 내용 붙여넣기 → Deploy.
   워커 주소 `https://<이름>.<계정>.workers.dev` 가 생긴다.
2. GitHub → Settings → Developer settings → OAuth Apps → New.
   Homepage `https://waffletrip.com/`, Callback `https://<워커주소>/callback`.
3. Worker → Settings → Variables → **Secret** 으로 `GITHUB_CLIENT_ID`,
   `GITHUB_CLIENT_SECRET`.
4. 워커 주소만 나에게 알려준다. Secret 은 절대 채팅·저장소에 넣지 않는다.

내가 하는 것: `base_url` 을 워커 주소로 바꿔 푸시하고, 브라우저로 실제 로그인
→ 기사 목록이 뜨는 것까지 눈으로 확인한 뒤에만 "된다"고 보고한다.

## 2. 사진 업로드 (B)

### 2.1 편집실 쪽

`config.yml`:

- `media_folder: content/uploads`, `public_folder: /content/uploads`.
- 기사 필드에 `photo`(image 위젯, 선택) 하나 — **대표 사진 한 장**. 본문 안
  이미지는 이번에 안 받는다(힌트에 적는다).
- `photo_hero`(boolean, 기본 false) — 1면용 풍경이면 켠다 → 매니페스트 `hero`.
- `photo_note`(string, 읽기용) — CI 검사 결과가 여기 적힌다. 편집자가 기사를 다시
  열면 "얼굴 2건 검출 — 지면에 싣지 않았다" 를 본다.
- 힌트 문구: "직접 찍은 사진만. 얼굴이 보이면 지면에 안 나갑니다. 공개 저장소라
  올린 원본은 지워도 이력에 남습니다."

맥 편집실 `tools/admin.py`:

- 같은 `photo` 업로드칸. **저장 전에 로컬에서 먼저 `photo_prepare.inspect()` 를
  돌려** 얼굴·사람이 잡히면 그 자리에서 거부한다(커밋되지 않는다). 통과분은
  `content/uploads/` 에 두고 프론트매터에 `/content/uploads/<파일>` 을 적는다 —
  웹 편집실과 같은 형식이라 CI 가 같은 길로 굽는다.
- 저장 = 커밋 + 푸시(`git add content/review content/uploads && git commit && git push`).
  푸시가 거부되면 `pull --rebase --autostash` 후 한 번 더. 실패하면 화면에 그대로
  보여준다 — 조용히 "저장됨"으로 넘기지 않는다.

### 2.2 CI 반입 `tools/photo_intake.py` (새 파일)

`daily.yml` 에 **해설 발행 바로 앞** `사진 반입` 단계로 넣는다.
publish_drafts 가 프론트매터 `photo` 를 읽기 전에 웹 경로로 바꿔 놓아야 한다.

동작 (기사 단위):

1. `content/review/*.md` 중 `photo` 가 `/content/uploads/` 로 시작하는 것을 찾는다.
2. 파일이 없으면 `photo` 를 비우고 `photo_note: "업로드 파일을 찾지 못했다"`.
3. `photo_prepare.inspect()` — EXIF 회전 + 4방향 얼굴 + 사람 면적. **검출기가
   최종이다.** 로컬 도구와 달리 여기엔 시트를 볼 사람이 없으므로 fail-closed.
   - 통과: `photo_prepare.bake()` 로 `assets/photos/<region>/up_<stem>.webp`
     (1600px, q80). 매니페스트에 `{src: 업로드경로, file, bytes, baked_at,
     origin: "편집실 업로드", hero}` 추가. 프론트매터 `photo: /img/<region>/up_<stem>.webp`,
     `photo_note: "통과"`. `data/photos/used.json[웹경로] = 기사 id` — 이 사진이
     다른 기사에 자동 배정되지 않게.
   - 차단: 프론트매터 `photo` 비움, `photo_note: "<사유> — 지면에 싣지 않았다"`.
   - 두 경우 모두 `content/uploads/` 의 원본을 지운다(`git rm`). 폴더는 항상 비어
     있어야 한다. 이력에는 남는다 — 사장님이 감수한 부분.
4. 연예 기사(3장)는 region 이 없으므로 `assets/photos/ent/` 에 굽고 매니페스트
   키도 `ent` 다. 자동 배정 풀에는 들어가지 않는다(ent 는 지역면이 아니다).
5. 결과를 `data/photo_intake.json` 에 누적한다(파일·기사·판정·시각). 건강검진이
   "차단 n건"을 같이 적는다.

의존성: `requirements.txt` 에 `opencv-python-headless`, `numpy` 추가. 첫 빌드만
느리고 pip 캐시 뒤엔 수 초. `tests/test_photo_prepare.py` 의 `importorskip` 은
그대로 둔다(있으면 돈다).

커밋: `발행 이력 커밋` 의 `git add` 에 `assets/photos content/uploads
data/photos/used.json data/photo_intake.json` 을 더한다. 그리고 `git add -A
content/uploads` 가 삭제를 담게 한다.

### 2.3 안전선

- 업로드된 사진의 출처는 매니페스트 `origin: "편집실 업로드"` 로 남는다.
  `photo_prepare.origin_of()` 의 NAS/자사 뿌리 규칙은 로컬 도구에만 적용된다 —
  편집실 업로드는 사람이 직접 고른 것이므로 그 사람이 출처를 책임진다. 캡션은
  기존대로 "직접 촬영".
- 검출기 통과를 100% 믿지 않는다(로컬 도구 주석의 실측). 그래서 지면 캡션과
  기사 프론트매터에 `up_` 접두사로 업로드 사진임을 남겨, 문제가 생기면 한 번에
  걷어낼 수 있게 한다.

## 3. 채널: 여행 / 연예 (C)

"살짝" 바꾼다. 여행은 그대로, 옆에 연예를 세운다.

- `models.Item` 에 `channel: str = "travel"` (`travel`|`ent`), `category: str = ""`
  (연예 부문 id). `item_to_dict/from_dict` 에 기본값으로 넣는다 — 기존 jsonl 은
  전부 travel 로 읽힌다.
- `topics.py`: `ENT_TOPICS = (("movie","영화"), ("drama","드라마·방송"),
  ("music","음악·공연"), ("star","인물"))`. `people` 은 여행 쪽 피플·오피니언이
  이미 쓰므로 인물은 `star`. `topic_of()` 는 channel 이 ent 면 category(없으면
  `star`)를 돌려준다.
- URL: 연예 기사는 `/ent/<id8>-<slug>/`, 부문 페이지 `/ent/`, `/ent/movie/` …
  `article_url()` 이 channel 을 본다. 지역면·도시면·자동 사진 배정·환율 패널은
  region 기준이라 연예 기사가 섞이지 않는다.
- 상단 메뉴 `base.html`: `여행 ▸ 여행BIZ … 통계·리포트 | 연예 ▸ 영화 드라마·방송
  음악·공연 인물`. 홈 `index.html`: 연예 기사가 있을 때만 "연예" 블록 하나.
  없으면 아무것도 안 그린다(빈 블록 금지).
- RSS·사이트맵·검색·llms.txt: 기존 필터(C등급 포함) 그대로라 연예도 들어간다.
- `publish_drafts.py`: 프론트매터 `channel`·`category` 를 Item 으로 옮긴다.
  travel 인데 region 이 `REGIONS` 밖이면 건너뛰고 사유를 찍는다(지금은 빈 region
  이 조용히 통과한다). ent 는 region 을 무시한다.
- 편집실 두 곳: `채널` select(여행/연예, 기본 여행), `연예 부문` select(선택).
  `지역면` 은 select 그대로 두되 힌트에 "연예 기사는 아무거나 두어도 무시된다".
  Decap 은 조건부 필드가 없다.
- 데스크/서명: 연예 기사의 기본 서명은 `와플트립 문화부` (`desks.py` 에 추가).
  실명 바이라인 체계는 결정 ③ 뒤 별도.

## 4. 테스트

- `test_render_site.py`: 편집실 설정 검사 셋을 고친다 — media_folder 는
  `content/uploads`, image 위젯은 `photo` 필드 하나만 허용, repo/branch/folder 는
  그대로.
- `test_photo_intake.py`(새): 가짜 검사기(monkeypatch)로 통과/차단 두 길 —
  프론트매터 재작성, 매니페스트 항목, used.json 등록, 업로드 원본 삭제, 파일
  없음 처리, ent 기사의 `assets/photos/ent/`.
- `test_admin.py`(새, 로컬 편집실): 업로드가 검사기 차단 시 파일이 남지 않는 것,
  저장이 커밋 호출로 이어지는 것(subprocess 는 가짜).
- `test_models.py`/`test_publish_drafts.py`: channel/category 왕복, 빈 region
  travel 기사 차단, ent 기사 통과.
- `test_render_site.py`/`test_topics.py`: 연예 기사가 `/ent/movie/` 와 메뉴에
  나오고 지역면·여행 부문면에는 없는 것, 연예 기사 0건이면 홈에 블록이 없는 것.

## 5. 순서와 시간

1. **A** — 워커 주소를 받는 즉시 한 줄 + 로그인 실물 확인. 사장님 10분 + 내 10분.
2. **B** — 반입 도구 + 편집실 두 곳 + 워크플로 + 테스트. 2~3시간.
3. **C** — 모델·부문·URL·메뉴·홈·편집실·테스트. 3~4시간.

B 와 C 는 A 를 기다리지 않는다. 각각 따로 커밋한다.
