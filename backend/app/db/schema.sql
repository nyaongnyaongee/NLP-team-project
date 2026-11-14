-- 이음 시연용 DB 테이블 (PostgreSQL) — 7개

-- 사용자: 학부모 · 교사 · 민원대응팀
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('parent', 'teacher', 'complaint_team')),
  name          TEXT NOT NULL,              -- 성까지 (가명처리 어른 명단으로 씀)
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL
);

-- 학생: 담임 한 명의 반 (「반」 테이블은 시연에서 안 만듦 — teacher_id 가 곧 반). 가명처리 학생 명단도 여기서
CREATE TABLE students (
  id         BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT NOT NULL REFERENCES users(id),
  name       TEXT NOT NULL,                 -- 이름만 (성 없이, 가명처리 명단과 같게)
  parent_id  BIGINT REFERENCES users(id),   -- 학부모 (없으면 NULL — 대화를 시작할 수 없을 뿐)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (teacher_id, name)
);

-- 대화: 학부모 한 명 ↔ 담임 한 명. 신고(D)도 여기에
CREATE TABLE conversations (
  id           BIGSERIAL PRIMARY KEY,
  teacher_id   BIGINT NOT NULL REFERENCES users(id),
  parent_id    BIGINT NOT NULL REFERENCES users(id),
  student_name TEXT NOT NULL,
  student_id   BIGINT REFERENCES students(id),  -- 반 명단에 있는 학생이면. 없으면 NULL (예전 대화)
  status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),  -- closed → C 추출
  report       JSONB,                       -- 신고 보고서. NULL 이면 신고 안 함
  reported_at  TIMESTAMPTZ,                 -- 민원대응팀 화면 = 이 값이 있는 대화
  extract      JSONB,                       -- 할 일 · 일정 추출(C) 상태: {"status": "pending|done|failed", "error", "count", "at"}. NULL = 닫은 적 없음
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 메시지: 학부모 것은 정제, 교사 것은 그대로
CREATE TABLE messages (
  id              BIGSERIAL PRIMARY KEY,
  conversation_id BIGINT NOT NULL REFERENCES conversations(id),
  sender_id       BIGINT NOT NULL REFERENCES users(id),
  raw_text        TEXT NOT NULL,            -- 원문 (가명처리 전 그대로). 교사에게는 API · 화면으로 안 줌, 법적 확인 때 DB 에서만 본다
  refined_text    TEXT,                     -- 정제문 (교사 메시지 · 원문 통과는 NULL)
  needs_refinement BOOLEAN,                 -- 정제 여부: true = 정제함(교사는 정제문), false = 원문 통과(교사는 원문),
                                            -- NULL = 처리 전 · 실패 · 교사 메시지. 교사에게는 이 값을 주지 않는다
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
  due_text        TEXT,                     -- 대화에 적힌 표현 그대로 (예: '이번 주 금요일까지')
  due_at          TIMESTAMPTZ,              -- 그 표현을 메시지 보낸 날 기준으로 바꾼 날짜 (Claude 가 계산, 코드가 범위 점검).
                                            -- 시각이 없으면 그날 00:00 (한국 시각)
  status          TEXT NOT NULL DEFAULT 'candidate'
                  CHECK (status IN ('candidate', 'added', 'done')),  -- 후보 → [추가] → 완료. 후보를 지우면 행 삭제
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 공지: 교사가 쓰고(draft) [보내기] 하면 sent. 받는 사람 = 반 학생(students)의 학부모 전원 + 그 교사와 대화가 있는 학부모
-- 보낸 공지도 고치거나 지울 수 있다 (updated_at > sent_at 이면 「수정됨」). 다시 보내기만 안 됨
CREATE TABLE notices (
  id         BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT NOT NULL REFERENCES users(id),
  title      TEXT NOT NULL,
  body       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'sent')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at    TIMESTAMPTZ
);

-- 학생 메모장: 학생 한 명에 메모장 하나 (담임이 자유롭게 적는 글 한 덩어리). 학부모 · 민원대응팀 · Claude 에게는 주지 않는다
CREATE TABLE student_memos (
  student_id BIGINT NOT NULL REFERENCES students(id),
  teacher_id BIGINT NOT NULL REFERENCES users(id),  -- 쓴 교사 (이 사람만 본다)
  body       TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (student_id, teacher_id)
);

-- messages.analysis 예시 (확정 아님, 프롬프트에 따라 바뀜)
-- {"abusive": true, "abuse_types": ["욕설", "협박"], "topic": "짝 바꾸기",
--  "requests": ["짝을 바꿔 달라"], "deadline": "오늘까지", "quotes": ["몇번을 말해야 알아들어요?"]}
