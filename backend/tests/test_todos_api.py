"""교사가 직접 등록하는 할 일 (POST /todos)"""
import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def clean(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE tasks RESTART IDENTITY"))


def test_교사가_할_일을_직접_등록한다(client, auth, ids):
    r = client.post("/todos", headers=auth("teacher1"), json={"title": "  가정통신문 인쇄  ", "due_at": "2026-11-20T09:00:00+09:00"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["title"] == "가정통신문 인쇄" and t["kind"] == "todo" and t["status"] == "added"
    assert t["conversation_id"] is None and t["due_at"] is not None
    assert [x["id"] for x in client.get("/todos", headers=auth("teacher1")).json()] == [t["id"]]
    assert client.get("/events", headers=auth("teacher1")).json() == []  # 일정 목록에는 안 나온다


def test_기한_없이도_등록되고_기한_있는_것_뒤에_온다(client, auth, ids):
    a = client.post("/todos", headers=auth("teacher1"), json={"title": "기한 없음"})
    assert a.status_code == 201 and a.json()["due_at"] is None
    client.post("/todos", headers=auth("teacher1"), json={"title": "기한 있음", "due_at": "2026-11-20T00:00:00+09:00"})
    assert [t["title"] for t in client.get("/todos", headers=auth("teacher1")).json()] == ["기한 있음", "기한 없음"]


def test_학부모는_등록할_수_없고_제목은_비울_수_없다(client, auth, ids):
    assert client.post("/todos", headers=auth("parent1"), json={"title": "x"}).status_code == 403
    assert client.post("/todos", json={"title": "x"}).status_code in (401, 403)
    for body in ({}, {"title": ""}, {"title": "   "}, {"title": "가" * 101}):
        assert client.post("/todos", headers=auth("teacher1"), json=body).status_code == 422
    assert client.get("/todos", headers=auth("teacher1")).json() == []
