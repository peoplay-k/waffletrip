-- 발행 상태 화면의 '기사 보기'.
-- 저장이 만든 커밋 해시를 기록에 남기고, 실행(run)마다 알아낸 기사 주소를 둔다.
ALTER TABLE log ADD COLUMN commit_sha TEXT NOT NULL DEFAULT '';
CREATE INDEX IF NOT EXISTS log_commit ON log (commit_sha);

CREATE TABLE IF NOT EXISTS run_links (
  run_id     INTEGER PRIMARY KEY,
  url        TEXT NOT NULL,   -- 빈 값이면 '기사가 지면에 없다'고 확인한 것(작성중·내림 등)
  title      TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
