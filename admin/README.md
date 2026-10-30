# 피플로드 편집실 (admin/)

피플로드(waffletrip.com)의 관리자 화면이다. 아이디·비밀번호로 들어가서

- **기사** 쓰기·고치기·검토요청·발행대기(승인)·내리기·다시 올리기
- **구조**(config/site.json): 여행 부문 · 문화 부문 · 문화 분류 규칙 · 지역 · 기자(서명) · 홈 배치
- **계정**: 관리자(사장님)와 기자. 기자는 자기가 만든 기사만, 작성중·검토요청일 때만 고친다
- **발행 상태**: GitHub Actions '매일 발행'(daily.yml) 최근 실행, 관리자는 '지금 발행'
- **기록**: 누가 언제 무엇을 바꿨는지

을 한다. 설계(계약)는 `docs/ADMIN_DESIGN.md` 다.

```
브라우저 ──(쿠키)──> 편집실 Worker (화면 public/ + API src/)  ── D1: 계정·세션·로그인 시도·기록
                                │
                                └─(서버만 아는 GITHUB_TOKEN)─> peoplay-k/waffletrip (main)
                                      content/review/*.md · config/site.json · content/uploads/
                                      → daily.yml 이 발행 → waffletrip.com
```

기사·구조의 정본은 저장소다. 편집실에서 저장하면 `편집실(<아이디>): <무엇을>` 커밋이 생기고,
그 커밋이 곧 감사 기록이다. D1 에는 계정·세션·잠금·화면용 기록·목록 캐시만 둔다.

## 폴더

| 경로 | 내용 |
|---|---|
| `wrangler.toml` | Worker 설정. D1 바인딩 `DB`, 화면 파일 `public/`, 변수 `GITHUB_REPO`·`GITHUB_BRANCH`·`GITHUB_API` |
| `src/index.js` | 라우터·CSRF 확인·보안 헤더 |
| `src/auth.js` | 로그인·로그아웃·세션·잠금·첫 설치·내 비밀번호 |
| `src/articles.js` | 기사 목록·읽기·저장·새 기사·사진 올리기·사진 미리보기, **권한표** |
| `src/site.js` | 구조 파일 읽기·저장 |
| `src/users.js` | 계정 관리·변경 기록·발행 상태 |
| `src/frontmatter.js` | 원고 앞머리(YAML) 읽기·쓰기 — 고치지 않은 칸은 글자 그대로 둔다 |
| `src/github.js` | GitHub REST·GraphQL |
| `public/` | 화면(빌드 없음). `index.html`·`app.js`·`app.css`, `js/` 화면별 모듈 |
| `public/shared/siteconfig.js` | 구조 검사·바뀐 점 요약. **화면과 서버가 같이 쓴다** |
| `migrations/` | D1 스키마 |
| `test/` | 단위 테스트, 가짜 GitHub(`mock-github.mjs`), 끝에서 끝 테스트(`e2e.test.mjs`) |

## 로컬에서 띄우기

Node 20 이상.

```sh
cd admin
npm install
```

**가짜 GitHub 로**(인터넷·토큰 없이 화면을 만져 볼 때):

```sh
npm run dev:mock
```

저장소의 `content/review`·`config/site.json` 을 임시 폴더에 복사하고, 가짜 GitHub 와
`wrangler dev --local`(D1 도 임시 폴더)을 띄운 뒤 주소를 알려 준다. 설치 코드는 `test`.
진짜 저장소에는 아무것도 쓰지 않는다. Ctrl+C 로 끄면 임시 폴더는 지운다.

**진짜 GitHub 로**: `admin/.dev.vars` 를 만들고(저장소에 올리지 않는다 — .gitignore 에 있다)

```
GITHUB_TOKEN=github_pat_...
ADMIN_SETUP_CODE=아무-문구
```

```sh
npm run migrate:local
npm run dev
```

http://localhost:8787 을 연다. 처음에는 첫 설치 화면이 나온다. **이 경우 저장하면 진짜 저장소에 커밋된다.**
다른 브랜치로 시험하려면 `.dev.vars` 에 `GITHUB_BRANCH=시험-브랜치` 를 더한다.

## 테스트

