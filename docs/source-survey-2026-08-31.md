# 소스 실측 조사 — 2026-08-31

Task 1 Step 4 결과. 스펙 8절 후보 매체를 실제로 두드려본 기록이다. 스펙의 목록은 후보일 뿐이었고,
아래 표가 검증된 사실이다. 나중에 소스를 늘릴 때 이미 확인한 것을 다시 두드리지 않도록 죽은 것도
사유와 함께 전부 남긴다.

## 수정 이력

- **2026-08-31 (수정 라운드 1)**: 초판은 "스펙 8절 후보 14개를 전부 두드렸다"고 썼으나 사실이
  아니었다 — 스펙 §8.2-b(지역별 현지 매체) 표의 실제 후보는 22개였고 8개를 누락했다(guam 2,
  saipan 1, hawaii 1, vietnam 2, kota 1, jeju 1). 여기에 리뷰에서 추가 지시한 2개
  (Honolulu Star-Advertiser, 제주일보)와 스펙 §8.2(국내 여행 전문 매체) 8개를 더해 이번
  라운드에서 총 **18개 후보를 추가 조사**했다. 이 문서는 그 결과까지 반영한 전체 재작성본이다.
  최초 판정이 잘못 기록된 게 아니라 — 조사 범위 자체가 불완전했던 것이었다. 아래 표는 이제
  스펙 §8.2 8개 + §8.2-b 22개 + 리뷰 추가 2개 = **32개 후보 전체**를 담고 있다.

## 방법

1. 각 매체 홈페이지 HTML에서 `<link type="application/rss+xml">` 태그를 정규식으로 찾는다.
2. 태그가 없으면 `/rss`, `/feed`, `/feed/`, `/rss.xml`, `/feeds/all.rss`, `/?feed=rss2`,
   `/arc/outboundfeeds/rss/`(Arc Publishing/Gray Media 계열), `/rss/allArticle.xml`(국내 지역언론
   CMS 계열) 등 흔한 경로를 직접 두드렸다. 리다이렉트가 걸리면 최종 목적지까지 따라가 확인했다
   (예: hawaiitourismauthority.org → hta.hawaii.gov).
3. 찾은 URL을 `candidates.txt`에 `id<TAB>url` 형식으로 넣고 `tools/check_sources.py`로
   최종 판정했다 — 이 스크립트가 **robots.txt 확인 → 1초 지연 → 실제 응답 확인(RSS 파싱 후
   항목 수) → 1초 지연** 순서로 최종 판정을 내리는 유일한 근거다. 요청 간 지연(스펙 5절 규칙 4)은
   수정 라운드 1에서 추가했다 — 초판에는 없었고, `guam_post` 가 조사 중 레이트리밋(429)에 걸린
   것과 무관하지 않아 보인다. UA는 `WaffleTripBot/1.0 (+https://waffletrip.com/about/)`.
4. 이번 라운드에서 `check_sources.py`가 응답 디코딩 실패(예: 서버가 인코딩을 잘못 선언)로 배치
   전체가 죽는 버그를 발견해 함께 고쳤다 — `probe()`의 예외 처리 범위를 요청뿐 아니라 `r.text`
   디코딩까지 넓혔다. (`vietnam_vietnamnews` 조사 중 실제로 발생시켜 확인함, 아래 상세 노트 참고.)

## 최종 판정 표 — 스펙 §8.2-b 지역별 현지 매체 (22개 전부 + 리뷰 추가 2개 = 24개)

