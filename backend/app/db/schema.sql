-- 이음 시연용 DB 테이블 (PostgreSQL) — 7개

-- 사용자: 학부모 · 교사 · 민원대응팀
CREATE TABLE users (
  id            BIGSERIAL PRIMARY KEY,
  role          TEXT NOT NULL CHECK (role IN ('parent', 'teacher', 'complaint_team')),
  name          TEXT NOT NULL,              -- 성까지 (가명처리 어른 명단으로 씀)
  login_id      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  invite_code   TEXT UNIQUE                 -- 교사의 반 초대 코드 (학부모가 이 코드로 자녀를 반에 잇는다). 교사만
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
  teacher_deleted_at TIMESTAMPTZ,           -- 교사가 목록에서 지운 시각 (종료된 대화만). 행 · 메시지는 DB 에 남김. 종료된 대화에는 글을 못 보내므로 다시 나타나지 않음
  parent_deleted_at  TIMESTAMPTZ,
  teacher_read_id    BIGINT,                -- 담임이 마지막으로 읽은 메시지 번호 (안 읽은 수 = 상대 글 중 이보다 큰 것). NULL = 안 읽음
  parent_read_id     BIGINT,                -- 학부모 쪽, 위와 같음           -- 학부모가 목록에서 지운 시각. 위와 같음 (교사 목록 · 보고서에는 그대로)
  extract      JSONB,                       -- 할 일 · 일정 추출(C) 상태: {"status": "pending|done|failed", "error", "count", "at"}. NULL = 닫은 적 없음
  closed_at    TIMESTAMPTZ,                 -- 대화를 닫은 시각 (종료 순 정렬). 열린 대화 · 이 열이 생기기 전에 닫은 대화는 NULL
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
  conversation_id BIGINT REFERENCES conversations(id),  -- NULL = 교사가 직접 등록한 반 전체 일정
  teacher_id      BIGINT REFERENCES users(id),           -- 직접 등록한 일정의 담임 (대화에서 뽑은 것은 NULL → 대화의 담임)
  kind            TEXT NOT NULL CHECK (kind IN ('todo', 'event')),
  shared          BOOLEAN NOT NULL DEFAULT true,         -- 일정을 학부모 캘린더에 보일지 (추가 · 완료한 것만 보임).
                                                         -- 대화의 일정 → 그 학부모, 반 전체 일정 → 공지 받는 학부모 전원
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

-- 공지 댓글: 보낸 공지에 교사 · 받는 학부모가 단다 (정제하지 않음)
CREATE TABLE notice_comments (
  id         BIGSERIAL PRIMARY KEY,
  notice_id  BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,  -- 공지를 지우면 댓글도
  author_id  BIGINT NOT NULL REFERENCES users(id),
  body       TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 자주 묻는 질문(Q&A): 교사가 등록하면 바로 반 학부모(공지와 같은 받는 사람)에게 보인다. 학생 · 학부모 이름은 넣지 않는다
CREATE TABLE faqs (
  id         BIGSERIAL PRIMARY KEY,
  teacher_id BIGINT NOT NULL REFERENCES users(id),
  question   TEXT NOT NULL,
  answer     TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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
