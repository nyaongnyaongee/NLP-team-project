"""시험용 DB(eum_test)를 따로 만들어 쓴다. 진짜 eum 은 건드리지 않는다.
실행: cd backend && source .venv/bin/activate && pytest   (PostgreSQL 이 켜져 있어야 함)
"""
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SCHEMA = Path(__file__).resolve().parents[1] / "app" / "db" / "schema.sql"


def _test_url() -> str:
    # .env 의 DATABASE_URL 에서 DB 이름만 eum_test 로 바꾼다
    base = os.environ.get("DATABASE_URL")
    if not base:
        for line in (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                base = line.split("=", 1)[1]
    return make_url(base).set(database="eum_test").render_as_string(hide_password=False)


TEST_URL = _test_url()
os.environ["DATABASE_URL"] = TEST_URL  # app 을 import 하기 전에 바꿔야 한다
os.environ.setdefault("JWT_SECRET", "test-secret")


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(make_url(TEST_URL).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text("SELECT 1 FROM pg_database WHERE datname='eum_test'")).scalar():
            c.execute(text("CREATE DATABASE eum_test"))
    eng = create_engine(TEST_URL)
    with eng.begin() as c:  # 매번 깨끗하게: 테이블 지우고 schema.sql 로 다시 만들기
        c.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    raw = eng.raw_connection()
    raw.cursor().execute(SCHEMA.read_text(encoding="utf-8"))
    raw.commit()
    raw.close()
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def ids(engine):
    """계정 3개 + 대화 2개 (parent1↔teacher1, parent2↔teacher1)"""
    from app.core.auth import hash_password

    out = {}
    with engine.begin() as c:
        for role, name, login in [("teacher", "김민지", "teacher1"), ("parent", "박서연", "parent1"),
                                  ("parent", "이도윤", "parent2")]:
            out[login] = c.execute(
                text("INSERT INTO users (role,name,login_id,password_hash) VALUES (:r,:n,:l,:p) RETURNING id"),
                {"r": role, "n": name, "l": login, "p": hash_password("pw1234")},
            ).scalar()
        for parent in ("parent1", "parent2"):
            out["conv_" + parent] = c.execute(
                text("INSERT INTO conversations (teacher_id,parent_id,student_name) VALUES (:t,:p,'학생') RETURNING id"),
                {"t": out["teacher1"], "p": out[parent]},
            ).scalar()
    return out


@pytest.fixture(autouse=True)
def clean_messages(engine, ids):
    yield
    with engine.begin() as c:  # 테스트마다 메시지만 비운다
        c.execute(text("TRUNCATE messages RESTART IDENTITY"))


@pytest.fixture(scope="session")
def client(ids):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


@pytest.fixture(scope="session")
def auth(client):
    """auth('parent1') -> 인증 헤더"""
    def _login(login_id: str) -> dict:
        r = client.post("/auth/login", json={"login_id": login_id, "password": "pw1234"})
        assert r.status_code == 200
        return {"Authorization": "Bearer " + r.json()["token"]}
    return _login