| id | 지역 | 매체명 | URL | 판정 | 사유 |
|---|---|---|---|---|---|
| guam_post | guam | The Guam Daily Post | `postguam.com/search/?f=rss&...` | 보류(X) | HTTP 429 — "postguam.com" 노트 참고 |
| guam_kuam | guam | KUAM News | `kuam.com/feed` | 죽음(X) | RSS/JSON 아님 — SPA, 흔한 경로 전부 앱쉘 HTML |
| guam_pacific_island_times | guam | Pacific Island Times | `pacificislandtimes.com/blog-feed.xml` | **사용가능(OK)** | RSS 항목 20개 |
| guam_pdn | guam | Pacific Daily News | `guampdn.com/search/?f=rss&...` | 죽음(X) | RSS 항목 0개 — "guam_pdn" 노트 참고 |
| guam_visitguam | guam | Guam Visitors Bureau | `visitguam.com/feed/` | 죽음(X) | HTTP 404, 흔한 경로 전부 실패 |
| saipan_variety | saipan | Marianas Variety | `mvariety.com/search/?f=rss&...` | robots 금지(X) | `User-agent: * / Disallow: /` — 전면 차단 |
| saipan_tribune | saipan | Saipan Tribune | `saipantribune.com/index.php/feed/` | **사용가능(OK), 단 불안정** | "saipan_tribune" 노트 참고 — 이번 실행은 RSS 항목 10개 |
| saipan_mva | saipan | Marianas Visitors Authority | `mymarianas.com/feed/` | 죽음(X) | TLS 프로토콜 불일치로 연결실패, 대안 확인해도 RSS 없음 |
| hawaii_news_now | hawaii | Hawaii News Now | `hawaiinewsnow.com/arc/outboundfeeds/rss/` | **사용가능(OK)** | RSS 항목 20개 |
| hawaii_beatofhawaii | hawaii | Beat of Hawaii | `beatofhawaii.com/feed/` | **사용가능(OK)** | RSS 항목 12개 |
| hawaii_hta | hawaii | Hawaii Tourism Authority | `hta.hawaii.gov/feed/` | **사용가능(OK)** | RSS 항목 10개 — 원 후보 도메인은 리다이렉트됨, "hawaii_hta" 노트 참고 |
| hawaii_staradvertiser (리뷰 추가) | hawaii | Honolulu Star-Advertiser | `staradvertiser.com/feed/` | **사용가능(OK)** | RSS 항목 40개 |
| vietnam_vnexpress | vietnam | VnExpress International (Travel) | `e.vnexpress.net/rss/travel.rss` | **사용가능(OK)** | RSS 항목 60개 |
| vietnam_vietnamnews | vietnam | Vietnam News | `vietnamnews.vn/rss/travel.rss` | 죽음(X) | 연결실패: UnicodeError — "vietnam_vietnamnews" 노트 참고 |
| vietnam_danangtoday | vietnam | Da Nang Today | `danangtoday.vn/feed/` | 죽음(X) | 연결실패: ConnectError — TLS 핸드셰이크 실패, 파킹 도메인 추정 |
| kota_borneopost | kota | The Borneo Post | `theborneopost.com/feed/` | 죽음(X) | HTTP 403 — 봇 차단(재요청 시 홈페이지도 403) |
| kota_dailyexpress | kota | Daily Express (Sabah) | `dailyexpress.com.my/feed/` | 죽음(X) | HTTP 403 — Cloudflare 봇 차단 |
| kota_nst | kota | New Straits Times | `nst.com.my/feed` | **사용가능(OK)** | RSS 항목 50개 — kota 지역 최초 확보 소스, "kota_nst" 노트 참고 |
| laos_vientianetimes | laos | Vientiane Times | `vientianetimes.org.la/feed` | 죽음(X) | HTTP 404 — 홈페이지 전체 검색해도 RSS 언급 없음 |
| laos_laotiantimes | laos | Laotian Times | `laotiantimes.com/feed/` | **사용가능(OK)** | RSS 항목 13개 |
| jeju_jejusori | jeju | 제주의소리 | `cdn.jejusori.net/rss/gn_rss_allArticle.xml` | **사용가능(OK)** | RSS 항목 50개 |
| jeju_headline | jeju | 헤드라인제주 | `headlinejeju.co.kr/rss/allArticle.xml` | robots 금지(X) | `Disallow: /rss/` — 피드는 정상 응답하지만 규칙 4에 따라 제외 |
| jeju_ijto | jeju | 제주관광공사 보도자료 | `ijto.or.kr/korean/Bd/list.php?btable=report_info` | 죽음(X) | RSS/JSON 아님 — 게시판형 HTML만 반환, RSS 경로 전부 404 |
| jeju_ilbo (리뷰 추가) | jeju | 제주일보 | `jejunews.com/rss/allArticle.xml` | **사용가능(OK)** | RSS 항목 50개 — 도메인은 jejunews.com (jejuilbo.com 은 여기로 리다이렉트) |

