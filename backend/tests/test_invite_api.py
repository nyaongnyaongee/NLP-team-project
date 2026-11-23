"""초대 코드: 교사 반 코드 + 자녀 이름으로 들어오기(가입 없이, 시연) · 자녀 더하기"""
import pytest
from sqlalchemy import text


@pytest.fixture
def invite(engine, ids):
    """teacher1 반 코드 TEST26, 반에 하준(학부모 없음) · 서윤(parent1)"""
    with engine.begin() as c:
        c.execute(text("UPDATE users SET invite_code = 'TEST26' WHERE id = :t"), {"t": ids["teacher1"]})
        for name, parent in [("하준", None), ("서윤", ids["parent1"])]:
            c.execute(text("INSERT INTO students (teacher_id, name, parent_id) VALUES (:t, :n, :p)"),
                      {"t": ids["teacher1"], "n": name, "p": parent})
    yield "TEST26"
    with engine.begin() as c:
        c.execute(text("TRUNCATE messages, tasks RESTART IDENTITY"))
        c.execute(text("UPDATE conversations SET student_id = NULL"))
        c.execute(text("DELETE FROM conversations WHERE id NOT IN (:a, :b)"),
                  {"a": ids["conv_parent1"], "b": ids["conv_parent2"]})
        c.execute(text("DELETE FROM students"))
        c.execute(text("UPDATE users SET invite_code = NULL"))
        c.execute(text("DELETE FROM users WHERE login_id LIKE 'guest-%'"))


def _join(client, code="TEST26", student="김하늘", parent="김보호"):
    return client.post("/auth/join", json={"invite_code": code, "student_name": student, "parent_name": parent})


def test_코드로_들어오면_학부모가_되고_자녀가_반에_이어진다(client, auth, invite):
    r = _join(client, code=" test-26 ")  # 대소문자 · 띄어쓰기 · 붙임표는 무시
    assert r.status_code == 200
    assert r.json()["role"] == "parent" and r.json()["name"] == "김보호"
    me = {"Authorization": "Bearer " + r.json()["token"]}
    rows = client.get("/conversations/startable", headers=me).json()
    assert [(s["student_name"], s["teacher_name"]) for s in rows] == [("김하늘", "김민지")]
    # 교사 반 명단에도 들어감 (이어진 학부모 이름과 함께) → 바로 대화를 열 수 있음
    roster = {s["name"]: s["parent_name"] for s in client.get("/students", headers=auth("teacher1")).json()}
    assert roster["김하늘"] == "김보호" and roster["하준"] is None
    assert client.post("/conversations/start", json={"student_id": rows[0]["student_id"]}, headers=me).status_code == 201


def test_명단에_있고_학부모가_없는_학생이면_그_학생에_잇는다(client, auth, invite):
    me = {"Authorization": "Bearer " + _join(client, student="하준").json()["token"]}
    assert [s["student_name"] for s in client.get("/conversations/startable", headers=me).json()] == ["하준"]
    assert [s["name"] for s in client.get("/students", headers=auth("teacher1")).json()].count("하준") == 1


def test_틀린_코드_이미_이어진_학생_이상한_이름은_안_된다(client, invite):
    assert _join(client, code="NOPE00").status_code == 400
    assert _join(client, code="").status_code == 400
    r = _join(client, student="서윤")
    assert r.status_code == 409 and "다른 보호자" in r.json()["detail"]
    assert _join(client, student="ㅋ").status_code == 400
    assert _join(client, parent="<b>x</b>").status_code == 400


def test_학부모는_코드로_자녀를_더_잇는다(client, auth, invite):
    r = client.post("/children", json={"invite_code": "TEST26", "student_name": "박둘째"}, headers=auth("parent1"))
    assert r.status_code == 200 and r.json()["student_name"] == "박둘째"
    names = [s["student_name"] for s in client.get("/conversations/startable", headers=auth("parent1")).json()]
    # PostgreSQL 의 한글 정렬 순서는 서버 로캘에 따라 달라질 수 있다.
    assert set(names) == {"박둘째", "서윤"}
    again = client.post("/children", json={"invite_code": "TEST26", "student_name": "서윤"}, headers=auth("parent1"))
    assert again.status_code == 409 and "이미 연결된" in again.json()["detail"]
    assert client.post("/children", json={"invite_code": "TEST26", "student_name": "누구"},
                       headers=auth("teacher1")).status_code == 403


def test_교사는_자기_초대_코드를_본다_없으면_만든다(client, auth, engine, ids, invite):
    assert client.get("/students/invite", headers=auth("teacher1")).json() == {"code": "TEST26"}
    with engine.begin() as c:
        c.execute(text("UPDATE users SET invite_code = NULL WHERE id = :t"), {"t": ids["teacher1"]})
    code = client.get("/students/invite", headers=auth("teacher1")).json()["code"]
    assert len(code) == 6 and code == client.get("/students/invite", headers=auth("teacher1")).json()["code"]
    assert client.get("/students/invite", headers=auth("parent1")).status_code == 403
