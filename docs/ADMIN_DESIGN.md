# 편집실(관리자 화면) 설계 — 2026-10-30

사장님(2026-10-30): "어드민을 완전 새롭게 만들어서 카테고리 등도 내가 실제로 바꾸고 이렇게 해야지.
지금 너가 임의로 하는건 안 돼. 처음엔 그렇게 하더라도 계속 내가 수정해서 바꾸고 해야 해. 제대로 해야지."

정한 것(같은 날 사장님 답):
- 로그인: **아이디·비밀번호**
- 고칠 수 있는 것: **카테고리·지역·메뉴 / 기사 쓰기·고치기·내리기 / 기자·서명 / 홈 화면 배치**
- 쓰는 사람: **사장님(관리자) + 기자들(권한 나눔)**

## 1. 큰 그림

```
 브라우저 ──(아이디·비밀번호, 쿠키)──> 편집실 서버 (Cloudflare Worker + D1)
                                         │  계정·세션·변경 기록은 D1
                                         │  기사·구조는 GitHub 저장소에 커밋 (서버만 아는 토큰)
                                         v
                              peoplay-k/waffletrip (main)
                                         │  content/review/*.md, config/site.json 이 바뀌면
                                         v
                              daily.yml(매일 발행) → waffletrip.com
```

- 사이트는 지금처럼 GitHub Pages 정적 사이트다. 편집실은 별도 서버(Cloudflare Worker)에서 돈다 —
  화면(HTML/JS)과 API 를 같은 주소에서 낸다(쿠키를 같은 출처로 쓰려고).
- GitHub 토큰은 **서버 비밀값**으로만 있다. 브라우저·기자는 토큰을 보지 않는다.
- 바뀐 것은 전부 저장소 커밋으로 남는다(누가·언제·무엇을). 되돌리기도 커밋으로 한다.

## 2. 사이트 구조 파일 `config/site.json`

정본. 파이프라인(src/site_config.py)이 읽어 지면을 만든다. 편집실이 고친다.

| 키 | 뜻 |
|---|---|
| `channels.travel`, `channels.ent` | `{name, desc}` 채널 이름(여행 / 문화)과 채널 첫 쪽 소개 글. desc 를 비우면 지역·부문 목록으로 자동. id 와 주소(/travel/, /ent/)는 바꾸지 않는다 |
| `travel_sections[]` | 여행 부문 `{id, name, desc, visible}`. 순서 = 메뉴 순서. 기본 넷(news·biz·feature·data)은 자동 분류 규칙이 있다. 새로 만든 부문은 기사에서 직접 고른 것만 들어간다 |
| `culture_sections[]` | 문화 부문 `{id, name, desc, visible}`. 순서 = 메뉴 순서. 주소 /ent/<id>/ |
| `culture_rules[]` | `{section, keywords[]}` 순서대로. 부문이 비어 온 문화 기사를 제목으로 가른다. 먼저 걸리는 줄이 이긴다 |
| `culture_aliases` | 옛 부문 id → 새 id (옛 주소를 넘기는 데도 쓴다) |
| `regions[]` | 지역면 `{id, name, keywords[], desk_duty, visible, currency?, weather?{city,lat,lon}, require_travel_word?, destination?}`. 순서 = 지역 목록 순서. keywords 는 수집한 기사 제목에서 지역을 고르는 말 |
| `korea_travel_words[]` | `require_travel_word` 인 지역(국내)은 제목에 이 말 중 하나가 있어야 잡힌다 |
| `reporters[]` | `{name, beats[]}`. beats 는 지역 id·`ent`·`data`. 서명에 그대로 나간다 — **실제 직원만** |
| `general_reporter` | 담당이 없는 지면의 기본 기자 |
| `home` | 홈 배치: `hero_count`(넘기는 큰 기사 수), `travel_block_size`, `culture_grid`, `culture_block_size`, `latest_count`, `photo_row`, `show_data_strip`, `show_photo_row`, `show_video`, `order`(["travel","culture","culture_sections","latest"] 의 순서), `pinned_lead`(머리기사로 고정할 기사 id, 빈 값이면 자동) |

id 규칙: 영문 소문자·숫자·하이픈, 2~24자. 한 번 만든 id 는 바꾸지 않는다(주소가 깨진다) —
이름만 바꾼다. 지우면 그 부문 기사는 기본 부문으로 간다(여행: 뉴스, 문화: 스타의 여행).
지역을 지우면 그 지역 기사·주소가 사라지므로 편집실은 **숨기기(visible:false)** 만 준다.

## 3. 기사 원고 `content/review/*.md`

YAML 앞머리 + 본문. 편집실이 쓰는 칸:

