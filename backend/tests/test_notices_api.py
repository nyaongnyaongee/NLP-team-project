"""공지 저장 · 보내기 API (Claude 안 부름)"""
import pytest
from sqlalchemy import text

from app.routers import notices as notices_router


@pytest.fixture(autouse=True)
def clean_notices(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE notices RESTART IDENTITY"))


@pytest.fixture
def sent_to(monkeypatch):
    """보내기 알림을 받은 사람 목록 (진짜 WebSocket 대신)"""
    calls = []
    monkeypatch.setattr(notices_router.hub, "notify_users", lambda uids, data: calls.append((sorted(uids), data)))
    return calls


def make(client, auth, title="현장학습 안내", body="11월 14일 9시 운동장"):
    r = client.post("/notices", json={"title": title, "body": body}, headers=auth("teacher1"))
    assert r.status_code == 201, r.text
    return r.json()


def test_저장한_공지는_학부모에게_안_보이고_보내면_보인다(client, auth, ids, sent_to):
    n = make(client, auth)
    assert n["status"] == "draft" and n["sent_at"] is None
    assert client.get("/notices", headers=auth("parent1")).json() == []
    assert [x["id"] for x in client.get("/notices", headers=auth("teacher1")).json()] == [n["id"]]

    r = client.post(f"/notices/{n['id']}/send", headers=auth("teacher1"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent" and r.json()["sent_at"]
    for who in ("parent1", "parent2"):  # teacher1 과 대화가 있는 학부모 둘 다
        got = client.get("/notices", headers=auth(who)).json()
        assert [(x["title"], x["body"]) for x in got] == [("현장학습 안내", "11월 14일 9시 운동장")]
        assert client.get(f"/notices/{n['id']}", headers=auth(who)).status_code == 200
    assert sent_to == [(sorted([ids["parent1"], ids["parent2"], ids["teacher1"]]), {"type": "notice", "notice_id": n["id"]})]


def test_쓰는_중에는_고치고_지울_수_있다(client, auth):
    n = make(client, auth)
    r = client.patch(f"/notices/{n['id']}", json={"body": "  고친 본문  "}, headers=auth("teacher1"))
    assert r.status_code == 200 and r.json()["body"] == "고친 본문" and r.json()["title"] == "현장학습 안내"
    assert client.delete(f"/notices/{n['id']}", headers=auth("teacher1")).status_code == 204
    assert client.get("/notices", headers=auth("teacher1")).json() == []


def test_보낸_공지는_다시_보낼_수_없다(client, auth, sent_to):
    n = make(client, auth)
    client.post(f"/notices/{n['id']}/send", headers=auth("teacher1"))
    assert client.post(f"/notices/{n['id']}/send", headers=auth("teacher1")).status_code == 409
    assert len(sent_to) == 1


def test_보낸_공지를_고치면_학부모에게_바뀐_글이_보이고_알림이_간다(client, auth, ids, sent_to):
    n = make(client, auth)
    sent = client.post(f"/notices/{n['id']}/send", headers=auth("teacher1")).json()
    assert sent["updated_at"] <= sent["sent_at"]  # 아직 「수정됨」 아님
    r = client.patch(f"/notices/{n['id']}", json={"body": " 9시 → 9시 30분 "}, headers=auth("teacher1"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent" and r.json()["sent_at"] == sent["sent_at"]
    assert r.json()["updated_at"] > r.json()["sent_at"]  # 화면이 「수정됨」 으로 보임
    got = client.get("/notices", headers=auth("parent1")).json()
    assert [(x["title"], x["body"]) for x in got] == [("현장학습 안내", "9시 → 9시 30분")]
    everyone = sorted([ids["parent1"], ids["parent2"], ids["teacher1"]])
    assert sent_to == [(everyone, {"type": "notice", "notice_id": n["id"]})] * 2


def test_보낸_공지를_지우면_학부모_화면에서도_사라진다(client, auth, ids, sent_to):
    n = make(client, auth)
    client.post(f"/notices/{n['id']}/send", headers=auth("teacher1"))
    assert client.delete(f"/notices/{n['id']}", headers=auth("teacher1")).status_code == 204
    assert client.get("/notices", headers=auth("parent1")).json() == []
    assert client.get(f"/notices/{n['id']}", headers=auth("parent1")).status_code == 404
    assert len(sent_to) == 2  # 보내기 + 지우기


def test_쓰는_중인_공지를_고치거나_지울_때는_알림이_없다(client, auth, sent_to):
    n = make(client, auth)
    client.patch(f"/notices/{n['id']}", json={"title": "고침"}, headers=auth("teacher1"))
    client.delete(f"/notices/{n['id']}", headers=auth("teacher1"))
    assert sent_to == []


def test_다른_교사나_학부모는_고치거나_지울_수_없다(client, auth):
    n = make(client, auth)
    p = auth("parent1")
    assert client.patch(f"/notices/{n['id']}", json={"title": "x"}, headers=p).status_code == 403
    assert client.delete(f"/notices/{n['id']}", headers=p).status_code == 403
    assert client.patch("/notices/99999", json={"title": "x"}, headers=auth("teacher1")).status_code == 404


def test_학부모는_쓰거나_보낼_수_없고_쓰는_중인_공지도_못_본다(client, auth):
    n = make(client, auth)
    p = auth("parent1")
    assert client.post("/notices", json={"title": "a", "body": "b"}, headers=p).status_code == 403
    assert client.post(f"/notices/{n['id']}/send", headers=p).status_code == 403
    assert client.get(f"/notices/{n['id']}", headers=p).status_code == 404


def test_대화가_없는_학부모는_공지를_못_받는다(client, auth, engine, sent_to):
    from app.core.auth import hash_password
    with engine.begin() as c:
        c.execute(text("INSERT INTO users (role,name,login_id,password_hash) VALUES ('parent','최하늘','parent9',:p) "
                       "ON CONFLICT (login_id) DO NOTHING"), {"p": hash_password("pw1234")})
    n = make(client, auth)
    client.post(f"/notices/{n['id']}/send", headers=auth("teacher1"))
    assert client.get("/notices", headers=auth("parent9")).json() == []


def test_빈_제목은_안_된다(client, auth):
    assert client.post("/notices", json={"title": "", "body": "b"}, headers=auth("teacher1")).status_code == 422
    assert client.post("/notices", json={"title": "a"}, headers=auth("teacher1")).status_code == 422
