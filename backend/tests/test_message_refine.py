"""send_message 에 붙은 정제 — 가짜 Claude 응답으로 (키 없이, 진짜 API 안 부름)"""
import json

import pytest
from sqlalchemy import text

from app.ai import refine as refine_module
from app.ai.client import ClaudeReply
from app.routers import messages as router_mod

pytestmark = pytest.mark.usefixtures("clean_messages")

# autouse 로 꺼지기 전의 진짜 백그라운드 함수 (파일을 불러올 때 잡아 둠)
REAL_BACKGROUND = router_mod._refine_in_background

RAW = "지민이 물통을 누가 또 숨겼대요. 담임 김민지 선생님 무능하네요. 내일까지 새로 사 주세요."


def reply(parsed=None, *, text=None, stop="end_turn"):
    return ClaudeReply(text=text if text is not None else json.dumps(parsed, ensure_ascii=False),
                       stop_reason=stop, model="fake", usage={"input": 1, "output": 1})


def good(masked: str) -> dict:
    first = masked.split(".")[0] + "."
    return {
        "abusive": True,
        "quotes": ["담임 " + masked.split("담임 ")[1].split(".")[0] + "."],
        "topic": "친구 관계 · 학교폭력",
        "requests": [{"type": "배상", "text": "새 물통을 사 달라"}],
        "threats": [],
        "deadline": "내일까지",
        "refined": first + " 같은 일이 되풀이되어 걱정됩니다.",
    }


@pytest.fixture
def refine_with(monkeypatch):
    """refine_with(builder): 학부모 메시지 정제를 켜고, Claude 대신 builder(masked)->ClaudeReply 를 쓴다.
    builder 가 받은 가린 글은 seen 리스트에 쌓인다."""
    seen: list[str] = []

    def use(builder):
        def call(masked):
            seen.append(masked)
            return builder(masked)

        real = refine_module.refine_message
        monkeypatch.setitem(router_mod._refine_state, "enabled", True)  # 다른 시험이 끈 채로 남겨도 켠 상태에서 시작
        monkeypatch.setattr(router_mod, "_refine_in_background", REAL_BACKGROUND)
        monkeypatch.setattr(router_mod, "refine_message", lambda raw, roster, adults: real(raw, roster, adults, call=call))
        return seen

    return use


def send(client, auth, who, conv, text):
    return client.post(f"/conversations/{conv}/messages", json={"text": text}, headers=auth(who))


def read(client, auth, who, conv):
    return client.get(f"/conversations/{conv}/messages", headers=auth(who)).json()


def test_학부모가_보내면_응답은_pending_이고_곧_정제문이_저장된다(client, auth, ids, refine_with):
    seen = refine_with(lambda m: reply(good(m)))
    r = send(client, auth, "parent1", ids["conv_parent1"], RAW)
    assert r.status_code == 201 and r.json()["status"] == "pending"  # 응답은 정제를 기다리지 않는다

    msg = read(client, auth, "teacher1", ids["conv_parent1"])[0]  # 교사가 조회
    assert msg["status"] == "done"
    assert msg["raw_text"] is None  # 원문은 교사에게 안 간다
    assert msg["refined_text"].startswith("지민이 물통을")  # 정제문은 원래 이름으로 복원
    assert msg["analysis"]["topic"] == "친구 관계 · 학교폭력"
    assert "quotes" not in msg["analysis"]  # 원문 인용(욕설 문장)도 교사에게 안 간다
    assert msg["analysis"]["deadline"] == "내일까지"
    # Claude 에게는 진짜 이름이 가려져서 갔다 (학생은 시연 명단, 교사는 어른 명단)
    assert len(seen) == 1 and "지민" not in seen[0] and "김민지" not in seen[0]