| 칸 | 값 |
|---|---|
| `title` | 제목 |
| `channel` | `travel` / `ent` |
| `region` | 여행 기사의 지역 id |
| `category` | 문화 기사의 부문 id |
| `topic` | (선택) 여행 기사의 부문을 직접 고를 때. 비우면 자동 |
| `section` | news / flight / data / promo (기존) |
| `summary` | 요약 |
| `source_name` | 필자(기자 이름). 비우면 지면 담당 기자 |
| `kind` | 취재 / 기획 / 인터뷰 / 해설 / 보도자료 |
| `source_url` | 원문 링크(선택) |
| `photo`, `photo_hero` | 대표 사진 |
| `status` | 아래 |
| `author` | 편집실에서 만든 사람의 아이디(기록용) |
| `id`, `published_id`, `published_on`, `sources`, `reason`, `duplicate_of`, `photo_note` | 파이프라인 칸 — **편집실은 그대로 둔다** |

`status`:

| 값 | 뜻 | 누가 |
|---|---|---|
| `draft` | 작성중. 지면에 안 나감 | 누구나 |
| `review` | 검토요청. 기자가 다 썼다 — 관리자가 보고 발행대기로 | 기자 |
| `approved` | 발행대기. 다음 발행(저장 커밋이 깨운다)에 나감 | 관리자 |
| `published` | 발행됨. 고치면 다음 발행에 지면도 바뀜(src/sync_edits.py) | 파이프라인이 붙임 |
| `hidden` | 내림. 지면·목록·검색·RSS·사이트맵에서 빠진다. 다시 `published` 로 돌리면 돌아온다 | 관리자 |

## 4. 권한

| | 관리자(admin) | 기자(reporter) |
|---|---|---|
| 기사 보기 | 전부 | 전부 |
| 새 기사 | O | O (draft/review 로만 저장) |
| 기사 고치기 | 전부 | 자기가 만든 것(author) 중 draft/review 인 것 |
| 발행대기·내리기·다시 올리기 | O | X |
| 구조(카테고리·지역·기자·홈) | O | X |
| 계정 관리 | O | X (자기 비밀번호 바꾸기만) |

## 5. 편집실 서버 API (같은 출처, JSON)

모든 쓰기 요청은 헤더 `X-Requested-With: peopleroad` 가 있어야 한다(CSRF). 쿠키는
`HttpOnly; Secure; SameSite=Strict`. 세션 30일.

| 메서드·경로 | 권한 | 하는 일 |
|---|---|---|
| `POST /api/login` `{username,password}` | - | 로그인. 5회 틀리면 15분 잠금 |
| `POST /api/logout` | 로그인 | |
| `GET /api/me` | 로그인 | `{username, name, role}` |
| `POST /api/me/password` `{current,next}` | 로그인 | 비밀번호 바꾸기 |
| `GET /api/setup` / `POST /api/setup` `{code,username,name,password}` | - | 계정이 하나도 없을 때만. 설치 코드(ADMIN_SETUP_CODE)가 맞으면 첫 관리자 |
| `GET /api/articles` | 로그인 | 원고 목록 `[{path,title,status,channel,region,category,published_on,author,source_name}]` |
| `GET /api/articles/:name` | 로그인 | `{front, body, sha}` |
| `PUT /api/articles/:name` `{front, body, sha}` | 권한표 | 저장(커밋). sha 가 다르면 409(그새 바뀜) |
| `POST /api/articles` `{front, body}` | 로그인 | 새 원고. 파일명 `YYYYMMDD_<slug>.md` |
| `POST /api/upload` (이미지) | 로그인 | content/uploads/ 에 올림 → 사진 반입이 검사 |
| `GET /api/site` | 로그인 | `{config, sha}` |
| `PUT /api/site` `{config, sha}` | 관리자 | 검증 후 저장(커밋) |
| `GET /api/users` / `POST` / `PUT /:username` / `DELETE /:username` | 관리자 | 계정 |
| `GET /api/log` | 관리자 | 최근 변경 기록 |
| `GET /api/deploys` | 로그인 | 최근 발행 상태(GitHub Actions) |

커밋 메시지: `편집실(<아이디>): <무엇을>` — 저장소 이력이 곧 감사 기록이다.

## 6. 배포

- `admin/` 폴더: `wrangler.toml`, `src/`(Worker), `public/`(화면), `migrations/`(D1).
- `.github/workflows/admin.yml`: `admin/**` 가 바뀌면 배포(wrangler deploy, D1 migrations apply,
  비밀값 넣기).
- 사장님이 한 번 만들어 주실 것(저장소 Settings → Secrets 에 넣는다. 채팅에 붙이지 않는다):
  `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `ADMIN_GITHUB_TOKEN`(Contents·Actions 읽기·쓰기),
  `ADMIN_SETUP_CODE`(첫 관리자 만들 때 쓰는 아무 문구).
- waffletrip.com/admin/ 은 편집실 주소로 넘긴다.
