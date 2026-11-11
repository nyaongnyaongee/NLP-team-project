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


def test_교사가_수정한_최종_답장은_메시지로_저장된다(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    answer = "확인했습니다. 내일 다시 알려드리겠습니다."
    response = client.post(f"/conversations/{conv}/messages", json={"text": answer}, headers=auth("teacher1"))
    assert response.status_code == 201
    assert response.json()["status"] == "skip" and response.json()["raw_text"] == answer
    assert response.json()["refined_text"] is None
    with engine.connect() as c:
        row = c.execute(text("SELECT raw_text, refined_text, status, sender_id FROM messages WHERE id = :i"),
                        {"i": response.json()["id"]}).one()
    assert row == (answer, None, "skip", ids["teacher1"])
    visible = client.get(f"/conversations/{conv}/messages", headers=auth("parent1")).json()[0]
    assert visible["raw_text"] == answer


def test_교사는_학부모_메시지가_온_것을_보지만_원문은_못_본다(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    client.post(f"/conversations/{conv}/messages", json={"text": "첫째"}, headers=auth("parent1"))
    client.post(f"/conversations/{conv}/messages", json={"text": "둘째"}, headers=auth("parent1"))
    msgs = client.get(f"/conversations/{conv}/messages", headers=auth("teacher1")).json()
    assert len(msgs) == 2 and msgs[0]["id"] < msgs[1]["id"]  # 보낸 순서대로
    assert all(m["raw_text"] is None for m in msgs)  # 원문은 교사에게 안 간다 (정제 전이라 정제문도 아직 없음)
    with engine.connect() as c:  # 원문은 DB 에 그대로 있다
        assert [r[0] for r in c.execute(text("SELECT raw_text FROM messages ORDER BY id"))] == ["첫째", "둘째"]
    mine = client.get(f"/conversations/{conv}/messages", headers=auth("parent1")).json()
    assert [m["raw_text"] for m in mine] == ["첫째", "둘째"]  # 학부모는 자기가 쓴 글을 본다


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
