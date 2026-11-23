"""다중 대화 민원 이관 보고서: API 키·DB 없이 원문 근거 검증을 시험한다."""
import json
from datetime import datetime

from app.ai.case_report import MAX_MESSAGES, MAX_RAW_CHARS, write_case_report
from app.ai.client import ClaudeReply
from app.ai.extract import KST


def at(day, hour=9):
    return datetime(2026, 11, day, hour, tzinfo=KST)


HISTORY = [
    {"id": 13, "conversation_id": 202, "who": "parent",
     "text": "김민지 선생님, 서윤이 앞자리로 꼭 바꾸세요. 안 하면 교육청에 민원 넣겠습니다. 010-1234-5678",
     "at": at(11)},
    {"id": 11, "conversation_id": 101, "who": "parent",
     "text": "서윤이 앞자리로 바꿔 주세요. 몇 번을 말해야 알아들어요?", "at": at(10)},
    {"id": 14, "conversation_id": 202, "who": "parent",
     "text": "또 말합니다. 앞자리로 바꿔 주세요.", "at": at(12)},
    {"id": 12, "conversation_id": 101, "who": "teacher",
     "text": "자리 배치는 월말에 바꿀 예정입니다.", "at": at(10, 12)},
]


def reply(body=None, *, stop="end_turn"):
    return ClaudeReply(text=json.dumps(body or {}, ensure_ascii=False), stop_reason=stop,
                       model="fake", usage={})


def body(**overrides):
    return {"summary": "학부모가 앞자리 배치를 여러 차례 요청했고 교사가 월말 변경을 안내했습니다.",
            "rude_evidence": [], "repeated_demands": [], "reason_evidence": [], **overrides}


def run(builder, history=HISTORY, reason="서윤이 앞자리 배치를 거듭 요구하며 답변을 재촉합니다"):
    seen = {}

    def call(masked):
        seen["masked"] = masked
        return builder(json.loads(masked))

    return write_case_report(history, reason, ["서윤"], ["김민지"], call=call), seen.get("masked")


def test_여러_대화_원문을_가리고_근거와_건수를_검증해_복원한다():
    def build(sent):
        messages = sent["messages"]
        assert [(m["no"], m["conversation_id"], m["who"]) for m in messages] == [
            (1, 101, "parent"), (2, 101, "teacher"), (3, 202, "parent"), (4, 202, "parent")]
        original_name_quote = messages[2]["text"].split(" 안 하면")[0]
        return reply(body(
            rude_evidence=[
                {"no": 1, "types": ["비꼼 · 조롱", "반말 · 호통"], "quote": "몇 번을 말해야 알아들어요?"},
                {"no": 3, "types": ["위협 · 협박"], "quote": "안 하면 교육청에 민원 넣겠습니다."}],
            repeated_demands=[{"theme": "앞자리 배치 요구", "evidence": [
                {"no": 1, "quote": "앞자리로 바꿔 주세요."},
                {"no": 3, "quote": "앞자리로 꼭 바꾸세요."},
                {"no": 4, "quote": "앞자리로 바꿔 주세요."}]}],
            reason_evidence=[{"no": 3, "quote": original_name_quote,
                              "explanation": "앞자리 배치를 당장 요구한 내용입니다."}] ))

    result, sent = run(build)
    assert result["status"] == "done" and result["error"] is None
    for secret in ("서윤", "김민지", "010-1234-5678"):
        assert secret not in sent
    report = result["report"]
    assert (report["parent_messages"], report["rude_messages"], report["repeated_demands_count"]) == (3, 2, 3)
    assert [(i["conversation_id"], i["message_id"]) for i in report["rude_evidence"]] == [(101, 11), (202, 13)]
    assert [i["message_id"] for i in report["repeated_demands"][0]["evidence"]] == [11, 13, 14]
    assert report["reason_evidence"][0]["quote"] == "김민지 선생님, 서윤이 앞자리로 꼭 바꾸세요."
    assert report["reason_evidence"][0]["at"] == at(11).isoformat()


