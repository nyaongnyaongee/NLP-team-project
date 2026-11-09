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


# ---------------------------------------------------------------- 자동 답장 추천 (정제 바로 뒤 백그라운드)

REAL_AUTO = router_mod.auto_draft  # conftest 가 autouse 로 끄기 전의 진짜 함수


def last_id(engine):
    with engine.begin() as c:
        return c.execute(text("SELECT max(id) FROM messages")).scalar()


def put_done(engine, conv, sender, refined):
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, analysis, status) "
                       "VALUES (:c, :s, '원문', :f, CAST(:a AS JSONB), 'done')"),
                  {"c": conv, "s": sender, "f": refined, "a": json.dumps({"topic": "건강 · 안전", "quotes": ["원문"]})})
    return last_id(engine)


def analysis_for(client, auth, who, conv, msg_id):
    msgs = client.get(f"/conversations/{conv}/messages", headers=auth(who)).json()
    return next(m for m in msgs if m["id"] == msg_id)["analysis"]


def test_정제된_학부모_글에_답장_추천이_붙고_교사만_본다(client, auth, ids, engine, claude):
    conv = ids["conv_parent1"]
    msg = put_done(engine, conv, ids["parent1"], "보건실에 다녀왔는지 알려 주세요.")
    seen = claude(lambda m: reply({"draft": "안녕하세요. [ ] 감사합니다.", "check": ["[ ] 자리를 채우세요"]}))

    REAL_AUTO(msg, conv)
    assert seen[0].endswith("[담임 메모]\n(없음)")  # 자동 추천은 메모 없이
    a = analysis_for(client, auth, "teacher1", conv, msg)
    assert a["reply_draft"] == {"draft": "안녕하세요. [ ] 감사합니다.", "check": ["[ ] 자리를 채우세요"]}
    assert a["topic"] == "건강 · 안전" and "quotes" not in a  # 기존 분석은 그대로, 인용은 여전히 안 나감
    assert analysis_for(client, auth, "parent1", conv, msg) is None


def test_추천이_실패하면_사유만_붙는다(client, auth, ids, engine, claude):
    msg = put_done(engine, ids["conv_parent1"], ids["parent1"], "정제문")
    claude(lambda m: reply({}, stop="refusal"))
    REAL_AUTO(msg, ids["conv_parent1"])
    assert "거절" in analysis_for(client, auth, "teacher1", ids["conv_parent1"], msg)["reply_draft"]["error"]


def test_교사가_이미_답했으면_추천을_만들지_않는다(client, auth, ids, engine, claude):
    msg = put_done(engine, ids["conv_parent1"], ids["parent1"], "정제문")
    put(engine, ids["conv_parent1"], ids["teacher1"], "skip", "답했습니다")
    seen = claude(lambda m: reply({"draft": "x", "check": []}))
    REAL_AUTO(msg, ids["conv_parent1"])
    assert seen == []
    assert "reply_draft" not in analysis_for(client, auth, "teacher1", ids["conv_parent1"], msg)


def test_정제가_끝나면_자동_추천을_부른다(client, auth, ids, monkeypatch):
    from app.routers import messages as mr

    called = []
    monkeypatch.setattr(router_mod, "auto_draft", lambda msg_id, conv_id: called.append(msg_id))
    monkeypatch.setattr(mr, "_refine_in_background", REAL_REFINE_BG)
    monkeypatch.setattr(mr, "refine_message", lambda *a: {"status": "done", "refined_text": "정제문",
                                                         "analysis": {"topic": "기타"}, "error": None})
    monkeypatch.setitem(mr._refine_state, "enabled", True)
    r = client.post(f"/conversations/{ids['conv_parent1']}/messages", json={"text": "원문"}, headers=auth("parent1"))
    assert called == [r.json()["id"]]

    monkeypatch.setattr(mr, "refine_message", lambda *a: {"status": "failed", "refined_text": None,
                                                         "analysis": None, "error": "실패"})
    client.post(f"/conversations/{ids['conv_parent1']}/messages", json={"text": "원문"}, headers=auth("parent1"))
    assert len(called) == 1  # 정제가 실패하면 추천도 안 만든다


REAL_REFINE_BG = messages_router._refine_in_background