def test_명시적_통과는_원문만_교사에게_보이고_AI_문장과_인용을_저장하지_않는다(client, auth, ids, engine, refine_with):
    refine_with(lambda m: reply({**good(m), "needs_refinement": False}))
    conv = ids["conv_parent1"]
    sent = send(client, auth, "parent1", conv, RAW).json()
    assert sent["status"] == "pending" and sent["raw_text"] == RAW

    teacher = read(client, auth, "teacher1", conv)[0]
    assert teacher["status"] == "done"
    assert teacher["raw_text"] == RAW
    assert teacher["refined_text"] is None and teacher["analysis"] is None
    with engine.connect() as c:
        row = c.execute(text("SELECT raw_text, refined_text, analysis, status FROM messages WHERE id = :i"),
                        {"i": sent["id"]}).one()
    assert row == (RAW, None, {"needs_refinement": False}, "done")
    parent = read(client, auth, "parent1", conv)[0]
    assert parent["raw_text"] == RAW and parent["refined_text"] is None and parent["analysis"] is None


def test_최상위_판정값_false도_원문_통과로_처리한다(client, auth, ids, engine, monkeypatch):
    monkeypatch.setattr(router_mod, "_refine_in_background", REAL_BACKGROUND)
    monkeypatch.setitem(router_mod._refine_state, "enabled", True)
    monkeypatch.setattr(router_mod, "refine_message", lambda *a: {
        "status": "done", "needs_refinement": False, "refined_text": "버려야 할 정제문",
        "analysis": {"quotes": [RAW], "topic": "버려야 할 분석"}, "error": None,
    })
    send(client, auth, "parent1", ids["conv_parent1"], RAW)
    teacher = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert teacher["raw_text"] == RAW and teacher["refined_text"] is None
    with engine.connect() as c:
        assert c.execute(text("SELECT analysis FROM messages")).scalar() == {"needs_refinement": False}


def test_명시적_정제는_정제문만_교사에게_보인다(client, auth, ids, refine_with):
    refine_with(lambda m: reply({**good(m), "needs_refinement": True, "abusive": False}))
    conv = ids["conv_parent1"]
    send(client, auth, "parent1", conv, RAW)
    teacher = read(client, auth, "teacher1", conv)[0]
    assert teacher["status"] == "done" and teacher["raw_text"] is None
    assert teacher["refined_text"] is not None and "무능하네요" not in teacher["refined_text"]


def test_abusive_false만으로는_통과시키지_않는다(client, auth, ids, refine_with):
    refine_with(lambda m: reply({**good(m), "abusive": False}))
    send(client, auth, "parent1", ids["conv_parent1"], RAW)
    teacher = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert teacher["status"] == "done" and teacher["raw_text"] is None
    assert teacher["refined_text"] is not None


def test_판정_없이_정제문이_빠진_완료_결과는_실패로_닫는다(client, auth, ids, engine, monkeypatch):
    monkeypatch.setattr(router_mod, "_refine_in_background", REAL_BACKGROUND)
    monkeypatch.setitem(router_mod._refine_state, "enabled", True)
    monkeypatch.setattr(router_mod, "refine_message", lambda *a: {
        "status": "done", "refined_text": None, "analysis": {}, "error": None,
    })
    send(client, auth, "parent1", ids["conv_parent1"], RAW)
    teacher = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert teacher["status"] == "failed" and teacher["raw_text"] is None
    assert teacher["analysis"]["error"] == "정제 결과에 정제문이 없습니다"
    with engine.connect() as c:
        assert c.execute(text("SELECT raw_text FROM messages")).scalar() == RAW


def test_거절되면_failed_와_사유가_저장된다(client, auth, ids, refine_with):
    refine_with(lambda m: reply(text="", stop="refusal"))
    send(client, auth, "parent1", ids["conv_parent1"], RAW)
    msg = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert msg["status"] == "failed" and msg["refined_text"] is None
    assert "거절" in msg["analysis"]["error"]
    assert msg["raw_text"] is None  # 실패해도 원문은 교사에게 안 간다 (DB 에는 있다)
    assert "지민" not in msg["analysis"]["error"]  # 사유에 원문이 들어가지 않는다