**사용 가능 11/24** (`guam_post` 보류 별도, `saipan_tribune`는 사용가능이지만 불안정 표시)

## 최종 판정 표 — 스펙 §8.2 국내 여행 전문 매체 (8개, region: auto)

리뷰에서 지시한 설계 변경(B). 현지 매체보다 여행 기사 비율이 높고, saipan·kota 처럼 현지 소스가
막힌 지역도 다룬다. 8개 전부 동일한 `/rss/allArticle.xml` 패턴(국내 지역언론에서 흔한 CMS 벤더
패턴)이었고, 8개 전부 살아있었다.

| id | 매체명 | URL | 판정 | 사유 |
|---|---|---|---|---|
| kr_traveltimes | 여행신문 | `traveltimes.co.kr/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_traveldaily | 트래블데일리 | `traveldaily.co.kr/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_tournews21 | 투어코리아 | `tournews21.com/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_travelnbike | 트래블바이크뉴스 | `travelnbike.com/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_ttlnews | TTL뉴스 | `ttlnews.com/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_ktsketch | 여행스케치 | `ktsketch.co.kr/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_travie | 트래비 | `travie.com/rss/allArticle.xml` | **OK** | RSS 항목 50개 |
| kr_tourtoctoc | 투어톡톡 | `tourtoctoc.com/rss/allArticle.xml` | **OK** | RSS 항목 50개 |

**사용 가능 8/8.** robots.txt는 8곳 모두 `Disallow: /admin/` 류의 관리자 경로만 금지하고
일반 크롤링은 허용이었다(`check_sources.py`가 개별 확인, 전부 "robots 허용"으로 통과).

## 지역별 커버리지 (최종)

| 지역 | enabled: true 소스 수 | 비고 |
|---|---|---|
| guam | 1 (+ 보류 1) | pacific_island_times. postguam은 429 보류, pdn/visitguam/kuam 죽음 |
| saipan | 1 (불안정 주의) | saipan_tribune만 생존 — 안정성 낮음, 아래 노트 참고. variety/mva 죽음 |
| hawaii | 4 | news_now, beatofhawaii, hta, staradvertiser |
| vietnam | 1 | vnexpress travel. vietnamnews/danangtoday 죽음 |
| kota | **1** (수정 전 0 → 이제 확보) | **kota_nst** — 리뷰가 지시한 핵심 수정 사항 |
| laos | 1 | laotiantimes. vientianetimes는 RSS 자체가 없음 |
| jeju | 2 | jejusori, jeju_ilbo(신규). headline은 robots 금지, ijto는 RSS 없음 |
| auto (국내 여행 전문 매체) | 8 | 8개 전부 생존, 기사별 지역 추론은 Task 2 |

이전 라운드의 최대 우려사항이었던 **saipan·kota 지역 소스 0개 문제는 이번 라운드에서 해소됐다**
(saipan은 saipan_tribune, kota는 kota_nst). 다만 saipan_tribune은 불안정하다는 캐비엇이 있고,
guam_post는 여전히 미해결 보류 상태다.

## 상세 노트

### postguam.com (guam_post) — 여전히 보류(429)

수정 라운드 1에서도 재확인했다. `tools/check_sources.py`를 2회 공식 실행(1차, 2차 모두 429)했고
그 사이 수동으로 8초 간격 3연속 재시도도 했지만 전부 `HTTP 429 Too Many Requests`. 응답 바디에
`client_ip`, `request_id`가 찍히는 것으로 봐서 TownNews/BLOX CMS의 레이트리밋이 우리 IP에 걸린
것으로 보인다. 약 40분에 걸쳐 시도했는데도 안 풀린 것으로 보아 단기(분 단위) 쿨다운이 아니라 더
긴 윈도(시간 단위 이상)일 가능성이 있다. **여전히 sources.yaml에 넣지 않았다** — 응답을 한 번도
받지 못했기 때문이다. `check_sources.py`에 요청 간 지연을 추가한 것(A-4)이 이 문제와 무관하지
않아 보인다 — 이번 조사 자체가 짧은 시간에 이 호스트를 반복 타격한 것이 레이트리밋을 촉발했을
가능성이 크다.

