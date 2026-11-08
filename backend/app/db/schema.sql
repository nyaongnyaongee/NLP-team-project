-- 이음 시연용 DB 테이블 (PostgreSQL) — 4개

-- 사용자: 학부모 · 교사 · 민원대응팀
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('parent', 'teacher', 'complaint_team')),
  name          TEXT NOT NULL,              -- 성까지 (가명처리 어른 명단으로 씀)
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL
);

-- 대화: 학부모 한 명 ↔ 담임 한 명. 신고(D)도 여기에
CREATE TABLE conversations (
  id           BIGSERIAL PRIMARY KEY,
  teacher_id   BIGINT NOT NULL REFERENCES users(id),
  parent_id    BIGINT NOT NULL REFERENCES users(id),
  student_name TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),  -- closed → C 추출
  report       JSONB,                       -- 신고 보고서. NULL 이면 신고 안 함
  reported_at  TIMESTAMPTZ,                 -- 민원대응팀 화면 = 이 값이 있는 대화
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 메시지: 학부모 것은 정제, 교사 것은 그대로
CREATE TABLE messages (
  id              BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id),
  sender_id       BIGINT NOT NULL REFERENCES users(id),
  raw_text        TEXT NOT NULL,            -- 원문 (가명처리 전 그대로). 교사에게는 API · 화면으로 안 줌, 법적 확인 때 DB 에서만 본다
  refined_text    TEXT,                     -- 정제문 (교사 메시지는 NULL)
  analysis        JSONB,                    -- Claude 분석 결과. 필드가 바뀌어도 테이블은 안 고침
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'done', 'failed', 'skip')),  -- skip = 교사 메시지
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 할 일 · 일정 (C)
CREATE TABLE tasks (
  id              BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id),
  kind            TEXT NOT NULL CHECK (kind IN ('todo', 'event')),
  title           TEXT NOT NULL,
  due_text        TEXT,                     -- 원문 표현 그대로 (예: '이번 주 금요일까지')
  due_at          TIMESTAMPTZ,              -- 코드가 받은 날 기준으로 바꾼 날짜
  status          TEXT NOT NULL DEFAULT 'candidate'
                  CHECK (status IN ('candidate', 'added', 'done'))  -- 후보 → [추가] → 완료
);

-- messages.analysis 예시 (확정 아님, 프롬프트에 따라 바뀜)
-- {"abusive": true, "abuse_types": ["욕설", "협박"], "topic": "짝 바꾸기",
--  "requests": ["짝을 바꿔 달라"], "deadline": "오늘까지", "quotes": ["몇번을 말해야 알아들어요?"]}