def test_Claude_호출이_예외로_끝나도_pending_으로_멈추지_않는다(client, auth, ids, refine_with):
    def boom(m):
        raise RuntimeError("뜻밖의 오류")

    refine_with(boom)
    send(client, auth, "parent1", ids["conv_parent1"], RAW)
    msg = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert msg["status"] == "failed" and "RuntimeError" in msg["analysis"]["error"]


def test_교사_메시지는_정제하지_않는다(client, auth, ids, refine_with):
    seen = refine_with(lambda m: reply(good(m)))
    r = send(client, auth, "teacher1", ids["conv_parent1"], "확인해 보겠습니다")
    assert r.json()["status"] == "skip"
    assert seen == []
    assert read(client, auth, "parent1", ids["conv_parent1"])[0]["refined_text"] is None


def test_다시_정제하면_실패했던_메시지가_done_이_된다(client, auth, ids, refine_with):
    state = {"ok": False}
    refine_with(lambda m: reply(good(m)) if state["ok"] else reply(text="", stop="refusal"))
    send(client, auth, "parent1", ids["conv_parent1"], RAW)
    first = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert first["status"] == "failed"

    state["ok"] = True
    r = client.post(f"/conversations/{ids['conv_parent1']}/messages/{first['id']}/refine", headers=auth("teacher1"))
    assert r.status_code == 202 and r.json()["status"] == "pending" and r.json()["analysis"] is None
    again = read(client, auth, "teacher1", ids["conv_parent1"])[0]
    assert again["status"] == "done" and again["refined_text"].startswith("지민이")


def test_다시_정제는_해당_교사만_할_수_있다(client, auth, ids, refine_with):
    refine_with(lambda m: reply(text="", stop="refusal"))
    mid = send(client, auth, "parent1", ids["conv_parent1"], RAW).json()["id"]
    url = f"/conversations/{ids['conv_parent1']}/messages/{mid}/refine"
    assert client.post(url, headers=auth("parent1")).status_code == 403  # 학부모 본인도 안 됨
    assert client.post(url, headers=auth("parent2")).status_code == 404  # 남의 대화
    assert client.post(url).status_code == 401  # 로그인 없음


def test_다시_정제는_학부모_메시지에만(client, auth, ids, refine_with):
    refine_with(lambda m: reply(good(m)))
    mid = send(client, auth, "teacher1", ids["conv_parent1"], "확인해 보겠습니다").json()["id"]  # skip
    assert client.post(f"/conversations/{ids['conv_parent1']}/messages/{mid}/refine", headers=auth("teacher1")).status_code == 404
    assert client.post(f"/conversations/{ids['conv_parent1']}/messages/99999/refine", headers=auth("teacher1")).status_code == 404
    # 다른 대화의 메시지 번호로는 안 된다
    other = send(client, auth, "parent2", ids["conv_parent2"], RAW).json()["id"]
    assert client.post(f"/conversations/{ids['conv_parent1']}/messages/{other}/refine", headers=auth("teacher1")).status_code == 404


# ---------------------------------------------------------------- 원문은 DB 에만: 누가 무엇을 보나

def test_교사가_받는_어떤_응답에도_원문이_없다(client, auth, ids, engine, refine_with):
    refine_with(lambda m: reply(good(m)))
    conv = ids["conv_parent1"]
    sent = send(client, auth, "parent1", conv, RAW).json()
    teacher_sees = [
        json.dumps(read(client, auth, "teacher1", conv), ensure_ascii=False),
        client.post(f"/conversations/{conv}/messages/{sent['id']}/refine", headers=auth("teacher1")).text,  # 다시 정제 응답
        json.dumps(read(client, auth, "teacher1", conv), ensure_ascii=False),
    ]
    for body in teacher_sees:
        assert RAW not in body
        assert "무능하네요" not in body  # 인용문(quotes)에 있던 문장
    with engine.connect() as c:  # 그래도 DB 에는 원문이 있다 (법적 확인용)
        from sqlalchemy import text as sql
        assert c.execute(sql("SELECT raw_text FROM messages WHERE id = :i"), {"i": sent["id"]}).scalar() == RAW


