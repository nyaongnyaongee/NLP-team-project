"""refine_message 시험 — API 키도 DB 도 없이, 가짜 Claude 응답으로"""
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from app.ai import client as ai_client
from app.ai.client import ClaudeReply
from app.ai.refine import get_masker, refine_message

ROSTER = ["서윤", "민재"]
ADULTS = ["김민지", "박서연"]
RAW = "서윤이 물통을 누가 또 숨겼대요. 담임 김민지 선생님 무능하네요. 내일까지 새로 사 주세요. 연락처는 010-1234-5678 입니다."


def reply(parsed=None, *, text=None, stop="end_turn", category=None):
    return ClaudeReply(text=text if text is not None else json.dumps(parsed, ensure_ascii=False),
                       stop_reason=stop, stop_category=category, model="fake", usage={"input": 1, "output": 1})


def good(masked: str, **over) -> dict:
    """가린 글을 바탕으로 만든 정상 응답 (이름은 가짜 이름 그대로 — 실제 모델도 그렇게 돌려줌)"""
    first = masked.split(".")[0] + "."
    parsed = {
        "abusive": True,
        "quotes": ["담임 " + masked.split("담임 ")[1].split(".")[0] + "."],
        "topic": "친구 관계 · 학교폭력",
        "requests": [{"type": "배상", "text": "새 물통을 사 달라"}],
        "threats": [],
        "deadline": "내일까지",
        "refined": first + " 같은 일이 되풀이되어 걱정됩니다.",
    }
    parsed.update(over)
    return parsed


def run(builder):
    """builder(masked) -> ClaudeReply.  가짜 call 이 받은 글도 같이 돌려준다."""
    seen = {}

    def call(masked):
        seen["masked"] = masked
        return builder(masked)

    return refine_message(RAW, ROSTER, ADULTS, call=call), seen["masked"]


def test_정상_Claude_는_가린_글만_보고_결과는_원래_값으로_복원된다():
    result, sent = run(lambda m: reply(good(m)))
    # Claude 에게 간 글에는 진짜 이름 · 전화번호가 없다
    for secret in ("서윤", "김민지", "010-1234-5678"):
        assert secret not in sent
    assert result["status"] == "done" and result["error"] is None
    assert result["refined_text"].startswith("서윤이 물통을")  # 정제문 복원
    assert result["analysis"]["quotes"] == ["담임 김민지 선생님 무능하네요."]  # 인용 복원
    assert result["analysis"]["deadline"] == "내일까지"
    assert "refined" not in result["analysis"]  # 정제문은 refined_text 로 따로


def test_요청_문장도_복원된다():
    def builder(m):
        fake_name = m.split("이 ")[0]  # 가짜 학생 이름
        return reply(good(m, requests=[{"type": "경위 설명", "text": f"{fake_name}의 물통 일을 설명해 달라"}]))

    result, _ = run(builder)
    assert result["analysis"]["requests"][0]["text"] == "서윤의 물통 일을 설명해 달라"


def test_거절되면_실패():
    result, _ = run(lambda m: reply(text="", stop="refusal", category="general_harms"))
    assert result["status"] == "failed" and "거절" in result["error"]
    assert result["refined_text"] is None and result["analysis"] is None


def test_길이_한도에서_잘리면_실패():
    result, _ = run(lambda m: reply(text='{"refined": "잘', stop="max_tokens"))
    assert result["status"] == "failed" and "max_tokens" in result["error"]


def test_JSON_이_아니면_실패():
    result, _ = run(lambda m: reply(text="죄송하지만 정제할 수 없습니다"))
    assert result["status"] == "failed" and "JSON" in result["error"]


def test_quotes_가_원문에_없으면_실패():
    result, _ = run(lambda m: reply(good(m, quotes=["이 문장은 원문에 없습니다"])))
    assert result["status"] == "failed" and "quotes" in result["error"]