### guam_pdn — RSS는 정상이지만 현재 항목 0개

postguam.com과 동일한 TNCMS(TownNews) 플랫폼이고 RSS XML 구조 자체는 완전히 정상이다
(`<channel>`, `generator: TNCMS 1.94.3` 등 전부 정상). 하지만 `<channel>` 안에 `<item>`이
하나도 없다 — `#topstory` 키워드 태그에 현재 걸린 기사가 없다는 뜻이다. postguam.com은 같은
패턴의 URL로 20개 항목을 반환하는 것과 대조적이라, guampdn.com 쪽에서 "topstory" 태그를 다르게
쓰거나 아예 안 쓰는 편집 워크플로일 가능성이 있다. 구조적으로는 재사용 가능한 URL이니, 다른
태그(예: 그냥 전체 기사 검색)로 재조사해볼 가치는 있지만 이번 태스크 범위 밖으로 남긴다.

### saipan_tribune — 사용가능 판정이지만 신뢰하지 말 것

이번 조사 전체에서 이 URL(`https://www.saipantribune.com/index.php/feed/`)에 대해 관측한 것:
- 1라운드 공식 실행(`check_sources.py`, 10초 타임아웃): **실패** (ReadTimeout)
- 수동 curl(25초 타임아웃): **성공** (RSS 항목 10개)
- 수동 curl 3연속 재시도(20초 타임아웃): **전부 실패** (완전 무응답)
- 2라운드 공식 실행(`check_sources.py`, 10초 타임아웃, 동일 스크립트): **성공** (RSS 항목 10개)

6번 시도해서 성공 2번, 실패 4번 — 대략 1/3 성공률이다. "실제로 두드려서 응답하는 것만 넣는다"는
원칙에 따라 가장 최근 공식 실행이 성공했으므로 `sources.yaml`에 `enabled: true`로 넣었지만,
이 판정을 뒤집을 만큼 신뢰하지는 않는다 — 매일 자동 수집에서 이 소스만 실패하는 날이 잦을
것으로 예상한다. 수집기(Task 2+)가 이 소스의 실패를 정상 상황으로 다뤄야 한다.

### saipan_mva (Marianas Visitors Authority) — 이중으로 죽음

`httpx`로 연결 시 `SSL: TLSV1_ALERT_PROTOCOL_VERSION`으로 연결 자체가 거부된다(서버가 우리
클라이언트가 제시한 TLS 버전을 거부). macOS 기본 `curl`(LibreSSL)로는 연결되길래 그 경로로
`/feed/`, `/rss`, `/?feed=rss2` 등을 확인했지만 전부 홈페이지로 리다이렉트될 뿐 실제 RSS가
없다. WordPress 사이트(`wp-content`, `wp-json` 확인됨)인데 피드가 의도적으로 막혀 있는 것으로
보인다. 두 가지 독립적인 이유로 죽음 판정.

### hawaii_hta — 원 후보 도메인이 리다이렉트됨

스펙에 적힌 "Hawaii Tourism Authority" 후보 URL `hawaiitourismauthority.org`는 자체 RSS가
없고, 접속하면 실제 공식 도메인인 **`hta.hawaii.gov`**(.gov)로 301 리다이렉트된다. 그 도메인의
`/feed/`가 정상 RSS(10건)를 반환해서 `sources.yaml`에는 `hta.hawaii.gov/feed/`를 등록했다.

### kota_nst (New Straits Times) — kota 지역 최초 확보 소스

리뷰에서 이미 확인한 내용(HTTP 200, RSS 2.0, 50건, robots 전체허용)을 브리프 원칙에 따라
직접 재확인했다: `https://www.nst.com.my/feed` → HTTP 200, `application/rss+xml`, **RSS 항목
50개**. `check_sources.py` 공식 실행에서도 robots 통과 + OK로 확인. kota 지역이 스펙 8.2-b
후보만으로는 소스가 0개였던 문제를 해결하는 소스다.

### vietnam_vietnamnews — 응답 디코딩 버그 발견

