# 소스 실측 조사 — 2026-08-31

Task 1 Step 4 결과. 스펙 8절 후보 매체 14개(7개 지역 × 대략 2개)를 실제로 두드려본 기록이다.
스펙의 목록은 후보일 뿐이었고, 아래 표가 검증된 사실이다. 나중에 소스를 늘릴 때 이미 확인한
것을 다시 두드리지 않도록 죽은 것도 사유와 함께 전부 남긴다.

## 방법

1. 각 매체 홈페이지 HTML에서 `<link type="application/rss+xml">` 태그를 정규식으로 찾는다.
2. 태그가 없으면 `/rss`, `/feed`, `/feed/`, `/rss.xml`, `/feeds/all.rss`, `/?feed=rss2`,
   `/arc/outboundfeeds/rss/`(Arc Publishing/Gray Media 계열), `/rss/allArticle.xml`(국내 지역언론
   CMS 계열) 등 흔한 경로를 직접 두드렸다.
3. 찾은 URL 14개를 `candidates.txt`에 `id<TAB>url` 형식으로 넣고 `tools/check_sources.py`로
   최종 판정했다 — 이 스크립트가 **robots.txt 확인 → 실제 응답 확인(RSS 파싱 후 항목 수)** 순서로
   최종 판정을 내리는 유일한 근거다. UA는 `WaffleTripBot/1.0 (+https://waffletrip.com/about/)`.

## 최종 판정 표 (`tools/check_sources.py candidates.txt` 실행 결과)

| id | 지역 | 매체명 | URL | 판정 | 사유 |
|---|---|---|---|---|---|
| guam_post | guam | The Guam Daily Post | `https://www.postguam.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory` | 보류(X) | HTTP 429 — 아래 "postguam.com 참고" 항목 참조 |
| guam_kuam | guam | KUAM News | `https://www.kuam.com/feed` | 죽음(X) | RSS/JSON 아님 (HTML만 반환) — SPA라 흔한 경로 전부 앱쉘 HTML 200 반환 |
| guam_pacific_island_times | guam | Pacific Island Times | `https://www.pacificislandtimes.com/blog-feed.xml` | **사용가능(OK)** | RSS 항목 20개 |
| saipan_variety | saipan | Marianas Variety | `https://www.mvariety.com/search/?f=rss&t=article&l=50&s=start_time&sd=desc&k%5B%5D=%23topstory` | robots 금지(X) | robots.txt가 `User-agent: * / Disallow: /` — 사이트 전체를 모든 크롤러에게 차단 |
| saipan_tribune | saipan | Saipan Tribune | `https://www.saipantribune.com/index.php/feed/` | 죽음(X) | 연결실패: ReadTimeout — 아래 "saipantribune.com 참고" 항목 참조 |
| hawaii_news_now | hawaii | Hawaii News Now | `https://www.hawaiinewsnow.com/arc/outboundfeeds/rss/` | **사용가능(OK)** | RSS 항목 20개 |
| hawaii_beatofhawaii | hawaii | Beat of Hawaii | `https://beatofhawaii.com/feed/` | **사용가능(OK)** | RSS 항목 12개 |
| vietnam_vnexpress | vietnam | VnExpress International (Travel) | `https://e.vnexpress.net/rss/travel.rss` | **사용가능(OK)** | RSS 항목 60개 |
| kota_borneopost | kota | The Borneo Post | `https://www.theborneopost.com/feed/` | 죽음(X) | HTTP 403 — 홈페이지까지 포함해 봇 차단(재요청 시 홈페이지도 403) |
| kota_dailyexpress | kota | Daily Express (Sabah) | `https://www.dailyexpress.com.my/feed/` | 죽음(X) | HTTP 403 — Cloudflare 봇 차단 (robots.txt 요청조차 Cloudflare 챌린지 페이지로 막힘) |
| laos_vientianetimes | laos | Vientiane Times | `https://www.vientianetimes.org.la/feed` | 죽음(X) | HTTP 404 — 홈페이지 전체(42,979자)를 검색해도 feed/rss 언급 전혀 없음, RSS 자체가 없는 것으로 판단 |
| laos_laotiantimes | laos | Laotian Times | `https://laotiantimes.com/feed/` | **사용가능(OK)** | RSS 항목 13개 |
| jeju_jejusori | jeju | 제주의소리 | `https://cdn.jejusori.net/rss/gn_rss_allArticle.xml` | **사용가능(OK)** | RSS 항목 50개 |
| jeju_headline | jeju | 헤드라인제주 | `https://www.headlinejeju.co.kr/rss/allArticle.xml` | robots 금지(X) | robots.txt가 `Disallow: /rss/` — 피드 자체는 정상 응답(HTTP 200, RSS 유효)하지만 규칙 4에 따라 제외 |

**사용 가능 6/14** (`check_sources.py` 실행 시점 기준. `guam_post`는 보류 상태 — 아래 참고)

