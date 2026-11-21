"""자주 묻는 질문(Q&A) API + Q&A 초안 — 가짜 Claude 응답으로 (키 없이, 진짜 API 안 부름)"""
import json

import pytest
from sqlalchemy import text

from app.ai import draft as draft_module
from app.ai.client import ClaudeReply
from app.routers import faqs as faqs_router
from app.routers import messages as messages_router

pytestmark = pytest.mark.usefixtures("clean_messages")


@pytest.fixture(autouse=True)
def clean_faqs(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE faqs RESTART IDENTITY"))


@pytest.fixture
def sent_to(monkeypatch):
    calls = []
    monkeypatch.setattr(faqs_router.hub, "notify_users", lambda uids, data: calls.append((sorted(uids), data)))
    return calls


@pytest.fixture
def claude(monkeypatch):
    """claude(builder): Q&A 초안이 Claude 대신 builder(masked)->ClaudeReply 를 쓴다. 보낸 글은 seen 에 쌓인다."""
    seen: list[str] = []

    def use(builder):
        def call(masked):
            seen.append(masked)
            return builder(masked)

        monkeypatch.setitem(messages_router._refine_state, "enabled", True)
        real = draft_module.draft_faq
        monkeypatch.setattr(faqs_router, "draft_faq", lambda *a: real(*a, call=call))
        return seen

    return use


def reply(parsed):
    return ClaudeReply(text=json.dumps(parsed, ensure_ascii=False), stop_reason="end_turn", model="fake", usage={})


def make(client, auth, q="체험학습 신청서는 언제까지 내나요?", a="가기 3일 전까지 내 주세요."):
    r = client.post("/faqs", json={"question": q, "answer": a}, headers=auth("teacher1"))
    assert r.status_code == 201, r.text
    return r.json()


def test_등록하면_반_학부모에게_바로_보이고_알림이_간다(client, auth, ids, sent_to):
    f = make(client, auth, q="  체험학습 신청서는 언제까지 내나요?  ")
    assert f["question"] == "체험학습 신청서는 언제까지 내나요?"
    for who in ("teacher1", "parent1", "parent2"):
        got = client.get("/faqs", headers=auth(who)).json()
        assert [(x["question"], x["answer"]) for x in got] == [("체험학습 신청서는 언제까지 내나요?", "가기 3일 전까지 내 주세요.")]
    everyone = sorted([ids["parent1"], ids["parent2"], ids["teacher1"]])
    assert sent_to == [(everyone, {"type": "faq"})]


def test_고치기_지우기는_교사만(client, auth, sent_to):
    f = make(client, auth)
    assert client.patch(f"/faqs/{f['id']}", json={"answer": "x"}, headers=auth("parent1")).status_code == 403
    assert client.delete(f"/faqs/{f['id']}", headers=auth("parent1")).status_code == 403
    assert client.post("/faqs", json={"question": "q", "answer": "a"}, headers=auth("parent1")).status_code == 403
    r = client.patch(f"/faqs/{f['id']}", json={"answer": " 5일 전까지 내 주세요. "}, headers=auth("teacher1"))
    assert r.status_code == 200 and r.json()["answer"] == "5일 전까지 내 주세요."
    assert r.json()["question"] == f["question"]
    assert client.patch(f"/faqs/{f['id']}", json={"answer": "   "}, headers=auth("teacher1")).status_code == 422
    assert client.delete(f"/faqs/{f['id']}", headers=auth("teacher1")).status_code == 204
    assert client.get("/faqs", headers=auth("parent1")).json() == []
    assert client.delete(f"/faqs/{f['id']}", headers=auth("teacher1")).status_code == 404


def test_민원대응팀은_볼_수_없다(client, auth):
    make(client, auth)
    assert client.get("/faqs", headers=auth("team1")).status_code == 403


def test_대화창_초안은_대화와_메모를_가려서_보내고_원래_이름으로_돌려준다(client, auth, ids, engine, claude):
    conv = ids["conv_parent1"]  # 시험 DB 의 대화 학생 이름은 「학생」이라, check 에 「학생」을 쓰면 지어낸 이름으로 걸린다
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, status) VALUES (:c, :t, :r, 'skip')"),
                  {"c": conv, "t": ids["teacher1"], "r": "신청서는 가기 3일 전까지 내 주시면 됩니다."})

    def build(sent):
        return reply({"question": "교외체험학습 신청서는 언제까지 내야 하나요?",
                      "answer": "체험학습 가기 3일 전까지 내 주세요.", "check": ["개인 사정을 뺐습니다"]})

    seen = claude(build)
    r = client.post("/drafts/faq", json={"memo": "체험학습 신청 기한 김민지", "conversation_id": conv},
                    headers=auth("teacher1"))
    assert r.status_code == 200, r.text
    assert r.json() == {"question": "교외체험학습 신청서는 언제까지 내야 하나요?",
                        "answer": "체험학습 가기 3일 전까지 내 주세요.", "check": ["개인 사정을 뺐습니다"]}
    sent = seen[0]
    assert sent.startswith("[대화]\n교사: 신청서는 가기 3일 전까지") and "[담임 메모]\n체험학습 신청 기한 " in sent
    assert "김민지" not in sent  # 교사 이름도 가린다
    assert client.get("/faqs", headers=auth("teacher1")).json() == []  # 초안은 저장하지 않는다


