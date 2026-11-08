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
        print("테이블 만듦 (users · conversations · messages · tasks)")


if __name__ == "__main__":
    main()
