"""학부모 메시지 정제 (A).  [재관]

    result = refine_message(raw_text, roster, adults)
    # {"status": "done" | "failed", "refined_text": str | None, "analysis": dict | None, "error": str | None}

이 함수가 하는 일: 명단으로 가명처리 → Claude → 검증 → 원래 값으로 복원.
저장(messages 갱신) · WebSocket 알림은 부르는 쪽이 한다. 이 함수는 DB 를 모른다.

개인정보: 가림표(Mapping)는 이 함수 안에서만 살고, 로그 · 반환값 · 오류 문구 어디에도 원문을 넣지 않는다.
가명처리가 실패하면 원문을 보내지 않고 바로 실패로 끝낸다.
"""
from __future__ import annotations

import json
import logging
import threading
from functools import lru_cache
from typing import Callable

import anthropic

from app.ai.client import ClaudeReply, call_refine
from app.ai.pii_mask import Mapping, PiiMasker

log = logging.getLogger("ai.refine")

_mask_lock = threading.Lock()  # PiiMasker 안의 난수 · 형태소 분석기를 여러 요청이 동시에 건드리지 않게


@lru_cache(maxsize=16)
def _build_masker(roster: tuple[str, ...], adults: tuple[str, ...]) -> PiiMasker:
    return PiiMasker(roster=list(roster), adults=list(adults))  # 처음 만들 때 1초쯤 걸림


def get_masker(roster: list[str], adults: list[str]) -> PiiMasker:
    """같은 명단이면 만들어 둔 것을 다시 쓴다 (반마다 한 번)."""
    return _build_masker(tuple(sorted(set(roster))), tuple(sorted(set(adults))))


def call_and_parse(call: Callable[[str], ClaudeReply], masked: str, log: logging.Logger) -> tuple[dict | None, str | None]:
    """Claude 를 부르고 응답 상태 · JSON 을 점검한다. (parsed, None) 또는 (None, 실패 사유).
    정제 · 초안이 같이 쓴다. 사유에는 원문 · 가린 글을 넣지 않는다."""
    try:
        reply = call(masked)
    except anthropic.APIStatusError as e:
        log.warning("Claude 호출 실패 status=%s", e.status_code)
        return None, f"Claude 호출 실패 (HTTP {e.status_code})"
    except anthropic.APIError as e:  # 연결 · 시간 초과 등
        log.warning("Claude 호출 실패 %s", type(e).__name__)
        return None, f"Claude 호출 실패 ({type(e).__name__})"
    except Exception as e:
        log.exception("호출 중 예기치 못한 오류")
        return None, f"Claude 호출 중 오류 ({type(e).__name__})"

    u = reply.usage
    log.info("model=%s stop=%s sec=%.1f in=%s out=%s cache_read=%s cache_write=%s", reply.model, reply.stop_reason,
             reply.seconds, u.get("input"), u.get("output"), u.get("cache_read"), u.get("cache_write"))

    if reply.stop_reason == "refusal":
        return None, f"Claude 가 응답을 거절함 ({reply.stop_category or '분류 없음'})"
    if reply.stop_reason == "max_tokens":
        return None, "응답이 길이 한도에서 잘림 (max_tokens)"
    if reply.stop_reason != "end_turn":
        return None, f"정상 종료가 아님 ({reply.stop_reason})"
    try:
        parsed = json.loads(reply.text)
        if not isinstance(parsed, dict):
            raise ValueError
    except ValueError:
        return None, "응답이 JSON 형식이 아님"
    return parsed, None


def _failed(error: str) -> dict:
    return {"status": "failed", "refined_text": None, "analysis": None, "error": error}


def _validate(parsed: dict, masked: str, masker: PiiMasker, mp: Mapping) -> list[str]:
    """복원하기 전 점검. 문제 목록을 돌려준다 (비어 있으면 통과)."""
    problems: list[str] = []
    refined = parsed.get("refined")
    if not isinstance(refined, str) or not refined.strip():
        return ["refined 가 비어 있음"]

    quotes = parsed.get("quotes") or []
    for q in quotes:
        if q not in masked:
            problems.append("quotes 가 원문에 그대로 없음")
            break
    deadline = parsed.get("deadline")
    if deadline is not None and deadline not in masked:
        problems.append("deadline 이 원문에 그대로 없음")

    # LLM 이 지어낸 이름
    texts = [refined] + [r.get("text", "") for r in parsed.get("requests") or []]
    for t in texts:
        problems += masker.check_response(t, mp, masked)
    return problems


def _unmask_analysis(parsed: dict, mp: Mapping) -> tuple[str, dict]:
    un = PiiMasker.unmask
    refined = un(parsed["refined"], mp)
    analysis = {k: v for k, v in parsed.items() if k != "refined"}
    analysis["quotes"] = [un(q, mp) for q in analysis.get("quotes") or []]
    analysis["requests"] = [{**r, "text": un(r.get("text", ""), mp)} for r in analysis.get("requests") or []]
    if analysis.get("deadline") is not None:
        analysis["deadline"] = un(analysis["deadline"], mp)
    return refined, analysis


def refine_message(
    raw_text: str,
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_refine,
) -> dict:
    """call 은 시험용: 가짜 응답을 돌려주는 함수를 넣으면 키 없이 시험할 수 있다."""
    # 1. 가명처리 (실패하면 원문을 보내지 않는다)
    try:
        masker = get_masker(roster, adults)
        with _mask_lock:
            masked, mp = masker.mask(raw_text)
    except Exception as e:
        log.exception("가명처리 실패")
        return _failed(f"가명처리 실패 ({type(e).__name__})")

    # 2~4. Claude → 응답 상태 → JSON
    parsed, error = call_and_parse(call, masked, log)
    if error:
        return _failed(error)

    # 5. 검증 (복원 전, 가린 상태에서)
    with _mask_lock:
        problems = _validate(parsed, masked, masker, mp)
    if problems:
        return _failed("검증 실패: " + " / ".join(problems))

    # 6. 복원
    refined, analysis = _unmask_analysis(parsed, mp)
    return {"status": "done", "refined_text": refined, "analysis": analysis, "error": None}
