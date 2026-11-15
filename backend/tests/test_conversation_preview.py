"""대화 목록 한 줄 요약 (preview) — 정제 분석을 다시 쓰고, 원문 정책(_view)을 그대로 따르는지"""
import json

import pytest
from sqlalchemy import text


@pytest.fixture(autouse=True)
def clean(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE messages RESTART IDENTITY"))


def put(engine, conv, sender, status, raw, refined=None, analysis=None, needs=None):
    with engine.begin() as c:
        c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, status, analysis, "
                       "needs_refinement) VALUES (:c, :s, :r, :f, :st, CAST(:a AS JSONB), :n)"),
                  {"c": conv, "s": sender, "r": raw, "f": refined, "st": status,
                   "a": json.dumps(analysis, ensure_ascii=False) if analysis else None, "n": needs})


def preview(client, auth, who, conv):
    return next(c for c in client.get("/conversations", headers=auth(who)).json() if c["id"] == conv)["preview"]


def analysis(topic, *reqs):
    return {"abusive": False, "quotes": ["씨 무능하네"], "topic": topic, "threats": [], "deadline": None,
            "requests": [{"type": "정보 문의", "text": t} for t in reqs]}


def test_교사는_주제_요청_마지막_글을_본다(client, auth, ids, engine):
    conv, p, t = ids["conv_parent1"], ids["parent1"], ids["teacher1"]
    put(engine, conv, p, "done", "씨 무능하네 도시락 싸요?", refined="도시락을 싸야 하나요?",
        analysis=analysis("일정 · 행사 · 공지", "현장학습에 도시락을 싸야 하는지 알려 달라"), needs=True)
    put(engine, conv, p, "done", "네 감사해요", analysis=analysis("감사 · 안부"), needs=False)
    pv = preview(client, auth, "teacher1", conv)
    assert pv["topic"] == "일정 · 행사 · 공지"  # 요청이 있는 글의 주제
    assert pv["requests"] == ["현장학습에 도시락을 싸야 하는지 알려 달라"]
    assert pv["last"] == {"text": "네 감사해요", "mine": False, "status": "done"}  # 통과 글은 원문

    put(engine, conv, t, "skip", "네, 도시락 " + "가" * 80)
    last = preview(client, auth, "teacher1", conv)["last"]
    assert last["mine"] and last["text"].endswith("…") and len(last["text"]) == 61


def test_정제한_글의_원문과_인용은_목록에도_안_나온다(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 무능하네", refined="실망스럽습니다.",
        analysis=analysis("교사 언행"), needs=True)
    pv = preview(client, auth, "teacher1", conv)
    assert pv["last"]["text"] == "실망스럽습니다." and pv["topic"] == "교사 언행"
    assert "무능" not in json.dumps(client.get("/conversations", headers=auth("teacher1")).json(), ensure_ascii=False)


def test_처리_전_실패한_글은_내용_없이_상태만(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "pending", "거친 말")
    assert preview(client, auth, "teacher1", conv) == {
        "last": {"text": None, "mine": False, "status": "pending"}, "summary": None, "topic": None, "requests": []}


def test_학부모도_요약을_보되_마지막_글은_자기_원문(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 무능하네 도시락 싸요?", refined="정제문",
        analysis={**analysis("급식", "알려 달라"), "summary": "도시락 문의"}, needs=True)
    pv = preview(client, auth, "parent1", conv)
    assert pv == {"last": {"text": "씨 무능하네 도시락 싸요?", "mine": True, "status": "done"},
                  "summary": "도시락 문의", "topic": "급식", "requests": []}
    assert "정제문" not in json.dumps(client.get("/conversations", headers=auth("parent1")).json(), ensure_ascii=False)


def test_메시지가_없으면_비어_있다(client, auth, ids):
    assert preview(client, auth, "teacher1", ids["conv_parent2"]) == {"last": None, "summary": None, "topic": None, "requests": []}


def test_요약이_있으면_첫_학부모_글의_요약을_쓴다(client, auth, ids, engine):
    conv, p = ids["conv_parent1"], ids["parent1"]
    put(engine, conv, p, "done", "도시락 싸요?", analysis={**analysis("일정 · 행사 · 공지", "알려 달라"),
                                                       "summary": "현장학습 도시락 필요 여부 문의"}, needs=False)
    put(engine, conv, p, "done", "하나 더요", analysis={**analysis("급식", "바꿔 달라"), "summary": "급식 문의"},
        needs=False)
    pv = preview(client, auth, "teacher1", conv)
    assert (pv["summary"], pv["topic"], pv["requests"]) == ("현장학습 도시락 필요 여부 문의", "일정 · 행사 · 공지", [])
    assert preview(client, auth, "parent1", conv)["summary"] == "현장학습 도시락 필요 여부 문의"
