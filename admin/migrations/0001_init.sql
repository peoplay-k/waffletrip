-- 피플로드 편집실 D1 스키마.
-- 계정·세션·로그인 시도·변경 기록만 둔다. 기사·구조는 GitHub 저장소가 정본이다.

CREATE TABLE IF NOT EXISTS users (
  username   TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  role       TEXT NOT NULL CHECK (role IN ('admin', 'reporter')),
  -- 'pbkdf2-sha256$<반복 횟수>$<base64 해시>' — 반복 횟수를 같이 적어 나중에 올려도 옛 비밀번호가 맞는다
  pw_hash    TEXT NOT NULL,
  pw_salt    TEXT NOT NULL,
  disabled   INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);

-- 세션 토큰은 원문을 두지 않는다. 쿠키의 토큰을 SHA-256 한 값만 둔다 —
-- D1 이 새도 그 값으로는 로그인할 수 없게.
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  username   TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_username ON sessions (username);
CREATE INDEX IF NOT EXISTS sessions_expires ON sessions (expires_at);

-- 로그인 실패 횟수. key 는 'user:<아이디>' 또는 'ip:<주소>'.
-- 15분 안에 5번 틀리면 locked_until 까지 막는다.
CREATE TABLE IF NOT EXISTS login_attempts (
  key          TEXT PRIMARY KEY,
  failures     INTEGER NOT NULL DEFAULT 0,
  first_at     INTEGER NOT NULL,
  locked_until INTEGER NOT NULL DEFAULT 0
);

-- 변경 기록. 저장소 커밋이 정식 감사 기록이고, 이건 편집실 화면에서 보려고 둔다.
CREATE TABLE IF NOT EXISTS log (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       INTEGER NOT NULL,
  username TEXT NOT NULL,
  action   TEXT NOT NULL,
  target   TEXT NOT NULL DEFAULT '',
  detail   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS log_ts ON log (ts);

-- 기사 목록 캐시. 파일 내용(블롭) 해시가 같으면 앞머리도 같으므로 해시를 열쇠로 둔다 —
-- 저장소가 바뀌어도 바뀐 파일만 새로 읽는다.
CREATE TABLE IF NOT EXISTS blob_meta (
  oid  TEXT PRIMARY KEY,
  meta TEXT NOT NULL,
  seen INTEGER NOT NULL
);

-- 폴더(트리) 해시별로 완성된 목록. 아무것도 안 바뀌었으면 이것 하나로 끝난다.
CREATE TABLE IF NOT EXISTS list_cache (
  tree_oid   TEXT PRIMARY KEY,
  list       TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
