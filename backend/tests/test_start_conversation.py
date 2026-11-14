"""대화 시작 (교사 · 학부모 둘 다) — 학생 ↔ 학부모 연결(students.parent_id)로"""
import pytest
from sqlalchemy import text

from app.routers import conversations as conv_router


@pytest.fixture
def kids(engine, ids):
    """teacher1 반: 서윤(parent1), 민재(parent2), 하준(학부모 없음)"""
    with engine.begin() as c:
        out = {}
        for name, parent in [("서윤", ids["parent1"]), ("민재", ids["parent2"]), ("하준", None)]:
            out[name] = c.execute(text("INSERT INTO students (teacher_id, name, parent_id) VALUES (:t, :n, :p) RETURNING id"),
                                  {"t": ids["teacher1"], "n": name, "p": parent}).scalar()
    yield out
    with engine.begin() as c:
        c.execute(text("TRUNCATE messages, tasks RESTART IDENTITY"))
        c.execute(text("UPDATE conversations SET student_id = NULL"))
        c.execute(text("DELETE FROM conversations WHERE id NOT IN (:a, :b)"),
                  {"a": ids["conv_parent1"], "b": ids["conv_parent2"]})
        c.execute(text("DELETE FROM students"))


@pytest.fixture
def notified(monkeypatch):
    calls = []
    monkeypatch.setattr(conv_router.hub, "notify_conversation", lambda conv_id: calls.append(conv_id))
    return calls


def test_교사는_학부모가_등록된_반_학생만_고를_수_있다(client, auth, kids):
    rows = client.get("/conversations/startable", headers=auth("teacher1")).json()
    assert [(r["student_name"], r["parent_name"], r["open_conversation_id"]) for r in rows] == [
        ("민재", "이도윤", None), ("서윤", "박서연", None)]  # 하준은 학부모가 없어서 빠짐


def test_학부모는_자기_아이만_보인다(client, auth, kids):
    rows = client.get("/conversations/startable", headers=auth("parent1")).json()
    assert [(r["student_name"], r["teacher_name"]) for r in rows] == [("서윤", "김민지")]
    assert client.get("/conversations/startable", headers=auth("team1")).status_code == 403


def test_학부모가_시작하면_담임과의_대화가_생기고_다시_누르면_같은_대화(client, auth, ids, kids, notified):
    r = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("parent1"))
    assert r.status_code == 201, r.text
    conv = r.json()
    assert (conv["teacher_id"], conv["parent_id"], conv["student_name"], conv["status"]) == (
        ids["teacher1"], ids["parent1"], "서윤", "open")
    assert "extract" not in conv  # 학부모에게는 교사용 칸을 안 줌
    assert notified == [conv["id"]]

    again = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("parent1"))
    assert again.status_code == 200 and again.json()["id"] == conv["id"]
    by_teacher = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("teacher1"))
    assert by_teacher.status_code == 200 and by_teacher.json()["id"] == conv["id"]  # 교사가 눌러도 같은 대화
    assert client.get("/conversations/startable", headers=auth("teacher1")).json()[1]["open_conversation_id"] == conv["id"]
    assert len(notified) == 1


def test_닫힌_대화만_있으면_새로_연다(client, auth, kids, notified):
    first = client.post("/conversations/start", json={"student_id": kids["민재"]}, headers=auth("teacher1")).json()
    client.post(f"/conversations/{first['id']}/close", headers=auth("teacher1"))
    r = client.post("/conversations/start", json={"student_id": kids["민재"]}, headers=auth("parent2"))
    assert r.status_code == 201 and r.json()["id"] != first["id"]


def test_남의_아이_학부모_없는_학생은_시작_못_함(client, auth, kids):
    assert client.post("/conversations/start", json={"student_id": kids["민재"]}, headers=auth("parent1")).status_code == 404
    assert client.post("/conversations/start", json={"student_id": kids["하준"]}, headers=auth("teacher1")).status_code == 404
    assert client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("team1")).status_code == 403