def test_초안에_학생_이름이_남으면_확인할_것에_알린다(client, auth, claude):
    def build(sent):
        fake = sent.split("[담임 메모]\n")[1].split("이가")[0]  # 메모의 지민 → 가짜 이름
        return reply({"question": f"{fake}이가 결석하면 어떻게 하나요?", "answer": "담임에게 알려 주세요.", "check": []})

    claude(build)
    r = client.post("/drafts/faq", json={"memo": "지민이가 결석하면 연락 주기"}, headers=auth("teacher1"))
    assert r.status_code == 200, r.text
    assert r.json()["question"] == "지민이가 결석하면 어떻게 하나요?"
    assert r.json()["check"] == ["Q&A 에 학생 이름(지민)이 들어 있습니다. 빼고 등록하세요"]


def test_초안은_교사만_남의_대화는_안_됨(client, auth, ids, claude):
    claude(lambda s: reply({"question": "q", "answer": "a", "check": []}))
    assert client.post("/drafts/faq", json={"memo": "m"}, headers=auth("parent1")).status_code == 403
    assert client.post("/drafts/faq", json={"memo": "m", "conversation_id": 99999},
                       headers=auth("teacher1")).status_code == 404


def test_Claude_가_꺼져_있으면_503(client, auth, monkeypatch):
    monkeypatch.setitem(messages_router._refine_state, "enabled", False)
    assert client.post("/drafts/faq", json={"memo": "m"}, headers=auth("teacher1")).status_code == 503


def test_대화창에서는_메모_없이_대화를_보고_만든다(client, auth, ids, engine, claude):
    conv = ids["conv_parent1"]
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, status, needs_refinement) "
                       "VALUES (:c, :p, :r, 'done', false)"),
                  {"c": conv, "p": ids["parent1"], "r": "체험학습 신청서는 언제까지 내면 되나요?"})
    seen = claude(lambda s: reply({"question": "체험학습 신청서는 언제까지 내나요?", "answer": "[ ]까지 내 주세요.",
                                   "check": ["담임 답이 아직 없어 [ ]로 비웠습니다"]}))
    r = client.post("/drafts/faq", json={"conversation_id": conv}, headers=auth("teacher1"))
    assert r.status_code == 200, r.text
    assert seen[0].startswith("[대화]\n학부모: 체험학습 신청서는") and seen[0].endswith("[담임 메모]\n(없음)")


def test_메모도_학부모_질문도_없으면_만들지_않는다(client, auth, ids, claude):
    seen = claude(lambda s: reply({"question": "q", "answer": "a", "check": []}))
    assert client.post("/drafts/faq", json={}, headers=auth("teacher1")).status_code == 422
    r = client.post("/drafts/faq", json={"conversation_id": ids["conv_parent1"]}, headers=auth("teacher1"))
    assert r.status_code == 409 and seen == []  # 빈 대화: Claude 를 부르지 않는다