`/rss` 경로 자체는 실제 RSS가 아니라 카테고리별 RSS 링크 색인 페이지였고, 거기서
`/rss/travel.rss`(여행 전용 피드)를 찾았다. 그런데 이 URL을 최초로 조사할 때
`tools/check_sources.py`가 `UnicodeError: UTF-16 stream does not start with BOM` 로 통째로
크래시했다 — 서버가 `Content-Type` 인코딩을 실제 응답과 다르게 선언한 것으로 보인다(BOM 없는데
UTF-16이라고 선언). 원래 `probe()`는 `httpx.get()` 호출만 `try/except`로 감싸고 `r.text` 접근은
감싸지 않아서, 이 후보 하나 때문에 나머지 대기 중이던 후보들이 전혀 조사되지 못하고 스크립트가
죽었다. `probe()`의 예외 처리 범위를 `r.text` 디코딩까지 넓혀 이 후보를 "연결실패: UnicodeError"
로 정상적으로 기록하고 나머지 후보 조사를 계속하도록 고쳤다(`tools/check_sources.py` 참고).
소스 자체는 서버 쪽 문제로 우리 스택(httpx)에서 못 읽으니 죽음으로 분류.

### vietnam_danangtoday — 파킹 도메인으로 추정

`curl -v`로 확인한 결과 TLS `ClientHello` 직후 `SSL_ERROR_SYSCALL`로 연결이 끊긴다. DNS가
`216.239.32.21`(구글 IP 대역)을 가리키고 있고 `http://`(비암호화)로는 404를 반환한다 — 정상
운영 중인 뉴스 사이트의 응답 패턴이 아니라 만료되어 파킹된 도메인일 가능성이 높다.

### mvariety.com — robots.txt 전면 차단 (1라운드와 동일)

robots.txt에 `User-agent: * / Disallow: /` 가 명시되어 있어 모든 크롤러에게 사이트 전체를
금지한다. RSS 자체는 postguam.com과 동일한 CMS 패턴이라 살아있을 가능성이 높지만 robots
규칙상 시도조차 하지 않는다.

### headlinejeju.co.kr — RSS는 살아있지만 robots.txt가 `/rss/` 명시 차단 (1라운드와 동일)

`/rss/allArticle.xml`은 HTTP 200, 정상 RSS 2.0 응답을 반환하지만 robots.txt에
`Disallow: /rss/`가 명시되어 있다. 스펙 5절 규칙 4에 따라 제외.

### jeju_ijto (제주관광공사 보도자료) — RSS 없음

공식 도메인은 `ijto.or.kr`(제주관광공사, Jeju Tourism Organization)로 확인했다. 보도자료는
`/korean/Bd/list.php?btable=report_info` 게시판형 페이지에 있고 RSS 태그도, 흔한 RSS 경로도
전부 없다(404 또는 홈페이지로 리다이렉트). 정부기관형 게시판 CMS라 RSS 미지원으로 판단.

### jeju_ilbo (제주일보) — 도메인 확인 필요했던 사례

검색으로 얻은 후보 도메인 두 개(`jejuilbo.com`, `jejunews.com`)를 직접 fetch해서 페이지
타이틀로 대조했다 — `jejuilbo.com`은 `jejunews.com`으로 리다이렉트되고, 최종 페이지 타이틀이
"제주일보"로 확인됨. 즉 **jejunews.com이 정본 도메인**이다. `/rss/allArticle.xml`이 정상 RSS
50건을 반환한다(jejusori.net과 동일한 국내 지역언론 CMS 패턴).

### theborneopost.com / dailyexpress.com.my — 봇 차단 (1라운드와 동일)

theborneopost.com은 홈페이지까지 포함해 반복 요청 시 403으로 전환됐다(WAF). dailyexpress.com.my는
robots.txt 요청 자체가 Cloudflare "Just a moment..." 챌린지 페이지로 막힌다. 둘 다 이번
라운드에서 재확인하지 않았다 — WAF/Cloudflare 차단은 요청 지연을 늘린다고 풀리는 성격이 아니고,
1라운드에서 이미 명확히 확인됐기 때문이다.

### kuam.com / vientianetimes.org.la — RSS 자체가 없음 (1라운드와 동일)