def test_학부모는_자기_원문만_보고_정제_결과는_못_본다(client, auth, ids, refine_with):
    refine_with(lambda m: reply(good(m)))
    conv = ids["conv_parent1"]
    posted = send(client, auth, "parent1", conv, RAW).json()
    assert posted["raw_text"] == RAW and posted["refined_text"] is None and posted["analysis"] is None
    msg = read(client, auth, "parent1", conv)[0]
    assert msg["raw_text"] == RAW
    assert msg["refined_text"] is None and msg["analysis"] is None  # 욕설로 분류됐는지 등은 학부모에게 안 보인다
    assert msg["status"] == "done"


def test_교사가_보낸_글은_양쪽_모두_그대로_보인다(client, auth, ids, refine_with):
    refine_with(lambda m: reply(good(m)))
    conv = ids["conv_parent1"]
    send(client, auth, "teacher1", conv, "확인해 보겠습니다")
    for who in ("teacher1", "parent1"):
        assert read(client, auth, who, conv)[0]["raw_text"] == "확인해 보겠습니다"


def test_초안은_자동으로_만들거나_DB에_저장하지_않는다(client, auth, ids, engine, refine_with, monkeypatch):
    from app.routers import drafts

    refine_with(lambda m: reply(good(m)))
    monkeypatch.setattr(drafts, "draft_reply", lambda *a, **k: pytest.fail("자동 초안 호출"))
    sent = send(client, auth, "parent1", ids["conv_parent1"], RAW).json()
    with engine.connect() as c:
        analysis = c.execute(text("SELECT analysis FROM messages WHERE id = :i"), {"i": sent["id"]}).scalar()
    assert "reply_draft" not in analysis


# ---------------------------------------------------------------- 시험용 스위치 (정제 켜고 끄기)

@pytest.fixture
def dev_tools(monkeypatch):
    monkeypatch.setattr(router_mod.settings, "dev_tools", True)


def test_스위치_API_는_개발_모드가_아니면_없는_것처럼_404(client):
    assert client.get("/dev/refine").status_code == 404
    assert client.post("/dev/refine", json={"enabled": False}).status_code == 404


def test_스위치로_켜고_끌_수_있다(client, dev_tools, monkeypatch):
    monkeypatch.setitem(router_mod._refine_state, "enabled", True)
    assert client.get("/dev/refine").json() == {"enabled": True}
    assert client.post("/dev/refine", json={"enabled": False}).json() == {"enabled": False}
    assert client.get("/dev/refine").json() == {"enabled": False}
    assert client.post("/dev/refine", json={"enabled": True}).json() == {"enabled": True}


def test_꺼져_있으면_Claude_를_부르지_않고_켠_뒤_다시_정제하면_된다(client, auth, ids, dev_tools, refine_with):
    seen = refine_with(lambda m: reply(good(m)))
    conv = ids["conv_parent1"]
    client.post("/dev/refine", json={"enabled": False})

    send(client, auth, "parent1", conv, RAW)
    msg = read(client, auth, "teacher1", conv)[0]
    assert msg["status"] == "failed" and "꺼져" in msg["analysis"]["error"]
    assert msg["raw_text"] is None  # 꺼져 있어도 교사에게 원문은 안 간다
    assert seen == []  # Claude 를 부르지 않았다 (API 비용 없음)

    client.post("/dev/refine", json={"enabled": True})
    r = client.post(f"/conversations/{conv}/messages/{msg['id']}/refine", headers=auth("teacher1"))
    assert r.status_code == 202
    again = read(client, auth, "teacher1", conv)[0]
    assert again["status"] == "done" and again["refined_text"].startswith("지민이")
    assert len(seen) == 1  # 켠 뒤에만 한 번 불렀다
