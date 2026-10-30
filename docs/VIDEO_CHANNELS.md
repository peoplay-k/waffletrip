# 영상 채널 — 와플트립 유튜브·틱톡·네이버 클립

2026-10-19 사장님: "영상도 다 되고 지금 그거 와플트립 유튜브나 클립, 틱톡에 다 올리자."

매일 발행 실행이 영상 두 종을 굽는다. 영상은 빌드 서버에서 만들어져 사이트에 공개로 올라간다
(저장소에는 넣지 않는다).

| 영상 | 주소 | 형태 |
|---|---|---|
| 지역 쇼츠(나레이션) | `https://waffletrip.com/video/<stem>.mp4` — stem 은 `data/shorts_latest.json` | 세로 9:16, 30~60초 |
| 주간 롱폼(나레이션) | `https://waffletrip.com/video/peopleroad-week.mp4` | 가로, 1~2분 |

인스타 @waffletrip06 은 이미 자동 발행 중이다(`tools/publish_instagram.py`).

## 유튜브 — 두 채널로 나눈다(2026-10-30 사장님 '둘 다 나눠서')

| 채널 | 무엇 | 시크릿 | 상태 |
|---|---|---|---|
| @peopleroad (UCkhVoG8C8OtKX60WpCpP99A) | 여행 쇼츠(하루걸러) + 주간 롱폼(7일에 1번) | `WAFFLETRIP_YT_CLIENT_ID` · `_CLIENT_SECRET` · `_REFRESH_TOKEN` (10/28 등록) | 돌고 있음 |
| @waffletrip (UCixhDwh_YbJqyB6SYiadRAA) | 연예 '오늘의 방송' 롱폼 + 숏폼 — 하루 2편(`WAFFLETRIP_ENT_YT_MAX`) | `WAFFLETRIP_ENT_YT_REFRESH_TOKEN` (클라이언트는 위와 같은 앱) | **사장님 두 가지 하면 돈다** |

- 발행기 `tools/publish_youtube.py`. 채널 ID·핸들이 맞지 않으면 그 채널엔 아무것도 안 올린다(브랜드 격리).
  여행 채널엔 연예 영상이 가지 않고, 연예 채널엔 그날(`video/peopleroad-tv-YYYYMMDD.json` 의 date 가 오늘)만, 롱폼 먼저.
- 중복: `data/youtube_posted.json`(연예는 `channel: ent`) + 연예 채널 최근 업로드 제목 대조(못 읽으면 안 올림).
- ★ OAuth 앱이 과미 유튜브(Kim 저장소 `GWAMI_YT_*`, 같은 클라이언트)와 같아 **하루 업로드 할당량 10,000(업로드 1편 ≈1,600)을 같이 쓴다.**
  그래서 연예는 하루 2편으로 두고, quotaExceeded 가 나면 그날 멈춘다. 늘리려면 GCP 프로젝트를 따로 만들어 `WAFFLETRIP_ENT_YT_CLIENT_ID/SECRET` 을 넣는다.

### 사장님이 하실 일 (연예 채널 켜기)
1. 인텔 맥 터미널에서 — 브라우저가 열리면 **@waffletrip 채널을 가진 구글 계정**으로 로그인, 채널 고르는 화면이 나오면 **waffletrip** 을 골라 허용:
   ```
   cd ~/Desktop/여행신문 && python3 tools/youtube_auth.py --target ent
   ```
   @waffletrip 이 아니면 등록하지 않고 멈춘다. @peopleroad 시크릿은 건드리지 않는다.
2. GitHub 웹에서 `.github/workflows/daily.yml` 의 '유튜브' 단계 `env:` 에 한 줄을 더한다(Claude 토큰은 워크플로 파일을 못 고친다).
   `WAFFLETRIP_YT_REFRESH_TOKEN: ...` 줄 바로 아래:
   ```yaml
             WAFFLETRIP_ENT_YT_REFRESH_TOKEN: ${{ secrets.WAFFLETRIP_ENT_YT_REFRESH_TOKEN }}
   ```
   두 가지가 끝나면 다음 매일 발행부터 연예 영상이 @waffletrip 에 올라간다. 하나라도 빠지면 연예는 조용히 건너뛴다(여행은 그대로).

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
