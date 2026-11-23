"""민원 이관: 다중 대화 증거 고정, 원문 권한, 상태, 담당자 양방향 채팅."""
import pytest
from sqlalchemy import text

from app.routers import complaints as complaints_router
from app.routers import messages as messages_router

REAL_CASE_BG = complaints_router._report_in_background


@pytest.fixture(autouse=True)
def clean(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("DELETE FROM complaint_cases"))
        c.execute(text("TRUNCATE messages RESTART IDENTITY"))
        c.execute(text("DELETE FROM conversations WHERE id NOT IN (:a, :b)"),
                  {"a": ids["conv_parent1"], "b": ids["conv_parent2"]})


def put(engine, conv_id, sender_id, raw, *, refined=None, status="done", needs_refinement=None):
    with engine.begin() as c:
        return c.execute(text(
            "INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, status, needs_refinement) "
            "VALUES (:conv, :sender, :raw, :refined, :status, :needs) RETURNING id"),
            {"conv": conv_id, "sender": sender_id, "raw": raw, "refined": refined,
             "status": status, "needs": needs_refinement}).scalar_one()


@pytest.fixture
def second_team(engine):
    from app.core.auth import hash_password

    with engine.begin() as c:
        user_id = c.execute(text(
            "INSERT INTO users (role, name, login_id, password_hash) "
            "VALUES ('complaint_team', '두 번째 담당자', 'team2', :hash) RETURNING id"),
            {"hash": hash_password("pw1234")}).scalar_one()
    yield user_id
    with engine.begin() as c:
        c.execute(text("DELETE FROM complaint_case_chat_reads WHERE user_id = :id"), {"id": user_id})
        c.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})


def submit(client, auth, ids, conversation_ids=None, reason="여러 차례 무리한 요구가 이어져 업무가 어렵습니다."):
    return client.post("/complaints", headers=auth("teacher1"), json={
        "conversation_ids": conversation_ids or [ids["conv_parent1"]], "reason": reason})


def test_여러_대화의_신청서_증거는_제출_시점에_고정되고_교사는_원문을_못_본다(client, auth, ids, engine):
    first = ids["conv_parent1"]
    with engine.begin() as c:
        second = c.execute(text(
            "INSERT INTO conversations (teacher_id, parent_id, student_name) "
            "VALUES (:t, :p, '다른 문의') RETURNING id"),
            {"t": ids["teacher1"], "p": ids["parent1"]}).scalar_one()
    raw = "씨발 지금 당장 처리해요"
    m1 = put(engine, first, ids["parent1"], raw, refined="빠른 처리를 부탁드립니다.", needs_refinement=True)
    put(engine, second, ids["parent1"], "매일 교실 앞자리를 주세요", needs_refinement=False)
    r = submit(client, auth, ids, [first, second])
    assert r.status_code == 202, r.text
    case = r.json()
    assert case["status"] == "received" and case["report_status"] == "pending"
    assert case["conversation_ids"] == [first, second]
    case_id = case["id"]
    put(engine, first, ids["parent1"], "신청 뒤에 보낸 새 글", needs_refinement=False)

    teacher = client.get(f"/complaints/{case_id}", headers=auth("teacher1")).json()
    assert teacher["status"] == "received" and teacher["report"] is None
    assert teacher["conversations"][0]["messages"][0]["text"] == "빠른 처리를 부탁드립니다."
    assert teacher["conversations"][0]["messages"][0]["raw_text"] is None
    assert raw not in str(teacher) and "신청 뒤에 보낸 새 글" not in str(teacher)
    assert teacher["conversations"][1]["messages"][0]["text"] == "매일 교실 앞자리를 주세요"

    team = client.get(f"/complaints/{case_id}", headers=auth("team1")).json()
    assert team["status"] == "in_progress" and team["started_at"]
    assert team["conversations"][0]["messages"][0]["id"] == m1
    assert team["conversations"][0]["messages"][0]["raw_text"] == raw
    assert "신청 뒤에 보낸 새 글" not in str(team)
    assert client.get("/complaints", headers=auth("teacher1")).json()[0]["status"] == "in_progress"
    assert client.get("/complaints", headers=auth("parent1")).status_code == 403
    assert client.get(f"/complaints/{case_id}", headers=auth("parent1")).status_code == 404