kuam.com은 React/SPA 앱 셸이라 정적 HTML 어디에도 RSS가 없다. vientianetimes.org.la는 홈페이지
전체(42,979자)를 뒤져도 feed/rss 언급이 전혀 없다. 둘 다 이번 라운드에서 재확인하지 않았다 —
"사이트에 RSS 기능 자체가 없다"는 결론은 지연을 늘린다고 바뀌지 않는다.

### vietnam_vnexpress — travel.rss를 선택한 이유 (1라운드와 동일)

`/rss/news.rss`, `/rss/travel.rss`, `/rss/tin-moi-nhat.rss` 세 개 모두 살아있는 것을 확인했다.
여행 신문이므로 여행 전용 피드인 `travel.rss`를 선택했다. 나머지 두 개는 죽은 게 아니라
"선택 안 함"이며 candidates.txt에 URL이 검증된 채로 남아 있어 재조사 없이 추가 가능하다.

## `sources.yaml`에 포함된 최종 소스 (20개: exchange_rate + 19개 뉴스)

| id | 지역 | 섹션 | 비고 |
|---|---|---|---|
| exchange_rate | all | data | 브리프 지정 기본 소스 |
| guam_pacific_island_times | guam | news | |
| saipan_tribune | saipan | news | 불안정 — 위 노트 참고 |
| hawaii_news_now | hawaii | news | |
| hawaii_beatofhawaii | hawaii | news | |
| hawaii_hta | hawaii | news | 실제 도메인 hta.hawaii.gov |
| hawaii_staradvertiser | hawaii | news | 리뷰 추가 |
| vietnam_vnexpress | vietnam | news | |
| kota_nst | kota | news | 리뷰 추가, kota 최초 확보 |
| laos_laotiantimes | laos | news | |
| jeju_jejusori | jeju | news | |
| jeju_ilbo | jeju | news | 리뷰 추가 |
| kr_traveltimes | auto | news | 국내 여행 전문 매체 |
| kr_traveldaily | auto | news | 국내 여행 전문 매체 |
| kr_tournews21 | auto | news | 국내 여행 전문 매체 |
| kr_travelnbike | auto | news | 국내 여행 전문 매체 |
| kr_ttlnews | auto | news | 국내 여행 전문 매체 |
| kr_ktsketch | auto | news | 국내 여행 전문 매체 |
| kr_travie | auto | news | 국내 여행 전문 매체 |
| kr_tourtoctoc | auto | news | 국내 여행 전문 매체 |

탈락·보류 후보 13개는 전부 `sources.yaml`에 `enabled: false` 항목 + 사유 주석으로 등록되어
있다(이 문서에 적힌 것과 동일한 사유). 조용히 뺀 것은 하나도 없다.

## 후속 조치 제안 (이번 태스크 범위 밖, 기록만 남김)

- postguam.com: 1시간 이상 지난 뒤 `tools/check_sources.py`로 단독 재조사 → 성공하면
  `enabled: true`로 전환.
- saipan_tribune: 안정성이 낮다. 수집기가 이 소스의 실패를 정상 상황으로 처리하는지 Task 2+
  에서 반드시 확인. 서버 상태가 개선되는지 며칠 뒤 재확인도 가치 있음.
- guam_pdn: `#topstory` 태그 대신 다른 검색 파라미터로 재조사하면 살릴 수 있을지도 모른다.
- ~~saipan, kota 지역: 스펙 8절 밖의 대체 매체 발굴이 필요~~ — **이 문장은 잘못된 전제였다.**
  스펙이 이미 8.2(국내 여행 전문 매체)로 이 문제를 해결하는 방향으로 수정되어 있었고, kota는
  8.2-b 안에서도 (New Straits Times) 이미 확보 가능했다. "스펙 밖"이 아니라 "스펙을 끝까지
  조사하지 않은 것"이 1라운드의 진짜 문제였다.
- mvariety.com: robots 전면 차단이라 RSS 대신 공식 API/파트너십 여부를 확인하지 않는 한 영구 제외.
- 국내 여행 전문 매체(auto) 8개의 지역 추론기(`src/region_tag.py`)는 Task 2 범위. 이번 태스크는
  값만 통과시켰다(`REGIONS`에 `"auto"` 추가).
