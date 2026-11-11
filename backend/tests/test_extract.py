"""extract_tasks 시험 — API 키도 DB 도 없이, 가짜 Claude 응답으로"""
import json
from datetime import date, datetime

from app.ai.client import ClaudeReply
from app.ai.extract import KST, extract_tasks

ROSTER = ["서윤", "민재"]
ADULTS = ["김민지", "박서연"]
TODAY = date(2026, 11, 12)  # 목요일


def at(day, hour=9):
    return datetime(2026, 11, day, hour, 0, tzinfo=KST)


HISTORY = [
    {"who": "parent", "text": "서윤이가 체육 시간에 넘어졌다고 합니다. 다음 주에 상담할 수 있을까요? 연락처는 010-1234-5678 입니다.", "at": at(10)},
    {"who": "teacher", "text": "체육 선생님께 전달하겠습니다. 상담은 다음 주 화요일 오후 3시 괜찮으실까요?", "at": at(11)},
    {"who": "parent", "text": "네. 그리고 민재가 밀었다는데 내일 병원 때문에 조퇴하겠습니다.", "at": at(11, 20)},
]


def reply(parsed=None, *, text=None, stop="end_turn"):
    return ClaudeReply(text=text if text is not None else json.dumps(parsed, ensure_ascii=False),
                       stop_reason=stop, model="fake", usage={})


def task(kind, title, due_text=None, d=None, t=None):
    return {"kind": kind, "title": title, "due_text": due_text, "date": d, "time": t}


def run(builder, history=HISTORY, existing=()):
    seen = {}

    def call(masked):
        seen["sent"] = masked
        return builder(masked)

    return extract_tasks(history, TODAY, list(existing), ROSTER, ADULTS, call=call), seen.get("sent")


def fake(sent, real_line_start, before):
    """가린 대화에서 「before」 바로 앞 단어 = 가짜 이름"""
    line = next(l for l in sent.splitlines() if real_line_start in l)
    return line.split(before)[0].split(" ")[-1]


def test_가린_대화와_날짜_달력을_보내고_결과는_복원된다():
    def build(sent):
        f = fake(sent, "밀었다는데", "가 밀었다는데")
        return reply({"tasks": [
            task("todo", "체육 선생님께 전달하기"),
            task("event", "학부모 상담", "다음 주 화요일 오후 3시", "2026-11-17", "15:00"),
            task("event", "병원 조퇴", "내일", "2026-11-12"),
            task("todo", f"{f} 관련 경위 확인하기"),
        ]})

    result, sent = run(build)
    for secret in ("서윤", "민재", "김민지", "010-1234-5678"):
        assert secret not in sent
    assert sent.startswith("[오늘]\n2026-11-12 (목)\n[달력]\n11/9(월) 11/10(화)")
    assert "\n11/10(화) 학부모: " in sent and "\n11/11(수) 교사: 체육 선생님께" in sent
    assert sent.endswith("[이미 등록된 것]\n(없음)")
    assert result["status"] == "done" and result["error"] is None
    assert result["tasks"] == [
        {"kind": "todo", "title": "체육 선생님께 전달하기", "due_text": None, "due_at": None},
        {"kind": "event", "title": "학부모 상담", "due_text": "다음 주 화요일 오후 3시",
         "due_at": datetime(2026, 11, 17, 15, 0, tzinfo=KST)},
        {"kind": "event", "title": "병원 조퇴", "due_text": "내일", "due_at": datetime(2026, 11, 12, 0, 0, tzinfo=KST)},
        {"kind": "todo", "title": "민재 관련 경위 확인하기", "due_text": None, "due_at": None},
    ]


def test_대화에_없는_날짜_표현이나_범위_밖_날짜는_날짜만_버린다():
    result, _ = run(lambda s: reply({"tasks": [
        task("event", "상담", "11월 30일", "2026-11-30"),          # 대화에 없는 표현 → 날짜 · 표현 버림
        task("event", "조퇴", "내일", "2031-01-01"),               # 범위 밖 → 표현은 두고 날짜만 버림
        task("event", "상담2", "다음 주 화요일", "11/17"),          # 꼴이 틀림
        task("event", "상담3", "다음 주 화요일", "2026-11-17", "3시"),  # 시각 꼴만 틀림 → 00:00
    ]}))
    got = [(t["title"], t["due_text"], t["due_at"]) for t in result["tasks"]]
    assert got == [("상담", None, None), ("조퇴", "내일", None), ("상담2", "다음 주 화요일", None),
                   ("상담3", "다음 주 화요일", datetime(2026, 11, 17, 0, 0, tzinfo=KST))]


def test_이미_등록된_것과_같은_제목_중복_형식_틀린_항목은_뺀다():
    existing = [{"kind": "todo", "title": "체육 선생님께 전달하기"}]

    def build(sent):
        assert sent.endswith("[이미 등록된 것]\n- 할 일: 체육 선생님께 전달하기")
        return reply({"tasks": [
            task("todo", "체육 선생님께  전달하기"),  # 띄어쓰기만 다름
            task("event", "학부모 상담"), task("event", "학부모 상담"),
            task("memo", "이상한 종류"), task("todo", "  "), "글자",
        ]})

    result, _ = run(build, existing=existing)
    assert [t["title"] for t in result["tasks"]] == ["학부모 상담"]


def test_등록된_제목의_이름도_가려서_보낸다():
    result, sent = run(lambda s: reply({"tasks": []}), existing=[{"kind": "todo", "title": "서윤 무릎 확인하기"}])
    assert "서윤" not in sent and result == {"status": "done", "tasks": [], "error": None}


def test_제목에_지어낸_이름이_있으면_실패():
    result, _ = run(lambda s: reply({"tasks": [task("todo", "하준이 부모님께 연락하기")]}))
    assert result["status"] == "failed" and "이름" in result["error"] and result["tasks"] == []


def test_읽을_글이_없으면_Claude_를_부르지_않는다():
    def boom(_):
        raise AssertionError("부르면 안 됨")

    assert extract_tasks([], TODAY, [], ROSTER, ADULTS, call=boom) == {"status": "done", "tasks": [], "error": None}


def test_거절_JSON_아님_tasks_아님은_실패():
    assert run(lambda s: reply({}, stop="refusal"))[0]["status"] == "failed"
    assert "JSON" in run(lambda s: reply(text="그냥 글"))[0]["error"]
    assert "tasks" in run(lambda s: reply({"tasks": "없음"}))[0]["error"]


def test_10개까지만():
    result, _ = run(lambda s: reply({"tasks": [task("todo", f"일 {i}") for i in range(15)]}))
    assert len(result["tasks"]) == 10