def test_선택_대화와_사유_검증(client, auth, ids, engine):
    first, other_parent = ids["conv_parent1"], ids["conv_parent2"]
    put(engine, first, ids["parent1"], "상담을 요청합니다", needs_refinement=False)
    assert submit(client, auth, ids, [first, other_parent]).status_code == 400
    assert submit(client, auth, ids, [first, first]).status_code == 400
    assert submit(client, auth, ids, [first], reason="   ").status_code == 400
    assert submit(client, auth, ids, [999999]).status_code == 404
    assert client.post("/complaints", headers=auth("parent1"), json={
        "conversation_ids": [first], "reason": "사유"}).status_code == 403
    with engine.begin() as c:
        c.execute(text("DELETE FROM messages"))
    assert submit(client, auth, ids, [first]).status_code == 400


def test_보고서_분석_한계를_넘는_신청서는_미리_거절한다(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO messages (conversation_id, sender_id, raw_text, status) "
            "SELECT :conv, :parent, '반복 요구', 'done' FROM generate_series(1, 81)"),
            {"conv": conv, "parent": ids["parent1"]})
    assert submit(client, auth, ids).status_code == 400
    with engine.begin() as c:
        c.execute(text("DELETE FROM messages"))
    put(engine, conv, ids["parent1"], "가" * 30_000, needs_refinement=False)
    assert submit(client, auth, ids).status_code == 400


def test_AI_보고서는_고정된_원문과_교사_사유로_만들고_담당자만_본다(
        client, auth, ids, engine, monkeypatch):
    from app.ai import case_report

    conv = ids["conv_parent1"]
    raw = "왜 아직도 안 해요? 지금 당장 자리를 바꿔요."
    message_id = put(engine, conv, ids["parent1"], raw, refined="자리 변경을 요청합니다.", needs_refinement=True)
    captured = {}

    def fake(history, reason, roster, adults):
        captured["history"] = history
        captured["reason"] = reason
        return {"status": "done", "error": None, "report": {
            "summary": "반복 요청이 확인됩니다.", "parent_messages": 1, "rude_messages": 1,
            "repeated_demands_count": 0, "repeated_demands": [],
            "reason_evidence": [{"conversation_id": conv, "message_id": message_id,
                                 "at": history[0]["at"].isoformat(), "quote": "지금 당장 자리를 바꿔요.",
                                 "explanation": "시한을 붙인 자리 변경 요구"}],
            "rude_evidence": []}}

    monkeypatch.setitem(messages_router._refine_state, "enabled", True)
    monkeypatch.setattr(case_report, "write_case_report", fake)
    monkeypatch.setattr(complaints_router, "_report_in_background", REAL_CASE_BG)
    created = submit(client, auth, ids)
    assert created.status_code == 202, created.text
    case_id = created.json()["id"]
    assert captured["history"][0]["text"] == raw
    assert captured["history"][0]["conversation_id"] == conv
    assert captured["reason"] == "여러 차례 무리한 요구가 이어져 업무가 어렵습니다."
    assert client.get(f"/complaints/{case_id}", headers=auth("teacher1")).json()["report"] is None
    team = client.get(f"/complaints/{case_id}", headers=auth("team1")).json()
    assert team["report_status"] == "done" and team["report"]["reason_evidence"][0]["quote"] in raw