def test_가짜_인용_교사_메시지_중복_증거는_건수에서_뺀다():
    def build(_):
        return reply(body(
            rude_evidence=[
                {"no": 1, "types": ["욕설"], "quote": "없는 욕설"},
                {"no": 2, "types": ["욕설"], "quote": "자리 배치는"},
                {"no": 3, "types": ["위협 · 협박", "위협 · 협박"], "quote": "교육청에 민원 넣겠습니다."},
                {"no": 3, "types": ["욕설"], "quote": "안 하면"},
                {"no": 4, "types": ["없는 유형"], "quote": "또 말합니다."}],
            repeated_demands=[
                {"theme": "근거 하나뿐", "evidence": [{"no": 1, "quote": "앞자리로 바꿔 주세요."},
                                                  {"no": 2, "quote": "자리 배치는"}]},
                {"theme": "앞자리", "evidence": [{"no": 1, "quote": "앞자리로 바꿔 주세요."},
                                             {"no": 3, "quote": "앞자리로 꼭 바꾸세요."},
                                             {"no": 3, "quote": "안 하면"}]},
                {"theme": "앞자리", "evidence": [{"no": 3, "quote": "앞자리로 꼭 바꾸세요."},
                                             {"no": 4, "quote": "앞자리로 바꿔 주세요."}]}],
            reason_evidence=[{"no": 9, "quote": "없는 말", "explanation": "없는 주장"},
                             {"no": 1, "quote": "앞자리로 바꿔 주세요.", "explanation": "반복 요청입니다."}]))

    report = run(build)[0]["report"]
    assert report["parent_messages"] == 3
    assert report["rude_messages"] == 1
    assert report["rude_evidence"][0]["types"] == ["위협 · 협박"]
    assert report["repeated_demands_count"] == 2
    assert len(report["repeated_demands"]) == 1
    assert [i["message_id"] for i in report["reason_evidence"]] == [11]


def test_학부모_글이나_신청_사유가_없으면_ai를_호출하지_않는다():
    never = lambda _: (_ for _ in ()).throw(AssertionError("AI 호출 금지"))
    assert write_case_report([HISTORY[3]], "불편합니다", [], [], call=never)["status"] == "failed"
    assert write_case_report(HISTORY, "   ", [], [], call=never)["status"] == "failed"


def test_입력이_너무_길면_일부를_몰래_빼지_않고_실패한다():
    never = lambda _: (_ for _ in ()).throw(AssertionError("AI 호출 금지"))
    too_many = [{**HISTORY[1], "id": i} for i in range(MAX_MESSAGES + 1)]
    assert write_case_report(too_many, "사유", [], [], call=never)["status"] == "failed"
    too_long = [{**HISTORY[1], "text": "가" * (MAX_RAW_CHARS + 1)}]
    assert write_case_report(too_long, "사유", [], [], call=never)["status"] == "failed"


def test_원문_한도_안의_메시지는_JSON_메타데이터가_늘어나도_분석한다():
    history = [{**HISTORY[1], "id": i + 1, "text": "가" * 350} for i in range(MAX_MESSAGES)]
    sent = {}

    def call(masked):
        sent["length"] = len(masked)
        return reply(body())

    result = write_case_report(history, "사유", [], [], call=call)
    assert sent["length"] > MAX_RAW_CHARS
    assert result["status"] == "done"
    assert result["report"]["parent_messages"] == MAX_MESSAGES


def test_지어낸_이름과_거절_응답은_보고서가_아니다():
    result, _ = run(lambda _: reply(body(summary="하준이가 피해를 입었습니다.")))
    assert result["status"] == "failed" and "이름" in result["error"] and result["report"] is None
    result, _ = run(lambda _: reply(stop="refusal"))
    assert result["status"] == "failed" and result["report"] is None
