"""대화 만들기 · 닫기 · 추출 저장, /todos · /events — 가짜 추출 결과로 (키 없이)"""
from datetime import datetime

import pytest
from sqlalchemy import text

from app.ai.extract import KST
from app.routers import conversations as conv_router
from app.routers import messages as messages_router

REAL_EXTRACT_BG = conv_router._extract_in_background


@pytest.fixture(autouse=True)
def clean(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE messages, tasks RESTART IDENTITY"))
        c.execute(text("DELETE FROM conversations WHERE id NOT IN (:a, :b)"),
                  {"a": ids["conv_parent1"], "b": ids["conv_parent2"]})
        c.execute(text("UPDATE conversations SET status = 'open', extract = NULL"))


@pytest.fixture
def extractor(monkeypatch):
    """extractor(result_or_fn): 닫으면 진짜 백그라운드 흐름을 돌리되 extract_tasks 대신 이것을 쓴다. 받은 인자는 calls 에."""
    calls = []

    def use(result):
        def fake(history, today, existing, roster, adults):
            calls.append({"history": history, "today": today, "existing": existing})
            return result(history) if callable(result) else result

        monkeypatch.setitem(messages_router._refine_state, "enabled", True)
        monkeypatch.setattr(conv_router, "_extract_in_background", REAL_EXTRACT_BG)
        monkeypatch.setattr(conv_router, "extract_tasks", fake)
        return calls

    return use


def put(engine, conv, sender, status, raw, refined=None):
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, status) "
                       "VALUES (:c, :s, :r, :f, :st)"), {"c": conv, "s": sender, "r": raw, "f": refined, "st": status})


DONE = {"status": "done", "error": None, "tasks": [
    {"kind": "todo", "title": "체육 선생님께 전달하기", "due_text": None, "due_at": None},
    {"kind": "event", "title": "학부모 상담", "due_text": "다음 주 화요일 오후 3시",
     "due_at": datetime(2026, 11, 17, 15, 0, tzinfo=KST)},
]}


def close(client, auth, conv, who="teacher1"):
    return client.post(f"/conversations/{conv}/close", headers=auth(who))


def test_닫으면_추출해서_후보로_저장된다(client, auth, ids, engine, extractor):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 무능하네 상담하자고", "상담하고 싶습니다.")
    put(engine, conv, ids["parent1"], "failed", "정제 안 된 원문")
    put(engine, conv, ids["teacher1"], "skip", "다음 주 화요일 오후 3시 어떠세요?")
    calls = extractor(DONE)

    r = close(client, auth, conv)
    assert r.status_code == 202 and r.json()["status"] == "closed"
    hist = calls[0]["history"]
    assert [(h["who"], h["text"]) for h in hist] == [("parent", "상담하고 싶습니다."),
                                                     ("teacher", "다음 주 화요일 오후 3시 어떠세요?")]
    assert calls[0]["existing"] == []

    c = client.get(f"/conversations/{conv}", headers=auth("teacher1")).json()
    assert c["status"] == "closed" and c["extract"]["status"] == "done" and c["extract"]["count"] == 2
    todos = client.get("/todos", headers=auth("teacher1")).json()
    events = client.get("/events", headers=auth("teacher1")).json()
    assert [(t["title"], t["status"], t["student_name"]) for t in todos] == [("체육 선생님께 전달하기", "candidate", "학생")]
    assert events[0]["title"] == "학부모 상담" and events[0]["due_text"] == "다음 주 화요일 오후 3시"
    assert datetime.fromisoformat(events[0]["due_at"]) == datetime(2026, 11, 17, 15, 0, tzinfo=KST)


def test_학부모는_닫지도_할_일을_보지도_못한다(client, auth, ids, extractor):
    extractor(DONE)
    assert close(client, auth, ids["conv_parent1"], "parent1").status_code == 403
    assert client.get("/todos", headers=auth("parent1")).status_code == 403
    assert "extract" not in client.get(f"/conversations/{ids['conv_parent1']}", headers=auth("parent1")).json()


def test_실패하면_사유를_남기고_다시_뽑을_수_있다(client, auth, ids, engine, extractor):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["teacher1"], "skip", "안녕하세요")
    extractor({"status": "failed", "tasks": [], "error": "Claude 호출 실패 (HTTP 529)"})
    close(client, auth, conv)
    c = client.get(f"/conversations/{conv}", headers=auth("teacher1")).json()
    assert c["extract"]["status"] == "failed" and "529" in c["extract"]["error"]

    extractor(DONE)
    r = client.post(f"/conversations/{conv}/extract", headers=auth("teacher1"))
    assert r.status_code == 202
    assert client.get(f"/conversations/{conv}", headers=auth("teacher1")).json()["extract"]["count"] == 2


def test_열린_대화는_다시_뽑기_안_됨(client, auth, ids):
    assert client.post(f"/conversations/{ids['conv_parent1']}/extract", headers=auth("teacher1")).status_code == 409


