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
    assert [(r["student_name"], r["parent_name"]) for r in rows] == [
        ("민재", "이도윤"), ("서윤", "박서연")]  # 하준은 학부모가 없어서 빠짐


def test_학부모는_자기_아이만_보인다(client, auth, kids):
    rows = client.get("/conversations/startable", headers=auth("parent1")).json()
    assert [(r["student_name"], r["teacher_name"]) for r in rows] == [("서윤", "김민지")]
    assert client.get("/conversations/startable", headers=auth("team1")).status_code == 403


def test_학부모가_시작하면_담임과의_새_대화가_생긴다(client, auth, ids, kids, notified):
    r = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("parent1"))
    assert r.status_code == 201, r.text
    conv = r.json()
    assert (conv["teacher_id"], conv["parent_id"], conv["student_name"], conv["status"]) == (
        ids["teacher1"], ids["parent1"], "서윤", "open")
    assert "extract" not in conv  # 학부모에게는 교사용 칸을 안 줌
    assert notified == [conv["id"]]


def test_문의마다_새_대화방_열린_대화가_있어도(client, auth, ids, kids, notified):
    a = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("parent1")).json()
    b = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("parent1")).json()
    c = client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("teacher1")).json()
    assert len({a["id"], b["id"], c["id"]}) == 3
    client.post(f"/conversations/{b['id']}/messages", json={"text": "준비물 문의드립니다"}, headers=auth("parent1"))
    mine = {x["id"]: x for x in client.get("/conversations", headers=auth("parent1")).json()}
    assert {a["id"], b["id"], c["id"]} <= set(mine)
    assert mine[a["id"]]["last_message_at"] is None and mine[b["id"]]["last_message_at"]  # 목록 정렬 · 표시용
    assert notified[:3] == [a["id"], b["id"], c["id"]]  # 만들 때마다 상대에게 알림 (그 뒤는 메시지 알림)


def test_남의_아이_학부모_없는_학생은_시작_못_함(client, auth, kids):
    assert client.post("/conversations/start", json={"student_id": kids["민재"]}, headers=auth("parent1")).status_code == 404
    assert client.post("/conversations/start", json={"student_id": kids["하준"]}, headers=auth("teacher1")).status_code == 404
    assert client.post("/conversations/start", json={"student_id": kids["서윤"]}, headers=auth("team1")).status_code == 403
