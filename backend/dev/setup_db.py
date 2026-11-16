"""DB 준비: eum 이 없으면 만들고, 테이블이 없으면 schema.sql 로 만든다.
psql · PATH 설정 없이 파이썬만으로 되고, Mac · Windows 가 같다.
dev.py 가 알아서 부르며, 이미 만들어져 있으면 아무것도 안 한다.
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app.core.config import settings  # noqa: E402

SCHEMA = BACKEND / "app" / "db" / "schema.sql"


def main():
    url = make_url(settings.database_url)
    dbname = url.database
    try:
        admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
        with admin.connect() as c:
            if not c.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}).scalar():
                c.execute(text(f'CREATE DATABASE "{dbname}"'))
                print(f"DB '{dbname}' 만듦")
        eng = create_engine(url)
        with eng.connect() as c:
            has_tables = c.execute(text("SELECT to_regclass('public.users')")).scalar()
    except OperationalError as e:
        first = str(e.orig).strip().splitlines()[0] if e.orig else str(e)
        sys.exit(
            "PostgreSQL 에 접속하지 못했습니다.\n"
            f"  사유: {first}\n"
            "  .env 의 DATABASE_URL (사용자 · 비밀번호 · 포트) 을 확인하세요.\n"
            "  비밀번호에 @ : / # 같은 기호가 있으면 %40 처럼 바꿔 써야 합니다."
        )
    if not has_tables:
        raw = eng.raw_connection()
        raw.cursor().execute(SCHEMA.read_text(encoding="utf-8"))
        raw.commit()
        raw.close()
        print("테이블 만듦 (users · students · conversations · messages · tasks · notices · notice_comments · student_memos)")
    else:
        _upgrade(eng)


# schema.sql 이 바뀐 뒤에도 예전에 만든 DB 를 지우지 않고 쓰게, 빠진 열만 더한다 (여러 번 돌려도 같음)
UPGRADES = [
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS extract JSONB",                         # C 추출 상태
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE messages ADD COLUMN IF NOT EXISTS needs_refinement BOOLEAN",                   # 정제 여부 (원문 통과)
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS teacher_deleted_at TIMESTAMPTZ",        # 교사 목록에서 지움 (DB 엔 남김)
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS parent_deleted_at TIMESTAMPTZ",         # 학부모 목록에서 지움 (DB 엔 남김)
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS teacher_id BIGINT REFERENCES users(id)",        # 직접 등록한 일정
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS shared BOOLEAN NOT NULL DEFAULT true",          # 학부모 캘린더에 공유
    "ALTER TABLE tasks ALTER COLUMN conversation_id DROP NOT NULL",                             # 반 전체 일정은 대화 없음
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS teacher_read_id BIGINT",                # 안 읽은 메시지 수
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS parent_read_id BIGINT",
    # 공지 테이블 (schema.sql 의 것과 같게)
    """CREATE TABLE IF NOT EXISTS notices (
      id         BIGSERIAL PRIMARY KEY,
      teacher_id BIGINT NOT NULL REFERENCES users(id),
      title      TEXT NOT NULL,
      body       TEXT NOT NULL,
      status     TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'sent')),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      sent_at    TIMESTAMPTZ
    )""",
    # 공지 댓글 (schema.sql 의 것과 같게)
    """CREATE TABLE IF NOT EXISTS notice_comments (
      id         BIGSERIAL PRIMARY KEY,
      notice_id  BIGINT NOT NULL REFERENCES notices(id) ON DELETE CASCADE,  -- 공지를 지우면 댓글도
      author_id  BIGINT NOT NULL REFERENCES users(id),
      body       TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    # 학생 · 학생 메모 (schema.sql 의 것과 같게)
    """CREATE TABLE IF NOT EXISTS students (
      id         BIGSERIAL PRIMARY KEY,
      teacher_id BIGINT NOT NULL REFERENCES users(id),
      name       TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (teacher_id, name)
    )""",
    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS student_id BIGINT REFERENCES students(id)",
    "ALTER TABLE students ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES users(id)",  # 학생 ↔ 학부모 (대화 시작)
    # 학생 메모장 (PR #15 의 student_notes = 메모 여러 개 → 학생마다 메모장 하나). 예전 메모는 오래된 것부터 이어 붙여 옮긴다
    """CREATE TABLE IF NOT EXISTS student_memos (
      student_id BIGINT NOT NULL REFERENCES students(id),
      teacher_id BIGINT NOT NULL REFERENCES users(id),
      body       TEXT NOT NULL DEFAULT '',
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (student_id, teacher_id)
    )""",
    """DO $$ BEGIN
      IF to_regclass('public.student_notes') IS NOT NULL THEN
        INSERT INTO student_memos (student_id, teacher_id, body, updated_at)
          SELECT student_id, teacher_id, string_agg(body, E'\n' ORDER BY created_at, id), max(updated_at)
          FROM student_notes GROUP BY student_id, teacher_id
          ON CONFLICT DO NOTHING;
        DROP TABLE student_notes;
      END IF;
    END $$""",
]


def _upgrade(eng):
    with eng.begin() as c:
        for sql in UPGRADES:
            c.execute(text(sql))


if __name__ == "__main__":
    main()