def test_스위치가_꺼져_있으면_Claude_를_안_부르고_실패(client, auth, ids, engine, extractor, monkeypatch):
    calls = extractor(DONE)
    monkeypatch.setitem(messages_router._refine_state, "enabled", False)
    close(client, auth, ids["conv_parent1"])
    assert calls == []
    c = client.get(f"/conversations/{ids['conv_parent1']}", headers=auth("teacher1")).json()
    assert c["extract"]["status"] == "failed" and "꺼져" in c["extract"]["error"]


def test_새_메시지가_오면_다시_열리고_다시_닫으면_후보만_바뀐다(client, auth, ids, engine, extractor):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["teacher1"], "skip", "안녕하세요")
    extractor(DONE)
    close(client, auth, conv)
    todo = client.get("/todos", headers=auth("teacher1")).json()[0]
    r = client.patch(f"/todos/{todo['id']}", json={"status": "added"}, headers=auth("teacher1"))
    assert r.status_code == 200 and r.json()["status"] == "added"

    client.post(f"/conversations/{conv}/messages", json={"text": "하나 더요"}, headers=auth("parent1"))
    assert client.get(f"/conversations/{conv}", headers=auth("teacher1")).json()["status"] == "open"

    calls = extractor({"status": "done", "error": None, "tasks": [
        {"kind": "event", "title": "새 일정", "due_text": None, "due_at": None}]})
    close(client, auth, conv)
    assert calls[-1]["existing"] == [{"kind": "todo", "title": "체육 선생님께 전달하기"}]
    assert [t["title"] for t in client.get("/todos", headers=auth("teacher1")).json()] == ["체육 선생님께 전달하기"]
    assert [t["title"] for t in client.get("/events", headers=auth("teacher1")).json()] == ["새 일정"]  # 옛 후보 「학부모 상담」은 바뀜


def test_할_일_고치기_완료_지우기와_필터(client, auth, ids, engine, extractor):
    put(engine, ids["conv_parent1"], ids["teacher1"], "skip", "안녕하세요")
    extractor(DONE)
    close(client, auth, ids["conv_parent1"])
    h = auth("teacher1")
    ev = client.get("/events", headers=h).json()[0]

    r = client.patch(f"/events/{ev['id']}", json={"title": "상담 (교실)", "due_at": None, "status": "done"}, headers=h)
    assert r.status_code == 200
    assert (r.json()["title"], r.json()["due_at"], r.json()["status"]) == ("상담 (교실)", None, "done")
    assert client.patch(f"/events/{ev['id']}", json={"title": None}, headers=h).json()["title"] == "상담 (교실)"
    assert client.get("/events?status=candidate", headers=h).json() == []
    assert len(client.get(f"/events?conversation_id={ids['conv_parent2']}", headers=h).json()) == 0
    assert client.patch(f"/todos/{ev['id']}", json={"status": "done"}, headers=h).status_code == 404  # 종류가 다름
    assert client.delete(f"/events/{ev['id']}", headers=h).status_code == 204
    assert client.get("/events", headers=h).json() == []


def test_대화_만들기(client, auth, ids):
    h = auth("teacher1")
    r = client.post("/conversations", json={"parent_id": ids["parent1"], "student_name": "지민"}, headers=h)
    assert r.status_code == 201 and r.json()["student_name"] == "지민" and r.json()["status"] == "open"
    again = client.post("/conversations", json={"parent_id": ids["parent1"], "student_name": "지민"}, headers=h)
    assert again.status_code == 409
    assert client.post("/conversations", json={"parent_id": ids["teacher1"], "student_name": "x"}, headers=h).status_code == 404
    assert client.post("/conversations", json={"parent_id": ids["parent1"], "student_name": "x"},
                       headers=auth("parent1")).status_code == 403
    mine = client.get("/conversations", headers=auth("parent1")).json()
    assert [c["student_name"] for c in mine] == ["학생", "지민"]


def test_시험용_초기화는_DEV_TOOLS_일_때만_되고_내용만_지운다(client, auth, ids, engine, extractor, monkeypatch):
    from app.core.config import settings

    put(engine, ids["conv_parent1"], ids["teacher1"], "skip", "안녕하세요")
    extractor(DONE)
    close(client, auth, ids["conv_parent1"])
    monkeypatch.setattr(settings, "dev_tools", False)
    assert client.post("/dev/reset").status_code == 404

    monkeypatch.setattr(settings, "dev_tools", True)
    assert client.post("/dev/reset").status_code == 200
    h = auth("teacher1")
    assert client.get(f"/conversations/{ids['conv_parent1']}/messages", headers=h).json() == []
    assert client.get("/todos", headers=h).json() == [] and client.get("/events", headers=h).json() == []
    c = client.get(f"/conversations/{ids['conv_parent1']}", headers=h).json()
    assert c["status"] == "open" and c["extract"] is None
