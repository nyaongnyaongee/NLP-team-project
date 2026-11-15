"""학부모 캘린더 — 교사가 공유한 일정만, 볼 사람에게만"""
import pytest
from sqlalchemy import text

from app.core.auth import hash_password
from app.routers.ws import hub


@pytest.fixture(autouse=True)
def clean(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE tasks RESTART IDENTITY"))
        c.execute(text("DELETE FROM users WHERE login_id = 'outsider_ev'"))


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(hub, "notify_users", lambda user_ids, data: calls.append((sorted(user_ids), data)))
    return calls


def titles(client, auth, who):
    r = client.get("/events", headers=auth(who))
    assert r.status_code == 200
    return [e["title"] for e in r.json()]


def conv_event(engine, conv, title, status="added", shared=True):
    with engine.begin() as c:
        return c.execute(text("INSERT INTO tasks (conversation_id, kind, title, status, shared) "
                              "VALUES (:c, 'event', :t, :s, :sh) RETURNING id"),
                         {"c": conv, "t": title, "s": status, "sh": shared}).scalar()


def test_교사가_등록한_반_일정은_반_학부모_모두에게_보인다(client, auth, ids, engine, sent):
    with engine.begin() as c:  # 이 교사와 아무 관계 없는 학부모
        c.execute(text("INSERT INTO users (role, name, login_id, password_hash) VALUES ('parent', '남', 'outsider_ev', :p)"),
                  {"p": hash_password("pw1234")})
    r = client.post("/events", headers=auth("teacher1"),
                    json={"title": "운동회", "due_at": "2026-11-20T09:00:00+09:00"})
    assert r.status_code == 201
    ev = r.json()
    assert ev["conversation_id"] is None and ev["student_name"] is None and ev["status"] == "added" and ev["shared"]
    assert sent[-1] == (sorted([ids["parent1"], ids["parent2"]]), {"type": "events"})

    assert titles(client, auth, "parent1") == ["운동회"] and titles(client, auth, "parent2") == ["운동회"]
    assert titles(client, auth, "outsider_ev") == []
    p = client.get("/events", headers=auth("parent1")).json()[0]
    assert p["teacher_name"] == "김민지" and "shared" not in p

    # 공유를 끄면 학부모 캘린더에서 빠진다 (교사 캘린더에는 그대로)
    assert client.patch(f"/events/{ev['id']}", headers=auth("teacher1"), json={"shared": False}).json()["shared"] is False
    assert titles(client, auth, "parent1") == []
    assert titles(client, auth, "teacher1") == ["운동회"]


def test_대화에서_나온_일정은_그_학부모만_추가한_것만(client, auth, ids, engine, sent):
    conv_event(engine, ids["conv_parent1"], "후보 상담", status="candidate")
    eid = conv_event(engine, ids["conv_parent1"], "학부모 상담", status="candidate")
    conv_event(engine, ids["conv_parent1"], "비공개", shared=False)
    assert titles(client, auth, "parent1") == []

    client.patch(f"/events/{eid}", headers=auth("teacher1"), json={"status": "added"})  # [추가]
    assert sent[-1] == ([ids["parent1"]], {"type": "events"})
    assert titles(client, auth, "parent1") == ["학부모 상담"]
    assert titles(client, auth, "parent2") == []

    client.delete(f"/events/{eid}", headers=auth("teacher1"))
    assert titles(client, auth, "parent1") == []


def test_권한(client, auth, ids):
    assert client.post("/events", headers=auth("parent1"), json={"title": "x"}).status_code == 403
    assert client.get("/todos", headers=auth("parent1")).status_code == 403  # 할 일은 여전히 교사만
    assert client.get("/events", headers=auth("team1")).status_code == 403
    assert client.post("/events", headers=auth("teacher1"), json={"title": ""}).status_code == 422