## 지역별 커버리지

| 지역 | 사용가능 소스 수 | 비고 |
|---|---|---|
| guam | 1 (+ 보류 1) | pacific_island_times 확보. postguam은 429 보류 (아래 참고) |
| saipan | **0** | 후보 2개 모두 탈락 (robots 전면금지 / 연결불안정) — 강제로 채우지 않음 |
| hawaii | 2 | hawaii_news_now, beatofhawaii |
| vietnam | 1 | vnexpress travel |
| kota | **0** | 후보 2개 모두 봇 차단(403) — 강제로 채우지 않음 |
| laos | 1 | laotiantimes (vientianetimes는 RSS 자체가 없음) |
| jeju | 1 | jejusori (headlinejeju는 robots 금지로 제외) |

**saipan, kota 두 지역은 스펙 8절 후보 중 살아있는 뉴스 소스를 하나도 찾지 못했다.** 지시에 따라
억지로 대체 매체를 찾지 않고 이 사실 그대로 기록한다. 두 지역 모두 `data`(환율) 소스만 갖는다.
향후 소스를 늘릴 때 이 두 지역을 우선 검토할 것.

## 상세 노트

### postguam.com — 보류(429), 죽은 게 아닐 가능성 높음

- robots.txt는 확인함: TNCMS 관리자/추적 경로 다수를 금지하지만 `/search/` RSS 경로나 와일드카드
  전체 차단은 없다. **robots는 허용.**
- 홈페이지 `<link>` 태그에서 RSS URL을 정상적으로 찾았고, 조사 초반(1회차) 수동 확인 시
  `https://www.postguam.com` 자체는 HTTP 200으로 응답했다.
- 그러나 이 매체를 조사 과정에서 짧은 시간(약 20분) 안에 6~7회 반복 요청했고, 이후 `check_sources.py`
  실행 시점과 재시도(8초 간격 3회) 모두 `HTTP 429 Too Many Requests`를 받았다.
- **판단**: 우리 쪽 반복 조사가 TownNews/BLOX CMS의 레이트리밋을 건드렸을 가능성이 매우 높다
  (실제 운영에서는 하루 1회 요청이라 문제되지 않을 패턴). "죽은 소스"와는 성격이 다르므로
  `sources.yaml`에는 **아직 넣지 않았다** — 이번 조사에서 실제로 응답을 받지 못했기 때문이다
  (원칙: 응답한 것만 남긴다). 레이트리밋이 풀린 뒤(예: 1시간 후) 재조사해서 성공하면 추가할 것.
  candidates.txt에는 그대로 남겨두어 재조사 시 URL을 다시 찾지 않아도 되게 했다.

### saipantribune.com — 매우 불안정, 이번 조사에서는 죽음으로 판정

- 홈페이지 HTML에서 정상적인 RSS `<link>` 태그 2개를 확인함: `/index.php/feed/`,
  `/index.php/comments/feed/`. CMS는 WordPress로 보인다.
- `curl` 25초 타임아웃으로 한 번은 홈페이지가 9.9초 만에 로드됐고, `/index.php/feed/`도 한 번은
  25초 타임아웃 내에 정상 RSS(항목 10개, `application/rss+xml`)로 응답했다.
- 하지만 그 직후 같은 URL을 20초 타임아웃으로 3연속 재시도했을 때 **3번 모두 완전히 응답 없이
  타임아웃**됐고, `robots.txt` 요청조차 TLS 핸드셰이크 단계에서 타임아웃됐다.
- `check_sources.py`(10초 타임아웃, 스펙 그대로 사용, 수정하지 않음)에서도 `연결실패: ReadTimeout`으로
  탈락.
- **판단**: RSS 자체는 유효하지만 서버가 너무 불안정해서 매일 자동 수집 파이프라인에 쓰기에는
  부적합하다고 판단, 이번 조사에서는 죽음(X)으로 남긴다. `sources.yaml`에 넣지 않았다. 재조사 시
  타임아웃을 20~30초로 늘려서 다시 시도해볼 가치는 있다.

### mvariety.com — robots.txt 전면 차단

- robots.txt에 `User-agent: * / Disallow: /` 가 명시되어 있어 (다수의 named AI 봇 차단 규칙 뒤에)
  **모든 크롤러에게 사이트 전체를 금지**하고 있다. RSS 자체는 postguam.com과 동일한 CMS
  패턴(`/search/?f=rss&...`)이라 살아있을 가능성이 높지만 robots 규칙상 시도조차 하지 않는다
  (전역 제약: robots.txt 준수).

### headlinejeju.co.kr — RSS는 살아있지만 robots.txt가 `/rss/` 명시적 차단

- `/rss/allArticle.xml` 은 HTTP 200, 정상 RSS 2.0 응답을 반환한다 (직접 확인함).
- 그러나 robots.txt에 `Disallow: /rss/` 가 명시되어 있다. 스펙 5절 규칙 4에 따라 죽은 게 아니어도
  robots 금지 경로는 소스로 쓸 수 없어 제외했다.

