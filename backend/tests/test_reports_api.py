"""신고(D) API — 가짜 보고서로 (키 없이). 원문 · 인용이 누구에게 가는지가 핵심"""
import pytest
from sqlalchemy import text

from app.routers import messages as messages_router
from app.routers import reports as reports_router

REAL_REPORT_BG = reports_router._report_in_background


@pytest.fixture(autouse=True)
def clean(engine, ids):
    yield
    with engine.begin() as c:
        c.execute(text("TRUNCATE messages RESTART IDENTITY"))
        c.execute(text("UPDATE conversations SET report = NULL, reported_at = NULL"))


@pytest.fixture
def reporter(monkeypatch):
    """reporter(result_or_fn): 신고하면 진짜 백그라운드 흐름을 돌리되 write_report 대신 이것을 쓴다."""
    calls = []

    def use(result):
        def fake(history, memo, roster, adults):
            calls.append({"history": history, "memo": memo})
            return result(history) if callable(result) else result

        monkeypatch.setitem(messages_router._refine_state, "enabled", True)
        monkeypatch.setattr(reports_router, "_report_in_background", REAL_REPORT_BG)
        monkeypatch.setattr(reports_router, "write_report", fake)
        return calls

    return use


def put(engine, conv, sender, status, raw, refined=None):
    with engine.begin() as c:
        return c.execute(text("INSERT INTO messages (conversation_id, sender_id, raw_text, refined_text, status) "
                              "VALUES (:c, :s, :r, :f, :st) RETURNING id"),
                         {"c": conv, "s": sender, "r": raw, "f": refined, "st": status}).scalar()


def done(history):
    first = next(h for h in history if h["who"] == "parent")
    return {"status": "done", "error": None, "report": {
        "summary": "학부모가 욕설을 했습니다.", "severity": "보통", "severity_reason": "욕설 1회",
        "threats": [], "parent_requests": [], "teacher_responses": [], "check": [],
        "incidents": [{"message_id": first["id"], "at": "2026-11-10T09:00:00+09:00", "types": ["욕설"],
                       "quote": "씨 무능하네"}],
        "parent_messages": 1, "period": {"from": "x", "to": "y"}, "memo": "계속 욕을 함"}}


def report(client, auth, conv, who="teacher1", memo="계속 욕을 함"):
    return client.post(f"/conversations/{conv}/report", headers=auth(who), json={"memo": memo})


def test_신고하면_원문으로_보고서를_쓰고_민원대응팀은_원문까지_본다(client, auth, ids, engine, reporter):
    conv = ids["conv_parent1"]
    m1 = put(engine, conv, ids["parent1"], "done", "씨 무능하네 상담하자고", "상담하고 싶습니다.")
    put(engine, conv, ids["parent1"], "failed", "정제 안 된 원문")
    put(engine, conv, ids["teacher1"], "skip", "다음 주 화요일 어떠세요?")
    calls = reporter(done)

    r = report(client, auth, conv)
    assert r.status_code == 202 and r.json()["reported_at"]
    assert [(h["who"], h["text"]) for h in calls[0]["history"]] == [
        ("parent", "씨 무능하네 상담하자고"), ("parent", "정제 안 된 원문"), ("teacher", "다음 주 화요일 어떠세요?")]
    assert calls[0]["memo"] == "계속 욕을 함"

    lst = client.get("/reports", headers=auth("team1")).json()
    assert [(x["conversation_id"], x["status"], x["severity"], x["teacher_name"], x["parent_name"]) for x in lst] == [
        (conv, "done", "보통", "김민지", "박서연")]
    d = client.get(f"/reports/{conv}", headers=auth("team1")).json()
    assert d["report"]["incidents"][0] == {"message_id": m1, "at": "2026-11-10T09:00:00+09:00", "types": ["욕설"],
                                           "quote": "씨 무능하네"}
    assert d["report"]["memo"] == "계속 욕을 함" and d["report"]["at"]
    assert [m["raw_text"] for m in d["messages"]][:2] == ["씨 무능하네 상담하자고", "정제 안 된 원문"]


def test_담임에게는_인용을_빼고_학부모에게는_신고_자체를_안_준다(client, auth, ids, engine, reporter):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 무능하네", "아쉽습니다.")
    reporter(done)
    report(client, auth, conv)

    t = client.get(f"/conversations/{conv}", headers=auth("teacher1")).json()
    assert t["report"]["status"] == "done" and t["report"]["summary"]
    assert t["report"]["incidents"] == [{"message_id": t["report"]["incidents"][0]["message_id"],
                                         "at": "2026-11-10T09:00:00+09:00", "types": ["욕설"]}]
    assert "씨 무능하네" not in str(client.get("/conversations", headers=auth("teacher1")).json())
    p = client.get(f"/conversations/{conv}", headers=auth("parent1")).json()
    assert "report" not in p and "reported_at" not in p


def test_실패하면_사유를_남기고_다시_만들면_처음_신고_시각은_그대로(client, auth, ids, engine, reporter):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 무능하네", "아쉽습니다.")
    reporter({"status": "failed", "report": None, "error": "Claude 가 응답을 거절함"})
    first = report(client, auth, conv).json()["reported_at"]
    t = client.get(f"/conversations/{conv}", headers=auth("teacher1")).json()
    assert t["report"] == {**t["report"], "status": "failed", "error": "Claude 가 응답을 거절함", "memo": "계속 욕을 함"}

    reporter(done)
    again = report(client, auth, conv, memo=None).json()
    assert again["reported_at"] == first
    assert client.get(f"/reports/{conv}", headers=auth("team1")).json()["report"]["status"] == "done"


def test_스위치가_꺼져_있으면_Claude_없이_실패(client, auth, ids, engine, monkeypatch):
    conv = ids["conv_parent1"]
    put(engine, conv, ids["parent1"], "done", "씨 무능하네", "아쉽습니다.")
    monkeypatch.setattr(reports_router, "_report_in_background", REAL_REPORT_BG)
    monkeypatch.setitem(messages_router._refine_state, "enabled", False)
    report(client, auth, conv)
    r = client.get(f"/reports/{conv}", headers=auth("team1")).json()["report"]
    assert r["status"] == "failed" and "꺼져" in r["error"]


def test_권한(client, auth, ids, engine):
    conv = ids["conv_parent1"]
    assert report(client, auth, conv, who="parent1").status_code == 403       # 학부모는 신고 못 함
    assert report(client, auth, conv, who="team1").status_code == 404         # 대화 당사자가 아님
    assert report(client, auth, ids["conv_parent2"], who="parent1").status_code == 404
    assert client.get("/reports", headers=auth("teacher1")).status_code == 403
    assert client.get(f"/reports/{conv}", headers=auth("team1")).status_code == 404  # 신고 안 된 대화
    assert report(client, auth, conv).status_code == 202                       # 신고 중(pending) 상태로 남음
    r = client.get("/reports", headers=auth("team1")).json()
    assert r[0]["status"] == "pending" and r[0]["summary"] is None
    assert report(client, auth, conv).json()["report"]["status"] == "pending"  # 만드는 중이면 그대로
