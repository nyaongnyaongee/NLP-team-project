"""메시지 보내기 → DB 저장 → 다른 계정에서 조회"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.usefixtures("clean_messages")  # 테스트마다 메시지 비우기


def test_로그인_성공과_실패(client):
    ok = client.post("/auth/login", json={"login_id": "parent1", "password": "pw1234"})
    assert ok.status_code == 200 and ok.json()["role"] == "parent"
    bad = client.post("/auth/login", json={"login_id": "parent1", "password": "틀림"})
    assert bad.status_code == 401
    nobody = client.post("/auth/login", json={"login_id": "없는사람", "password": "pw1234"})
    assert nobody.status_code == 401


def test_학부모_메시지는_pending_으로_저장된다(client, auth, ids, engine):
    r = client.post(f"/conversations/{ids['conv_parent1']}/messages",
                    json={"text": "짝 좀 바꿔주세요"}, headers=auth("parent1"))
    assert r.status_code == 201
    assert r.json()["status"] == "pending" and r.json()["refined_text"] is None
    with engine.connect() as c:  # 응답만이 아니라 DB 에 진짜 들어갔는지
        row = c.execute(text("SELECT raw_text, status, sender_id FROM messages")).one()
    assert row == ("짝 좀 바꿔주세요", "pending", ids["parent1"])


def test_교사_메시지는_skip_으로_저장된다(client, auth, ids):
    r = client.post(f"/conversations/{ids['conv_parent1']}/messages",
                    json={"text": "확인해 보겠습니다"}, headers=auth("teacher1"))
    assert r.status_code == 201 and r.json()["status"] == "skip"


def test_교사가_학부모_메시지를_본다(client, auth, ids):
    conv = ids["conv_parent1"]
    client.post(f"/conversations/{conv}/messages", json={"text": "첫째"}, headers=auth("parent1"))
    client.post(f"/conversations/{conv}/messages", json={"text": "둘째"}, headers=auth("parent1"))
    r = client.get(f"/conversations/{conv}/messages", headers=auth("teacher1"))
    assert [m["raw_text"] for m in r.json()] == ["첫째", "둘째"]  # 보낸 순서대로


def test_학부모는_다른_학부모_대화를_못_본다(client, auth, ids):
    conv = ids["conv_parent1"]
    client.post(f"/conversations/{conv}/messages", json={"text": "비밀"}, headers=auth("parent1"))
    assert client.get(f"/conversations/{conv}/messages", headers=auth("parent2")).status_code == 404
    assert client.post(f"/conversations/{conv}/messages", json={"text": "끼어들기"},
                       headers=auth("parent2")).status_code == 404


def test_내_대화_목록에는_내_대화만_나온다(client, auth, ids):
    p1 = client.get("/conversations", headers=auth("parent1")).json()
    assert [c["id"] for c in p1] == [ids["conv_parent1"]]
    t = client.get("/conversations", headers=auth("teacher1")).json()
    assert {c["id"] for c in t} == {ids["conv_parent1"], ids["conv_parent2"]}


def test_로그인_없이는_막힌다(client, ids):
    assert client.get(f"/conversations/{ids['conv_parent1']}/messages").status_code == 401
    bad = {"Authorization": "Bearer fake.token"}
    assert client.get("/conversations", headers=bad).status_code == 401


def test_없는_대화는_404(client, auth):
    assert client.get("/conversations/99999/messages", headers=auth("parent1")).status_code == 404
