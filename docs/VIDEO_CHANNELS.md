# 영상 채널 — 와플트립 유튜브·틱톡·네이버 클립

2026-10-19 사장님: "영상도 다 되고 지금 그거 와플트립 유튜브나 클립, 틱톡에 다 올리자."

매일 발행 실행이 영상 두 종을 굽는다. 영상은 빌드 서버에서 만들어져 사이트에 공개로 올라간다
(저장소에는 넣지 않는다).

| 영상 | 주소 | 형태 |
|---|---|---|
| 지역 쇼츠(나레이션) | `https://waffletrip.com/video/<stem>.mp4` — stem 은 `data/shorts_latest.json` | 세로 9:16, 30~60초 |
| 주간 롱폼(나레이션) | `https://waffletrip.com/video/peopleroad-week.mp4` | 가로, 1~2분 |

인스타 @waffletrip06 은 이미 자동 발행 중이다(`tools/publish_instagram.py`).

## 유튜브 @waffletrip — 자동 발행 준비 끝, 시크릿 3개만 넣으면 돈다

`tools/publish_youtube.py` 가 매일 발행의 publish 잡에서 돈다.

- 그날 쇼츠 → 유튜브 쇼츠(제목 끝 `#Shorts`). 같은 편은 두 번 안 올린다(`data/youtube_posted.json`)
- 주간 롱폼 → 일반 영상, **7일에 한 번만**. 목소리 없는 판은 올리지 않는다
- **토큰의 채널 핸들이 `@waffletrip` 이 아니면 아무것도 올리지 않는다**(브랜드 격리)
- 업로드 중 끊기면 "결과 불명"으로 적고 다시 올리지 않는다(중복 방지)

사장님이 하실 일(한 번):

1. Google Cloud 콘솔 → 프로젝트 → **YouTube Data API v3** 사용 설정
2. OAuth 동의 화면(외부, 게시 상태로) → OAuth 클라이언트 ID(데스크톱 앱) 만들기
3. **@waffletrip 채널을 가진 구글 계정으로** 로그인해 refresh token 받기
   (범위 `https://www.googleapis.com/auth/youtube.upload` 와 `youtube.readonly`)
4. GitHub `peoplay-k/waffletrip` → Settings → Secrets and variables → Actions 에 세 개:
   `WAFFLETRIP_YT_CLIENT_ID`, `WAFFLETRIP_YT_CLIENT_SECRET`, `WAFFLETRIP_YT_REFRESH_TOKEN`
5. 끝. 다음 매일 발행부터 올라간다. 값은 채팅·저장소에 붙여넣지 않는다

과미(@guami_travel)용 시크릿 `GWAMI_YT_*` 은 Kim 저장소에 있고 다른 채널이다. 섞어 쓰면 핸들 확인에서 막힌다.

## 틱톡 @waffletrip — 계정 연결이 필요하다

Claude 에 연결된 틱톡 계정(2026-10-19 확인): foodkingstar, guami-travel, travelstyling, gemfman2, tiktok.
**@waffletrip 으로 확인되는 계정이 없다.** 다른 브랜드 계정에 올리면 안 되므로 올리지 않았다.

- 사장님이 Claude 대화에서 "틱톡 와플트립 계정 연결해줘"라고 하면 연결 화면이 뜬다(Higgsfield 커넥터)
- 연결되면 사이트의 공개 영상 주소를 가져와 발행 양식을 띄운다. **틱톡 정책상 마지막 '게시'는
  사장님이 Claude 앱의 양식에서 직접 누른다**(공개 범위·AI 생성 표시 선택)
- 위 목록의 `tiktok` 이라는 이름의 계정이 와플트립이라면 그렇다고만 알려주면 된다

## 네이버 클립 — 업로드 API 가 없다

네이버는 클립 업로드용 공개 API 를 열어 두지 않았다. 사람이 앱에서 올린다.

1. 휴대폰에서 `https://waffletrip.com/video/<stem>.mp4` 를 열어 저장
   (stem 은 `data/shorts_latest.json`, 예: `peopleroad-guam-20261016-voiced`)
2. 네이버 앱 → 클립 → 만들기 → 저장한 영상 선택
3. 설명은 `data/shorts_latest.json` 의 `caption` 을 그대로 붙인다