### theborneopost.com — 조사 중 차단 강화됨

- 1차 확인(홈페이지, RSS 링크 태그 스캔) 시점에는 홈페이지가 200으로 응답했지만 RSS `<link>` 태그는
  없었다.
- 이후 `/feed/` 등 흔한 경로를 두드리자 전부 403, 재시도 시 홈페이지 자체도 403으로 바뀌었다.
  robots.txt는 200으로 응답하지만 전통적 `Disallow` 대신 신형 "Content-Signal" 형식만 담고 있다.
- **판단**: 봇 차단(WAF)에 의한 죽음으로 본다.

### dailyexpress.com.my — Cloudflare 봇 차단

- robots.txt 요청 자체가 403과 함께 Cloudflare "Just a moment..." 챌린지 페이지를 반환한다.
  사이트 전체가 Cloudflare 봇 검증 뒤에 있어 이번 방식(단순 HTTP GET)으로는 어떤 경로도
  통과하지 못한다. 죽음으로 판정.

### kuam.com — RSS 없음 (SPA)

- 홈페이지가 174,621자에 달하는 React/SPA 셸이며 정적 HTML 어디에도 `feed`/`rss` 언급이 없다.
- `/rss`, `/feed`, `/feed/`, `/?feed=rss2`, `/arc/outboundfeeds/rss/` 등 흔한 경로를 모두
  두드렸지만 전부 동일한 앱 셸 HTML을 200으로 반환할 뿐 실제 RSS/JSON이 아니다(`lang="es"`인 것도
  이상해서 앱 셸 fallback으로 보임). Hawaii News Now와 달리 KUAM은 Arc Publishing 계열이 아닌
  것으로 보인다.

### vientianetimes.org.la — RSS 없음

- 홈페이지(42,979자)를 전부 훑어도 `feed`/`rss` 관련 언급이 전혀 없다. `/feed`, `/rss`, `/rss.xml`,
  `/feeds/all.rss`, `/arc/outboundfeeds/rss/`, `/rss/allArticle.xml`, `/rss/index.xml` 모두
  404. RSS 자체를 제공하지 않는 것으로 결론.

### vietnam_vnexpress — travel.rss를 선택한 이유

- `/rss/news.rss`, `/rss/travel.rss`, `/rss/tin-moi-nhat.rss` 세 개 모두 살아있는 것을 확인했다
  (전부 HTTP 200, `application/xml`, 유효 RSS). 와플트립은 여행 신문이므로 그중 여행 전용
  피드인 `travel.rss`를 선택했다. 나머지 두 개는 죽은 게 아니라 "선택 안 함"이며, 필요하면
  candidates.txt에 이미 검증된 URL로 있으니 재조사 없이 바로 추가할 수 있다.
- robots.txt는 `User-agent: * / Allow: /` 이며 GPTBot/ClaudeBot 등 특정 명명된 AI 크롤러만
  개별적으로 차단한다. 우리 UA(`WaffleTripBot/1.0`)는 그 명단에 없어 와일드카드 허용을 받는다.

## `sources.yaml`에 포함된 최종 소스 (7개)

| id | 지역 | 섹션 | 사유 |
|---|---|---|---|
| exchange_rate | all | data | 브리프 지정 기본 소스 (무료 공개 API, 인증키 불필요) |
| guam_pacific_island_times | guam | news | Step 4에서 확인, robots 허용 |
| hawaii_news_now | hawaii | news | Step 4에서 확인, robots 허용 |
| hawaii_beatofhawaii | hawaii | news | Step 4에서 확인, robots 허용 |
| vietnam_vnexpress | vietnam | news | Step 4에서 확인, robots 허용 |
| laos_laotiantimes | laos | news | Step 4에서 확인, robots 허용 |
| jeju_jejusori | jeju | news | Step 4에서 확인, robots 허용 |

`saipan`, `kota` 두 지역은 이번 조사에서 편입된 소스가 없다. `guam_post`는 보류.

## 후속 조치 제안 (이번 태스크 범위 밖, 기록만 남김)

- postguam.com: 1시간 이상 지난 뒤 `tools/check_sources.py`로 단독 재조사 → 성공하면 sources.yaml에 추가.
- saipantribune.com: 타임아웃을 20~30초로 늘려 재조사 가치 있음. 서버가 원래 이렇게 불안정한지,
  일시적 부하였는지 하루 이틀 뒤 다시 확인.
- saipan, kota 지역: 스펙 8절 밖의 대체 매체 발굴이 필요 (이번 태스크 범위 아님, 강제로 채우지 않음).
- mvariety.com: robots 전면 차단이라 RSS 대신 공식 API/파트너십 여부를 확인하지 않는 한 영구 제외.
