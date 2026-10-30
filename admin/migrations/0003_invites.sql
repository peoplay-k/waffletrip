-- 초대 링크(2026-10-30). 관리자가 계정을 만들 때 비밀번호를 정해 카톡으로 보내는 대신,
-- 한 번만 쓰는 링크를 준다. 링크를 연 본인이 비밀번호를 정한다. 토큰은 SHA-256 만 둔다.
CREATE TABLE IF NOT EXISTS invites (
  token_hash TEXT PRIMARY KEY,
  username   TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  created_by TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS invites_username ON invites (username);