def test_학부모와_교사_채팅은_역할별로_분리되고_완료되면_읽기만_가능하다(client, auth, ids, engine):
    put(engine, ids["conv_parent1"], ids["parent1"], "반복 요청입니다", needs_refinement=False)
    case_id = submit(client, auth, ids).json()["id"]
    assert client.get("/complaints/chats/parent", headers=auth("parent1")).json() == []
    assert client.post(f"/complaints/{case_id}/complete", headers=auth("team1")).status_code == 409
    client.get(f"/complaints/{case_id}", headers=auth("team1"))  # 열람 = 진행 중
    assert len(client.get("/complaints/chats/parent", headers=auth("team1")).json()) == 1
    assert len(client.get("/complaints/chats/teacher", headers=auth("teacher1")).json()) == 1
    assert client.get("/complaints/chats/parent", headers=auth("teacher1")).status_code == 403
    parent_path = f"/complaints/{case_id}/chats/parent/messages"
    teacher_path = f"/complaints/{case_id}/chats/teacher/messages"
    assert client.get(parent_path, headers=auth("parent1")).status_code == 404
    first = client.post(parent_path, headers=auth("team1"), json={"text": "안녕하세요. 상담을 도와드리겠습니다."})
    assert first.status_code == 201, first.text
    assert first.json()["author_role"] == "complaint_team"
    parent_chats = client.get("/complaints/chats/parent", headers=auth("parent1")).json()
    assert parent_chats == [{"case_id": case_id, "channel": "parent", "status": "in_progress",
                             "counterpart_name": "민원 담당자", "last_message_at": first.json()["created_at"],
                             "last_message_text": "안녕하세요. 상담을 도와드리겠습니다.", "unread_count": 1}]
    assert "reason" not in str(parent_chats) and "report" not in str(parent_chats)
    reply = client.post(parent_path, headers=auth("parent1"), json={"text": "네, 확인했습니다."})
    assert reply.status_code == 201
    assert [m["text"] for m in client.get(parent_path, headers=auth("parent1")).json()] == [
        "안녕하세요. 상담을 도와드리겠습니다.", "네, 확인했습니다."]
    assert client.get(parent_path, headers=auth("parent2")).status_code == 404
    assert client.get(parent_path, headers=auth("teacher1")).status_code == 404
    assert client.post(teacher_path, headers=auth("teacher1"), json={"text": "  "}).status_code == 400
    assert client.post(teacher_path, headers=auth("teacher1"), json={"text": "교사 측 설명입니다."}).status_code == 201
    assert client.get(teacher_path, headers=auth("parent1")).status_code == 404
    done = client.post(f"/complaints/{case_id}/complete", headers=auth("team1"))
    assert done.status_code == 200 and done.json()["status"] == "completed"
    assert client.get("/complaints/chats/parent", headers=auth("parent1")).json()[0]["status"] == "completed"
    assert client.get("/complaints/chats/teacher", headers=auth("team1")).json()[0]["status"] == "completed"
    assert client.post(parent_path, headers=auth("team1"), json={"text": "완료 후 글"}).status_code == 409
    assert client.post(teacher_path, headers=auth("teacher1"), json={"text": "완료 후 글"}).status_code == 409


