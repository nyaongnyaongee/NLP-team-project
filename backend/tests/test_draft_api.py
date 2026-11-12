"""초안 API — 가짜 Claude 응답으로 (키 없이, 진짜 API 안 부름)"""
import json

import pytest
from sqlalchemy import text

from app.ai import draft as draft_module
from app.ai.client import ClaudeReply
from app.routers import drafts as router_mod
from app.routers import messages as messages_router

pytestmark = pytest.mark.usefixtures("clean_messages")


def reply(parsed=None, *, stop="end_turn"):
    return ClaudeReply(text=json.dumps(parsed, ensure_ascii=False), stop_reason=stop, model="fake", usage={})


@pytest.fixture
def claude(monkeypatch):
    """claude(builder): 초안 함수가 Claude 대신 builder(masked)->ClaudeReply 를 쓴다. 보낸 글은 seen 에 쌓인다."""
    seen: list[str] = []

    def use(builder):
        def call(masked):
            seen.append(masked)
            return builder(masked)

        monkeypatch.setitem(messages_router._refine_state, "enabled", True)
        real_reply, real_notice = draft_module.draft_reply, draft_module.draft_notice
        monkeypatch.setattr(router_mod, "draft_reply", lambda *a: real_reply(*a, call=call))
        monkeypatch.setattr(router_mod, "draft_notice", lambda *a: real_notice(*a, call=call))
        return seen

    return use


def put(engine, conv, sender, status, raw, refined=None):
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, status) "
                       "VALUES (:c, :s, :r, :f, :st)"), {"c": conv, "s": sender, "r": raw, "f": refined, "st": status})


def ask(client, auth, who, conv, memo=None):
    return client.post(f"/conversations/{conv}/draft", json={"memo": memo}, headers=auth(who))


def test_교사는_정제문과_자기_글로_초안을_받는다(client, auth, ids, engine, claude):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 진짜 무능하네 보건실 갔냐고", "보건실에 다녀왔는지 알려 주세요.")
    put(engine, conv, ids["teacher1"], "skip", "확인해 보겠습니다.")
    put(engine, conv, ids["parent1"], "failed", "아직 정제 안 된 원문")
    seen = claude(lambda m: reply({"draft": "안녕하세요. 보건실에 다녀왔습니다. 감사합니다.", "check": []}))

    r = ask(client, auth, "teacher1", conv, memo="보건실 다녀옴")
    assert r.status_code == 200, r.text
    assert r.json() == {"draft": "안녕하세요. 보건실에 다녀왔습니다. 감사합니다.", "check": []}
    sent = seen[0]
    assert "학부모: 보건실에 다녀왔는지 알려 주세요." in sent and "교사: 확인해 보겠습니다." in sent
    assert "무능" not in sent and "아직 정제 안 된" not in sent  # 원문 · 정제 안 된 글은 Claude 에게도 안 간다


def test_통과한_원문과_정제문을_초안_문맥에_넣고_초안은_저장하지_않는다(client, auth, ids, engine, claude):
    conv = ids["conv_parent1"]
    with engine.begin() as c:
        passed = c.execute(text(
            "INSERT INTO messages (conversation_id, sender_id, raw_text, analysis, needs_refinement, status) "
            "VALUES (:c, :s, :r, '{}'::jsonb, false, 'done') RETURNING id"
        ), {"c": conv, "s": ids["parent1"], "r": "체육 시간에 넘어졌어요."}).scalar()
        refined = c.execute(text(
            "INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, analysis, status) "
            "VALUES (:c, :s, :r, :f, '{}'::jsonb, 'done') RETURNING id"
        ), {"c": conv, "s": ids["parent1"], "r": "무능한 교사", "f": "상황을 알려 주세요."}).scalar()
    seen = claude(lambda m: reply({"draft": "확인해 보겠습니다.", "check": []}))

    response = ask(client, auth, "teacher1", conv)
    assert response.status_code == 200
    assert response.json()["draft"] == "확인해 보겠습니다."
    assert "학부모: 체육 시간에 넘어졌어요." in seen[0]
    assert "학부모: 상황을 알려 주세요." in seen[0]
    assert "무능한 교사" not in seen[0]
    with engine.connect() as c:
        rows = c.execute(text("SELECT id, analysis FROM messages WHERE id IN (:p, :r) ORDER BY id"),
                         {"p": passed, "r": refined}).all()
    assert rows == [(passed, {}), (refined, {})]


def test_판정_없이_완료됐으나_정제문이_없으면_초안_문맥에서_제외한다(client, auth, ids, engine, claude):
    put(engine, ids["conv_parent1"], ids["parent1"], "done", "공개하면 안 되는 원문")
    seen = claude(lambda m: reply({"draft": "x", "check": []}))
    teacher = client.get(f"/conversations/{ids['conv_parent1']}/messages", headers=auth("teacher1")).json()[0]
    assert teacher["raw_text"] is None
    assert ask(client, auth, "teacher1", ids["conv_parent1"]).status_code == 409
    assert seen == []


def test_학부모는_초안을_못_만든다(client, auth, ids, engine, claude):
    put(engine, ids["conv_parent1"], ids["parent1"], "done", "원문", "정제문")
    claude(lambda m: reply({"draft": "x", "check": []}))
    assert ask(client, auth, "parent1", ids["conv_parent1"]).status_code == 403


def test_남의_대화는_404(client, auth, ids, claude):
    claude(lambda m: reply({"draft": "x", "check": []}))
    assert ask(client, auth, "parent1", ids["conv_parent2"]).status_code == 404


def test_정제된_학부모_메시지가_없으면_409_이고_Claude_를_안_부른다(client, auth, ids, engine, claude):
    put(engine, ids["conv_parent1"], ids["parent1"], "pending", "원문")
    seen = claude(lambda m: reply({"draft": "x", "check": []}))
    assert ask(client, auth, "teacher1", ids["conv_parent1"]).status_code == 409
    assert seen == []


def test_Claude_가_실패하면_502_와_사유(client, auth, ids, engine, claude):
    put(engine, ids["conv_parent1"], ids["parent1"], "done", "원문", "정제문")
    claude(lambda m: reply({}, stop="refusal"))
    r = ask(client, auth, "teacher1", ids["conv_parent1"])
    assert r.status_code == 502 and "거절" in r.json()["detail"]


def test_스위치가_꺼져_있으면_503_이고_Claude_를_안_부른다(client, auth, ids, engine, claude, monkeypatch):
    put(engine, ids["conv_parent1"], ids["parent1"], "done", "원문", "정제문")
    seen = claude(lambda m: reply({"draft": "x", "check": []}))
    monkeypatch.setitem(messages_router._refine_state, "enabled", False)
    assert ask(client, auth, "teacher1", ids["conv_parent1"]).status_code == 503
    assert client.post("/drafts/notice", json={"points": "내일 현장학습"}, headers=auth("teacher1")).status_code == 503
    assert seen == []


def test_공지_초안은_교사만(client, auth, claude):
    claude(lambda m: reply({"title": "현장학습 안내", "body": "안녕하세요, 학부모님.", "check": []}))
    r = client.post("/drafts/notice", json={"points": "내일 현장학습"}, headers=auth("teacher1"))
    assert r.status_code == 200 and r.json()["title"] == "현장학습 안내"
    assert client.post("/drafts/notice", json={"points": "x"}, headers=auth("parent1")).status_code == 403
    assert client.post("/drafts/notice", json={"points": ""}, headers=auth("teacher1")).status_code == 422
