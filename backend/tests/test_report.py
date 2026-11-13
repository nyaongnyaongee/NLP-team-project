"""write_report 시험 — API 키도 DB 도 없이, 가짜 Claude 응답으로"""
import json
from datetime import datetime

from app.ai.client import ClaudeReply
from app.ai.extract import KST
from app.ai.report import write_report

ROSTER = ["서윤", "민재"]
ADULTS = ["김민지", "박서연"]


def at(day, hour=9, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=KST)


HISTORY = [
    {"id": 11, "who": "parent", "text": "서윤이 짝 왜 안 바꿔줘요? 몇 번을 말해야 알아들어요?", "at": at(10, 9, 12)},
    {"id": 12, "who": "teacher", "text": "짝은 이번 달 말에 바꿀 예정입니다.", "at": at(10, 12, 30)},
    {"id": 13, "who": "parent", "text": "김민지 선생 그만둬라. 오늘 안에 안 바꾸면 교육청에 넣는다. 010-1234-5678", "at": at(10, 21, 47)},
]


def reply(parsed=None, *, text=None, stop="end_turn"):
    return ClaudeReply(text=text if text is not None else json.dumps(parsed, ensure_ascii=False),
                       stop_reason=stop, model="fake", usage={})


def body(**kw):
    out = {"summary": "학부모가 짝을 바꿔 달라고 요구했습니다.", "incidents": [], "threats": [],
           "parent_requests": [], "teacher_responses": [], "severity": "보통",
           "severity_reason": "반말이 있습니다.", "check": []}
    return {**out, **kw}


def run(builder, history=HISTORY, memo="욕설이 계속됩니다"):
    seen = {}

    def call(masked):
        seen["sent"] = masked
        return builder(masked)

    return write_report(history, memo, ROSTER, ADULTS, call=call), seen.get("sent")


def line(sent, no):
    return next(l for l in sent.splitlines() if l.startswith(f"#{no} "))


def test_원문을_가려서_번호_시각과_보내고_인용은_원래대로_복원된다():
    def build(sent):
        l3 = line(sent, 3)
        quote = l3.split("학부모: ")[1].split(".")[0] + "."   # 「(가짜 이름) 선생 그만둬라.」
        return reply(body(
            incidents=[{"no": 3, "types": ["반말 · 호통", "교사 자질 비난"], "quote": quote},
                       {"no": 1, "types": ["비꼼 · 조롱"], "quote": "몇 번을 말해야 알아들어요?"}],
            threats=["교육청"], parent_requests=["짝 바꾸기"], teacher_responses=["11/10 이달 말 예정이라고 답함"],
            check=["#3 이후 전화가 있었는지"]))

    result, sent = run(build)
    for secret in ("서윤", "김민지", "010-1234-5678"):
        assert secret not in sent
    assert sent.startswith("[담임 메모]\n욕설이 계속됩니다\n[대화]\n#1 11/10(화) 09:12 학부모: ")
    assert "\n#2 11/10(화) 12:30 교사: 짝은 이번 달 말에" in sent
    assert result["status"] == "done" and result["error"] is None
    r = result["report"]
    assert [i["message_id"] for i in r["incidents"]] == [11, 13]            # 번호 순으로, 메시지 id 로 바꿔서
    assert r["incidents"][1]["quote"] == "김민지 선생 그만둬라."            # 원래 이름으로
    assert r["incidents"][1]["at"] == at(10, 21, 47).isoformat()
    assert r["threats"] == ["교육청"] and r["severity"] == "보통"
    assert r["parent_messages"] == 2 and r["memo"] == "욕설이 계속됩니다"
    assert r["period"] == {"from": at(10, 9, 12).isoformat(), "to": at(10, 21, 47).isoformat()}


def test_인용이_원문에_없거나_번호가_틀리면_그_항목만_버린다():
    result, _ = run(lambda s: reply(body(incidents=[
        {"no": 1, "types": ["비꼼 · 조롱"], "quote": "몇번을 말해야 알아들어요?"},   # 띄어쓰기가 다름
        {"no": 2, "types": ["욕설"], "quote": "짝은 이번 달 말에"},                   # 교사 글
        {"no": 9, "types": ["욕설"], "quote": "그만둬라"},                            # 없는 번호
        {"no": 3, "types": ["없는 종류"], "quote": "오늘 안에 안 바꾸면 교육청에 넣는다."},
        {"no": 3, "types": ["위협 · 협박"], "quote": "교육청에 넣는다."},             # 같은 메시지 두 번째
    ])))
    assert result["status"] == "done"
    assert [(i["message_id"], i["types"]) for i in result["report"]["incidents"]] == [(13, ["기타"])]


def test_목록에_없는_위협_심각도는_버린다():
    result, _ = run(lambda s: reply(body(threats=["교육청", "우주", "교육청"], severity="매우 높음")))
    assert result["report"]["threats"] == ["교육청"] and result["report"]["severity"] is None


def test_메모가_없으면_없음으로_보낸다():
    result, sent = run(lambda s: reply(body()), memo="  ")
    assert sent.startswith("[담임 메모]\n(없음)\n") and result["report"]["memo"] is None


def test_지어낸_이름이_있으면_실패():
    result, _ = run(lambda s: reply(body(summary="하준이가 그랬다고 합니다.")))
    assert result["status"] == "failed" and "이름" in result["error"] and result["report"] is None


def test_요약이_비거나_거절이면_실패():
    assert run(lambda s: reply(body(summary=" ")))[0]["status"] == "failed"
    result, _ = run(lambda s: reply(text="", stop="refusal"))
    assert result["status"] == "failed" and "거절" in result["error"]


def test_학부모_글이_없으면_Claude_를_부르지_않는다():
    result, sent = run(lambda s: reply(body()), history=[HISTORY[1]])
    assert result["status"] == "failed" and sent is None