```sh
npm test            # 단위 + 끝에서 끝
npm run test:unit   # 단위만(몇 초)
npm run test:e2e    # wrangler dev + 가짜 GitHub + Playwright(크로뮴)
```

- 단위: 앞머리 읽기·쓰기를 `content/review` 의 **진짜 원고 전부**로 돌린다(고치지 않고 쓰면 글자 하나
  다르지 않은지, 다시 쓴 앞머리를 PyYAML 도 같게 읽는지 — 파이썬과 PyYAML 이 없으면 그 검사만 건너뛴다).
  구조 검사 규칙, 권한표, 비밀번호 해시도 본다.
- 끝에서 끝: 첫 설치 → 로그인·로그아웃 → 기자 계정 → 기자가 쓰고 검토요청 → 기자 권한 403 →
  관리자 승인·내리기(바뀌는 것은 status 한 줄뿐인지 바이트로 비교) → 409(그사이 바뀜) → 사진 →
  구조 왕복·검증 오류 → 발행 상태 → 비밀번호·중지 → 로그인 잠금.
- Playwright 는 `require('playwright')` 로 찾는다(전역 설치). 크로뮴이 없으면 `npx playwright install chromium`.

## 배포

`.github/workflows/admin.yml` 이 `admin/**` 가 바뀌면 한다: 단위 테스트 → D1 이 없으면 만들고 id 를
`wrangler.toml` 에 넣음(저장소의 id 는 자리표시) → `migrations apply --remote` → `wrangler deploy` →
비밀값 넣기. 저장소 Secrets 에 필요한 것(처음 한 번, 사장님): `CLOUDFLARE_API_TOKEN`,
`CLOUDFLARE_ACCOUNT_ID`, `ADMIN_GITHUB_TOKEN`, `ADMIN_SETUP_CODE`. 자세한 순서는 `docs/ADMIN.md`.

손으로 할 때:

```sh
npx wrangler login
npx wrangler d1 create peopleroad-admin          # 나온 database_id 를 wrangler.toml 에
npx wrangler d1 migrations apply peopleroad-admin --remote
npx wrangler deploy
npx wrangler secret put GITHUB_TOKEN             # 붙여 넣기(화면에 안 보임)
npx wrangler secret put ADMIN_SETUP_CODE
```

### Worker 비밀값·변수

| 이름 | 종류 | 뜻 |
|---|---|---|
| `GITHUB_TOKEN` | 비밀값 | 저장소에 커밋하는 토큰. fine-grained, 이 저장소만: **Contents 읽기·쓰기, Actions 읽기·쓰기**(발행 상태·지금 발행), Metadata 읽기 |
| `ADMIN_SETUP_CODE` | 비밀값 | 첫 관리자를 만들 때 넣는 문구. 계정이 하나라도 생기면 더는 쓰이지 않는다 |
| `GITHUB_REPO` | 변수 | 기본 `peoplay-k/waffletrip` |
| `GITHUB_BRANCH` | 변수 | 기본 `main` |
| `GITHUB_API` | 변수 | 기본 `https://api.github.com`. 테스트가 가짜 GitHub 로 바꾼다 |

## 권한(서버가 판단한다 — 화면은 믿지 않는다)

| | 관리자 | 기자 |
|---|---|---|
| 기사 보기 | 전부 | 전부 |
| 새 기사 | 작성중·검토요청·발행대기 | 작성중·검토요청 |
| 기사 고치기 | 전부 | 자기가 만든 것(`author`) 중 작성중·검토요청 |
| 발행대기·내리기·다시 올리기 | O | X (403) |
| 구조·계정·기록·지금 발행 | O | X (403) |
| 내 비밀번호 | O | O |

- 이미 발행된 기사(`published_id` 가 있는 것)는 '발행됨'과 '내림' 사이만 오간다. 작성중으로 되돌리면
  파이프라인이 헷갈리기 때문이다. 발행된 적 없는 원고를 '발행됨'으로 둘 수도 없다(발행은 파이프라인이 붙인다).
- 파이프라인 칸(`id`·`published_id`·`published_on`·`sources`·`reason`·`duplicate_of`·`photo_note`)과
  `author` 는 화면이 무엇을 보내든 서버가 원래 값을 지킨다. 화면에 없는 모르는 칸도 그대로 남는다.

## 보안 메모