def test_담당자_채팅_읽지_않은_상대_메시지는_채널별_사용자별로_센다(client, auth, ids, engine, second_team):
    put(engine, ids["conv_parent1"], ids["parent1"], "이관할 문의", needs_refinement=False)
    case_id = submit(client, auth, ids).json()["id"]
    client.get(f"/complaints/{case_id}", headers=auth("team1"))
    parent_path = f"/complaints/{case_id}/chats/parent"
    teacher_path = f"/complaints/{case_id}/chats/teacher"

    team_message = client.post(parent_path + "/messages", headers=auth("team1"),
                               json={"text": "학부모님께 연락드립니다"}).json()
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 0
    assert client.get("/complaints/chats/parent", headers=auth("parent1")).json()[0]["unread_count"] == 1

    first_parent = client.post(parent_path + "/messages", headers=auth("parent1"),
                               json={"text": "첫 답장"}).json()
    second_parent = client.post(parent_path + "/messages", headers=auth("parent1"),
                                json={"text": "두 번째 답장"}).json()
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 2
    assert client.get("/complaints/chats/parent", headers=auth("team2")).json()[0]["unread_count"] == 2
    assert client.get("/complaints/chats/teacher", headers=auth("team1")).json()[0]["unread_count"] == 0
    assert client.get("/complaints/chats/parent", headers=auth("parent1")).json()[0]["unread_count"] == 1
    assert len(client.get(parent_path + "/messages", headers=auth("team1")).json()) == 3
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 2

    read = parent_path + "/read"
    assert client.post(read, headers=auth("team1"), json={"message_id": first_parent["id"]}).status_code == 204
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 1
    # 오래된 읽음 요청이 늦게 와도 커서는 뒤로 가지 않는다.
    assert client.post(read, headers=auth("team1"), json={"message_id": team_message["id"]}).status_code == 204
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 1
    assert client.post(read, headers=auth("team1"), json={"message_id": second_parent["id"]}).status_code == 204
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 0
    assert client.get("/complaints/chats/parent", headers=auth("team2")).json()[0]["unread_count"] == 2

    assert client.post(read, headers=auth("parent1"), json={"message_id": team_message["id"]}).status_code == 204
    assert client.get("/complaints/chats/parent", headers=auth("parent1")).json()[0]["unread_count"] == 0
    assert client.post(read, headers=auth("parent2"), json={"message_id": team_message["id"]}).status_code == 404
    assert client.post(read, headers=auth("teacher1"), json={"message_id": team_message["id"]}).status_code == 404
    assert client.post(read, headers=auth("team1"), json={"message_id": 999999}).status_code == 400

    teacher_message = client.post(teacher_path + "/messages", headers=auth("teacher1"),
                                  json={"text": "교사의 설명"}).json()
    assert client.get("/complaints/chats/teacher", headers=auth("team1")).json()[0]["unread_count"] == 1
    assert client.get("/complaints/chats/teacher", headers=auth("teacher1")).json()[0]["unread_count"] == 0
    assert client.post(read, headers=auth("team1"), json={"message_id": teacher_message["id"]}).status_code == 400
    assert client.post(teacher_path + "/read", headers=auth("team1"),
                       json={"message_id": teacher_message["id"]}).status_code == 204
    assert client.get("/complaints/chats/teacher", headers=auth("team1")).json()[0]["unread_count"] == 0

    final_parent = client.post(parent_path + "/messages", headers=auth("parent1"),
                               json={"text": "처리 전 마지막 메시지"}).json()
    assert client.post(f"/complaints/{case_id}/complete", headers=auth("team1")).status_code == 200
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 1
    assert client.post(read, headers=auth("team1"), json={"message_id": final_parent["id"]}).status_code == 204
    assert client.get("/complaints/chats/parent", headers=auth("team1")).json()[0]["unread_count"] == 0


def test_실패한_AI_보고서는_담당자만_다시_요청할_수_있다(client, auth, ids, engine):
    put(engine, ids["conv_parent1"], ids["parent1"], "반복 요구", needs_refinement=False)
    case_id = submit(client, auth, ids).json()["id"]
    endpoint = f"/complaints/{case_id}/report/retry"
    assert client.post(endpoint, headers=auth("team1")).status_code == 409  # 아직 생성 중
    assert client.post(endpoint, headers=auth("teacher1")).status_code == 403
    with engine.begin() as c:
        c.execute(text("UPDATE complaint_cases SET report_status = 'failed', report_error = 'AI 오류' WHERE id = :id"),
                  {"id": case_id})
    assert client.get(f"/complaints/{case_id}", headers=auth("teacher1")).json()["report_error"] is None
    assert client.get(f"/complaints/{case_id}", headers=auth("team1")).json()["report_error"] == "AI 오류"
    retried = client.post(endpoint, headers=auth("team1"))
    assert retried.status_code == 202 and retried.json()["report_status"] == "pending"
    assert client.post(endpoint, headers=auth("team1")).status_code == 409
    with engine.begin() as c:
        c.execute(text("UPDATE complaint_cases SET report_requested_at = now() - interval '11 minutes' WHERE id = :id"),
                  {"id": case_id})
    assert client.post(endpoint, headers=auth("team1")).status_code == 202  # 서버 중단 후 고착된 pending
