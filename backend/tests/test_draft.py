"""draft_reply · draft_notice 시험 — API 키도 DB 도 없이, 가짜 Claude 응답으로"""
import json

from app.ai import client as ai_client
from app.ai.client import ClaudeReply
from app.ai.draft import draft_notice, draft_reply

ROSTER = ["서윤", "민재"]
ADULTS = ["김민지", "박서연"]
HISTORY = [
    {"who": "parent", "text": "서윤이가 체육 시간에 넘어졌다고 합니다. 보건실에 다녀왔는지 알려 주세요."},
    {"who": "teacher", "text": "네 확인해 보겠습니다."},
    {"who": "parent", "text": "민재가 밀었다고 합니다. 민재 부모님께 사과를 받게 해 주세요. 연락처는 010-1234-5678 입니다."},
]


def reply(parsed=None, *, text=None, stop="end_turn"):
    return ClaudeReply(text=text if text is not None else json.dumps(parsed, ensure_ascii=False),
                       stop_reason=stop, model="fake", usage={"input": 1, "output": 1})


def fake_name(sent: str, line_start: str) -> str:
    """가린 대화에서 첫 학부모 줄의 첫 단어(= 서윤이의 가짜 이름 + 「이가」)"""
    line = next(l for l in sent.splitlines() if l.startswith(line_start))
    return line.split(": ", 1)[1].split("이가")[0]


def run_reply(builder, memo="보건실 다녀옴"):
    seen = {}

    def call(masked):
        seen["sent"] = masked
        return builder(masked)

    return draft_reply(HISTORY, memo, ROSTER, ADULTS, call=call), seen.get("sent")


def test_가린_대화만_보내고_초안은_원래_이름으로_복원된다():
    def build(sent):
        f = fake_name(sent, "학부모:")
        return reply({"draft": f"안녕하세요. {f}는 그날 보건실에 다녀왔습니다. 감사합니다.",
                      "check": [f"{f} 쪽 사과 요청에 답하지 않았습니다"]})

    result, sent = run_reply(build)
    for secret in ("서윤", "민재", "김민지", "010-1234-5678"):
        assert secret not in sent
    assert sent.startswith("[대화]\n학부모: ") and "\n교사: 네 확인해 보겠습니다." in sent
    assert sent.endswith("[담임 메모]\n보건실 다녀옴")
    assert result["status"] == "done" and result["error"] is None
    assert result["draft"] == "안녕하세요. 서윤는 그날 보건실에 다녀왔습니다. 감사합니다."
    assert result["check"] == ["서윤 쪽 사과 요청에 답하지 않았습니다"]


def test_같은_이름은_메시지가_달라도_같은_가짜_이름():
    _, sent = run_reply(lambda s: reply({"draft": "감사합니다.", "check": []}))
    lines = [l for l in sent.splitlines() if l.startswith("학부모:")]
    # 둘째 학부모 글의 민재는 두 번 나오는데 같은 가짜 이름이어야 한다
    second = lines[1].split(": ", 1)[1]
    fake = second.split("가 밀었다고")[0]
    assert second.count(fake) == 2


def test_메모가_없으면_없음으로_보낸다():
    _, sent = run_reply(lambda s: reply({"draft": "감사합니다.", "check": []}), memo=None)
    assert sent.endswith("[담임 메모]\n(없음)")


def test_초안에_지어낸_이름이_있으면_실패():
    result, _ = run_reply(lambda s: reply({"draft": "하준이가 그랬다고 들었습니다.", "check": []}))
    assert result["status"] == "failed" and "이름" in result["error"] and result["draft"] is None


def test_초안이_비어_있으면_실패():
    result, _ = run_reply(lambda s: reply({"draft": "  ", "check": []}))
    assert result["status"] == "failed" and "draft" in result["error"]


def test_거절_JSON_아님도_정제와_같이_실패로():
    assert run_reply(lambda s: reply({}, stop="refusal"))[0]["status"] == "failed"
    assert "JSON" in run_reply(lambda s: reply(text="그냥 글"))[0]["error"]


def test_check_는_많아야_5개_빈_줄은_뺀다():
    result, _ = run_reply(lambda s: reply({"draft": "감사합니다.", "check": ["", "a", "b", "c", "d", "e", "f"]}))
    assert result["check"] == ["a", "b", "c", "d", "e"]


# ---------------------------------------------------------------- 공지

def test_공지_초안():
    result = draft_notice("내일 현장학습. 9시까지 운동장. 도시락", ROSTER, ADULTS,
                          call=lambda m: reply({"title": "현장학습 안내", "body": "안녕하세요, 학부모님.\n- 9시까지 운동장", "check": []}))
    assert result == {"status": "done", "title": "현장학습 안내", "body": "안녕하세요, 학부모님.\n- 9시까지 운동장",
                      "check": [], "error": None}


def test_공지에_학생_이름이_남으면_check_에_꼭_넣는다():
    def build(masked):
        fake = masked.split(" ")[0]  # 「서윤이」의 가짜 이름 + 이
        fake = fake[:-1] if fake.endswith("이") else fake
        return reply({"title": "준비물 안내", "body": f"{fake} 어머님이 도와주십니다.", "check": []})

    result = draft_notice("서윤이 어머님이 도와주심. 준비물 색연필", ROSTER, ADULTS, call=build)
    assert result["status"] == "done"
    assert result["body"] == "서윤 어머님이 도와주십니다."
    assert result["check"] == ["공지에 학생 이름(서윤)이 들어 있습니다. 빼고 보내세요"]


def test_공지_본문이_비면_실패():
    result = draft_notice("내일 현장학습", ROSTER, ADULTS, call=lambda m: reply({"title": "안내", "body": "", "check": []}))
    assert result["status"] == "failed" and result["body"] is None


# ---------------------------------------------------------------- client: 기능마다 프롬프트 · 스키마가 맞게 들어간다

def test_초안_호출은_초안_프롬프트와_스키마를_쓴다(monkeypatch):
    seen = []
    monkeypatch.setattr(ai_client, "call_json", lambda system, schema, masked, **kw: seen.append((system, schema)))
    ai_client.call_draft_reply("x")
    ai_client.call_draft_notice("x")
    ai_client.call_refine("x")
    assert seen == [(ai_client.DRAFT_REPLY_PROMPT, ai_client.DRAFT_REPLY_SCHEMA),
                    (ai_client.DRAFT_NOTICE_PROMPT, ai_client.DRAFT_NOTICE_SCHEMA),
                    (ai_client.SYSTEM_PROMPT, ai_client.REFINE_SCHEMA)]
    assert set(ai_client.DRAFT_REPLY_SCHEMA["required"]) == {"draft", "check"}
    assert set(ai_client.DRAFT_NOTICE_SCHEMA["required"]) == {"title", "body", "check"}