- 비밀번호: PBKDF2-SHA256, 16바이트 소금, 시간 차 없는 비교. 횟수는 `wrangler.toml` 의 `PASSWORD_ITERATIONS`
  (기본 **20,000회** — 무료 요금제의 요청당 CPU 10ms 안에 든다. 100,000회는 약 18ms 라 1102 오류가 난다.
  유료 요금제면 100,000 으로 올린다). 저장 꼴 `pbkdf2-sha256$<횟수>$<해시>` — 횟수를 바꿔도 옛 비밀번호가
  맞고, 다음 로그인 때 새 횟수로 다시 저장된다. 최소 **10자**.
- 세션: 32바이트 난수 토큰. D1 에는 SHA-256 만 둔다. 쿠키 `HttpOnly; Secure; SameSite=Strict; Path=/`, 30일.
  비밀번호를 바꾸면 다른 기기 세션은 끊고, 관리자가 재설정·역할 변경·중지하면 그 사람 세션을 모두 끊는다.
- 로그인 잠금: 15분 안에 5번 틀리면 **그 아이디**와 **그 주소(IP)** 를 각각 15분 잠근다. 주소는 Cloudflare 가
  붙이는 `CF-Connecting-IP`(바깥에서 보낸 같은 이름 헤더는 Cloudflare 가 덮어쓴다). 없는 아이디도 같은 시간이 걸린다.
  관리자가 비밀번호를 재설정하면 그 아이디 잠금도 풀린다. 첫 설치 코드도 같은 방식으로 잠근다.
- CSRF: 쓰기 요청은 `X-Requested-With: peopleroad` 헤더가 있어야 하고, `Origin` 이 있으면 같은 주소여야 한다.
- 모든 응답에 CSP(`default-src 'self'`, 인라인 스크립트·스타일 없음)·`X-Frame-Options: DENY`·`nosniff`.
  API 응답은 `Cache-Control: no-store`.
- 화면은 기사 글자를 늘 `textContent` 로 넣는다. 본문 미리보기는 지면의 `src/render/md.py` 처럼 이스케이프를
  먼저 하고 구조를 나중에 넣는다.
- 사진은 브라우저가 보낸 종류를 믿지 않고 파일 머리 바이트로 JPG·PNG·WEBP 만 받는다(10MB 까지).
  `content/uploads/<날짜>_<난수>.<확장자>` 로 커밋되고, 사진 반입(tools/photo_intake.py)이 검사한다.
  **공개 저장소라 올린 원본은 지워도 이력에 남는다.**
- GitHub 토큰은 Worker 비밀값으로만 있다. 화면·기자는 보지 않는다.

## 알아둘 점

- **구조만 바꾸면 지면이 바로 안 바뀐다.** daily.yml 은 `content/review/**` 가 바뀔 때만 저절로 돈다.
  구조를 저장한 뒤 바로 반영하려면 '발행 상태 → 지금 발행'(관리자)을 누른다. 다음 기사 저장이나 아침 예약 발행 때도 반영된다.
- 같은 기사를 두 사람이 동시에 고치면 나중에 저장한 쪽이 409 를 받는다("그사이 다른 사람이 고쳤습니다").
  화면이 '내 본문 복사'와 '새로 불러오기'를 준다. 구조 저장도 같다.
- 기사 목록은 폴더 해시가 같으면 D1 에 둔 목록을 그대로 내고, 바뀌었으면 바뀐 파일만 GitHub 에서 읽는다
  (파일 내용 해시별 캐시). 처음 한 번만 폴더 전체를 GraphQL 한 번으로 읽는다.
- 앞머리를 못 읽는 원고는 목록에 '읽기 오류'로 보이고, 편집실에서는 고칠 수 없다(GitHub 에서 직접 고친다).
- 아무것도 바꾸지 않고 저장하면 커밋하지 않는다.
- **CPU 한도**: Workers 무료 요금제는 요청당 CPU 10ms. 그래서 비밀번호 해시는 20,000회(약 5ms)로 둔다(위 보안 메모).
  그래도 로그인이 'Worker exceeded resource limits'(1102)로 실패하면 `PASSWORD_ITERATIONS` 를 낮추지 말고
  Workers Paid 요금제로 올린 뒤 100000 으로 올린다.