def test_deadline_이_원문에_없으면_실패():
    result, _ = run(lambda m: reply(good(m, deadline="다음 주 월요일까지")))
    assert result["status"] == "failed" and "deadline" in result["error"]


def test_지어낸_이름이_있으면_실패():
    # 명단에는 있지만 이 글에는 나오지 않은 이름(민재)을 Claude 가 끼워 넣음
    result, _ = run(lambda m: reply(good(m, refined="민재가 물통을 숨겼다고 합니다.")))
    assert result["status"] == "failed" and "민재" in result["error"]


def test_정제문이_비어_있으면_실패():
    result, _ = run(lambda m: reply(good(m, refined="  ")))
    assert result["status"] == "failed"


def test_deadline_이_null_이면_그대로_null():
    result, _ = run(lambda m: reply(good(m, deadline=None)))
    assert result["status"] == "done" and result["analysis"]["deadline"] is None


def _api_error(status):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIStatusError("boom", response=httpx.Response(status, request=req), body=None)


def test_API_오류는_실패로_돌려주고_원문을_담지_않는다():
    def boom(m):
        raise _api_error(529)

    result = refine_message(RAW, ROSTER, ADULTS, call=boom)
    assert result["status"] == "failed" and "529" in result["error"]
    for secret in ("서윤", "김민지", "물통"):
        assert secret not in result["error"]


def test_연결_오류도_실패로():
    def boom(m):
        raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    result = refine_message(RAW, ROSTER, ADULTS, call=boom)
    assert result["status"] == "failed" and "APIConnectionError" in result["error"]


def test_가명처리가_실패하면_Claude_를_부르지_않는다(monkeypatch):
    class Broken:
        def mask(self, text):
            raise RuntimeError("깨짐")

    monkeypatch.setattr("app.ai.refine.get_masker", lambda r, a: Broken())
    called = []
    result = refine_message(RAW, ROSTER, ADULTS, call=lambda m: called.append(m))
    assert result["status"] == "failed" and "가명처리" in result["error"]
    assert called == []  # 원문이 어디로도 나가지 않았다


def test_같은_명단은_가명처리기를_다시_만들지_않는다():
    assert get_masker(["서윤", "민재"], ["김민지"]) is get_masker(["민재", "서윤"], ["김민지"])


# ---------------------------------------------------------------- client.call_refine: 요청 모양 (네트워크 없이)

class FakeMessages:
    def __init__(self, store):
        self.store = store

    def create(self, **kw):
        self.store.update(kw)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="{}")], stop_reason="end_turn", stop_details=None, model=kw["model"],
            usage=SimpleNamespace(input_tokens=5, output_tokens=7, cache_read_input_tokens=3, cache_creation_input_tokens=0))


def fake_client(store, beta_store):
    return SimpleNamespace(messages=FakeMessages(store), beta=SimpleNamespace(messages=FakeMessages(beta_store)))


def test_요청에_캐시_스키마_effort_가_들어간다():
    plain, beta = {}, {}
    r = ai_client.call_refine("가린 글", model="claude-haiku-5-5", client=fake_client(plain, beta))
    assert plain["model"] == "claude-haiku-5-5" and not beta  # Haiku 는 fallback 기능 없이 일반 호출
    assert plain["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert plain["system"][0]["text"] == ai_client.SYSTEM_PROMPT
    assert plain["messages"] == [{"role": "user", "content": "가린 글"}]
    assert plain["output_config"]["format"]["schema"] == ai_client.REFINE_SCHEMA
    assert plain["output_config"]["effort"] == "medium"
    assert plain["max_tokens"] == 4000
    assert r.usage == {"input": 5, "output": 7, "cache_read": 3, "cache_write": 0}


def test_Sonnet_은_거절_대비_fallback_을_켠다():
    plain, beta = {}, {}
    ai_client.call_refine("가린 글", model="claude-sonnet-5-5", client=fake_client(plain, beta))
    assert not plain and beta["fallbacks"] == "default" and beta["betas"] == [ai_client.FALLBACK_BETA]
