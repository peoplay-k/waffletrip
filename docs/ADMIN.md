# 편집실 — 아이디·비밀번호로 로그인해서 기사·카테고리·지역·기자·홈을 고친다

주소: **https://waffletrip.com/admin/** (편집실 서버로 넘어간다)

2026-10-30 새로 만들었다. 사장님: "어드민을 완전 새롭게 만들어서 카테고리 등도 내가 실제로 바꾸고
이렇게 해야지 … 계속 내가 수정해서 바꾸고 해야 해." 예전 편집실(Sveltia, GitHub 토큰으로 로그인)은
걷었다. 설계는 `docs/ADMIN_DESIGN.md`.

- 로그인: 아이디·비밀번호. 사장님(관리자)과 기자(권한 나눔).
- 고칠 수 있는 것: 기사 쓰기·고치기·내리기, 카테고리(여행·문화 부문)·지역면·채널 이름과 소개,
  기자·서명, 홈 화면 배치.
- 저장하면 저장소에 커밋되고, 그 커밋이 발행을 깨워 **10분 안팎에** 지면이 바뀐다.

---

## 처음 한 번 — 설치 (사장님, 20분)

편집실은 Cloudflare(무료)에서 돈다. 아래 네 값을 **저장소 Secrets 에만** 넣는다.
**채팅·카톡·메일·문서에 붙여 넣지 않는다.**

넣는 곳: GitHub → `peoplay-k/waffletrip` → **Settings → Secrets and variables → Actions →
New repository secret**. 이름은 아래 그대로, 값은 각 단계에서 복사한 것.

### 1. Cloudflare 계정과 `CLOUDFLARE_ACCOUNT_ID`

1. https://dash.cloudflare.com/sign-up 에서 무료 계정을 만든다(이미 있으면 로그인).
2. 왼쪽 **Workers & Pages** 를 한 번 연다. 처음이면 `…workers.dev` 하위 주소를 정하라고 한다 —
   아무 영문 이름(예: `peopleroad`)으로 정한다. 편집실 주소가 `peopleroad-admin.<그 이름>.workers.dev` 가 된다.
3. 같은 화면 오른쪽(또는 계정 홈)의 **Account ID** 를 복사 → Secret 이름 **`CLOUDFLARE_ACCOUNT_ID`**.

### 2. `CLOUDFLARE_API_TOKEN`

1. https://dash.cloudflare.com/profile/api-tokens → **Create Token**.
2. **Edit Cloudflare Workers** 템플릿 옆 **Use template**.
3. Permissions 에 줄을 하나 더해 **Account · D1 · Edit** 를 넣는다.
4. Account Resources: 내 계정. Zone Resources: All zones(그대로).
5. **Continue to summary → Create Token** → 나온 값을 복사 → Secret 이름 **`CLOUDFLARE_API_TOKEN`**.

### 3. `ADMIN_GITHUB_TOKEN` — 편집실 서버가 저장소에 저장할 때 쓰는 열쇠

사람이 로그인할 때 쓰는 것이 아니다. 서버 안에만 들어가고, 기자들은 보지 못한다.

1. https://github.com/settings/personal-access-tokens/new
2. Token name `피플로드 편집실 서버`, Expiration 은 고를 수 있는 가장 긴 기간.
3. Resource owner **peoplay-k**, Repository access **Only select repositories → waffletrip**.
4. Repository permissions: **Contents → Read and write**, **Actions → Read and write**. 다른 것은 주지 않는다.
5. **Generate token** → 복사 → Secret 이름 **`ADMIN_GITHUB_TOKEN`**.
6. 만료되면 같은 방법으로 새로 만들어 이 Secret 만 바꾸고, 아래 4번의 Run workflow 를 한 번 누른다.

### 4. `ADMIN_SETUP_CODE` 와 배포

1. 아무 문구(예: 남이 못 맞힐 긴 문장)를 정해 Secret 이름 **`ADMIN_SETUP_CODE`** 로 넣는다.
   첫 관리자 계정을 만들 때 한 번 쓰는 암호다. 계정이 하나라도 생기면 더는 통하지 않는다.
2. GitHub → **Actions → 편집실 배포 → Run workflow**.
3. 초록으로 끝나면 그 실행의 요약(Summary)에 편집실 주소가 나온다.
   몇 분 뒤 https://waffletrip.com/admin/ 도 그 주소로 넘어간다.

### 5. 첫 관리자 계정

1. 편집실 주소를 연다 → **처음 설치** 화면.
2. 설치 코드(4-1 의 문구), 사장님 아이디·이름·비밀번호를 넣는다. 끝.
3. 이후 기자 계정은 편집실 **계정** 메뉴에서 만든다(기자에게 아이디와 첫 비밀번호를 알려 주고,
   기자는 로그인해서 자기 비밀번호를 바꾼다).

---

## 안 될 때

- **Actions 실행이 '건너뜀' 으로 끝남** — Secrets 네 개 중 빠진 것이 요약에 나온다.
- **'D1 데이터베이스 id 를 못 얻었다'** — 2-3 의 D1 Edit 줄이 빠졌다. 토큰을 다시 만든다.
- **'workers.dev 주소를 못 찾았다'** — 1-2 를 안 했다. Workers & Pages 를 한 번 열고 다시 Run workflow.
- **편집실에서 저장이 '저장소 권한 없음'** — 3 의 토큰이 만료됐거나 권한이 빠졌다.
- 비밀번호를 잊은 기자 — 관리자가 계정 메뉴에서 새 비밀번호를 정해 준다.
- 사장님 비밀번호를 잊음 — 다른 관리자 계정이 있으면 그 계정으로 바꾼다. 없으면 요청한다.
