"""학생 명단 · 학생 메모장 · 가명처리 명단 출처 — 키 없이"""
import pytest
from sqlalchemy import text

from app.ai.roster import class_roster, load_sample_roster
from app.routers import messages as messages_router

REAL_REFINE_BG = messages_router._refine_in_background  # conftest 가 테스트마다 막기 전에 잡아 둔다


def test_반이_비면_시연용_명단_대화_학생은_꼭_넣는다():
    assert class_roster([]) == load_sample_roster()
    assert class_roster(["서윤", "민재"], "도하") == ["서윤", "민재", "도하"]
    assert class_roster(["서윤"], "서윤") == ["서윤"] and class_roster(["서윤"], " ") == ["서윤"]


@pytest.fixture
def klass(engine, ids):
    """teacher1 반 3명 + 다른 교사 teacher2 반 1명"""
    from app.core.auth import hash_password

    with engine.begin() as c:
        t2 = c.execute(text("INSERT INTO users (role,name,login_id,password_hash) VALUES "
                            "('teacher','최유진','teacher2',:p) RETURNING id"), {"p": hash_password("pw1234")}).scalar()
        out = {"teacher2": t2}
        for t, name in [(ids["teacher1"], "서윤"), (ids["teacher1"], "민재"), (ids["teacher1"], "학생"), (t2, "하린")]:
            out[name] = c.execute(text("INSERT INTO students (teacher_id, name) VALUES (:t, :n) RETURNING id"),
                                  {"t": t, "n": name}).scalar()
    yield out
    with engine.begin() as c:
        c.execute(text("TRUNCATE messages, tasks RESTART IDENTITY"))
        c.execute(text("UPDATE conversations SET student_id = NULL"))
        c.execute(text("DELETE FROM conversations WHERE id NOT IN (:a, :b)"),
                  {"a": ids["conv_parent1"], "b": ids["conv_parent2"]})
        c.execute(text("DELETE FROM student_memos"))  # TRUNCATE … CASCADE 는 대화까지 지운다
        c.execute(text("DELETE FROM students"))
        c.execute(text("DELETE FROM users WHERE login_id = 'teacher2'"))


def test_메모장은_학생마다_하나_통째로_저장된다(client, auth, klass):
    h = auth("teacher1")
    assert [(s["name"], s["has_memo"]) for s in client.get("/students", headers=h).json()] == [
        ("민재", False), ("서윤", False), ("학생", False)]   # 이름 순, 다른 교사 반 학생은 없음

    sid = klass["서윤"]
    assert client.get(f"/students/{sid}/memo", headers=h).json() == {"student_id": sid, "body": "", "updated_at": None}
    pad = "큰 소리에 놀람 — 활동 전에 미리 알려 주면 괜찮음\n땅콩 알레르기\n\n짝: 민재랑 잘 맞음"
    r = client.put(f"/students/{sid}/memo", headers=h, json={"body": pad + "\n\n"})
    assert r.status_code == 200 and r.json()["body"] == pad and r.json()["updated_at"]   # 끝 빈 줄만 정리, 줄바꿈은 그대로
    assert client.get(f"/students/{sid}/memo", headers=h).json()["body"] == pad
    assert client.get("/students", headers=h).json()[1]["has_memo"] is True

    client.put(f"/students/{sid}/memo", headers=h, json={"body": "땅콩 알레르기"})          # 덮어쓰기 (따로 쌓이지 않음)
    assert client.get(f"/students/{sid}/memo", headers=h).json()["body"] == "땅콩 알레르기"
    client.put(f"/students/{sid}/memo", headers=h, json={"body": ""})                      # 다 지우면 빈 메모장
    assert client.get(f"/students/{sid}/memo", headers=h).json()["body"] == ""
    assert client.get("/students", headers=h).json()[1]["has_memo"] is False


def test_다른_교사_학부모_민원대응팀은_못_본다(client, auth, klass):
    sid = klass["서윤"]
    client.put(f"/students/{sid}/memo", headers=auth("teacher1"), json={"body": "비밀"})
    r = client.post("/auth/login", json={"login_id": "teacher2", "password": "pw1234"})
    other = {"Authorization": "Bearer " + r.json()["token"]}
    assert client.get(f"/students/{sid}/memo", headers=other).status_code == 404
    assert client.put(f"/students/{sid}/memo", headers=other, json={"body": "x"}).status_code == 404
    assert [s["name"] for s in client.get("/students", headers=other).json()] == ["하린"]
    for who in ("parent1", "team1"):
        assert client.get("/students", headers=auth(who)).status_code == 403
        assert client.get(f"/students/{sid}/memo", headers=auth(who)).status_code == 403
    assert client.get(f"/students/{sid}/memo", headers=auth("teacher1")).json()["body"] == "비밀"


def test_대화를_만들면_반_학생과_이어진다(client, auth, ids, klass):
    h = auth("teacher1")
    c1 = client.post("/conversations", headers=h, json={"parent_id": ids["parent1"], "student_name": "민재"}).json()
    c2 = client.post("/conversations", headers=h, json={"parent_id": ids["parent2"], "student_name": "명단밖"}).json()
    assert c1["student_id"] == klass["민재"] and c2["student_id"] is None


def test_정제는_그_교사_반_명단으로_가린다(ids, engine, klass, monkeypatch):
    """반 명단(teacher1 의 3명)을 넘긴다. 시연용 JSON 20명은 안 씀"""
    seen = {}

    def fake(raw, roster, adults):
        seen["roster"] = roster
        return {"status": "failed", "refined_text": None, "analysis": None, "error": "시험"}

    monkeypatch.setitem(messages_router._refine_state, "enabled", True)
    monkeypatch.setattr(messages_router, "refine_message", fake)
    with engine.begin() as c:
        mid = c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, status) "
                             "VALUES (:c, :s, '민재가요', 'pending') RETURNING id"),
                        {"c": ids["conv_parent1"], "s": ids["parent1"]}).scalar()
    REAL_REFINE_BG(mid, "민재가요", ids["conv_parent1"])
    assert sorted(seen["roster"]) == ["민재", "서윤", "학생"]
