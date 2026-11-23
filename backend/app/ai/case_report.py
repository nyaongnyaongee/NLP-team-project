"""민원 이관 신청서의 다중 대화 보고서.

입력은 신청 전에 교사가 선택한 대화의 메시지만 받는다. 학부모의 글은 정제문이
아닌 원문이며, 개인정보를 가린 뒤 Claude에 보낸다. AI가 제시한 인용은 반드시
해당 학부모 원문의 부분 문자열인지 확인한 다음에만 보고서에 싣는다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Callable

from app.ai.client import CASE_REPORT_SCHEMA, ClaudeReply, call_case_report
from app.ai.draft import _invented_names, _mask_all
from app.ai.extract import KST
from app.ai.pii_mask import PiiMasker
from app.ai.refine import call_and_parse

log = logging.getLogger("ai.case_report")

MAX_MESSAGES = 80
MAX_RAW_CHARS = 30_000
MAX_INPUT_CHARS = 100_000  # 가명·메시지 번호·시각을 붙인 JSON 은 원문보다 길어진다.
MAX_REASON_CHARS = 2_000
MAX_QUOTE_CHARS = 300
RUDE_TYPES = set(CASE_REPORT_SCHEMA["properties"]["rude_evidence"]["items"]["properties"]["types"]["items"]["enum"])


def _failed(error: str) -> dict:
    return {"status": "failed", "report": None, "error": error}


def _kst(at: datetime) -> datetime:
    return (at if at.tzinfo else at.replace(tzinfo=KST)).astimezone(KST)


def _ordered(history: list[dict]) -> list[dict] | None:
    """잘못된 입력이나 중복 메시지를 AI로 보내지 않는다."""
    if not isinstance(history, list) or not 1 <= len(history) <= MAX_MESSAGES:
        return None
    seen: set[int] = set()
    for h in history:
        if not isinstance(h, dict) or type(h.get("id")) is not int or type(h.get("conversation_id")) is not int \
                or h["id"] in seen or h.get("who") not in ("parent", "teacher") \
                or not isinstance(h.get("text"), str) or not isinstance(h.get("at"), datetime):
            return None
        seen.add(h["id"])
    return sorted(history, key=lambda h: (_kst(h["at"]), h["id"]))


def write_case_report(
    history: list[dict],
    reason: str,
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_case_report,
) -> dict:
    """선택 대화 원문에서 검증 가능한 근거만 담은 고정 형식 보고서를 만든다.

    history: [{id, conversation_id, who, text, at}, ...]. ``text``는 학부모의
    원문 또는 교사가 최종 보낸 문장이다. 입력이 너무 길면 일부를 몰래 빼지 않고
    실패를 돌려준다. ``call``은 API 키 없이 가짜 Claude로 시험할 때 사용한다.
    """
    if not isinstance(reason, str) or not reason.strip():
        return _failed("교사의 이관 신청 사유가 비어 있습니다")
    reason = reason.strip()
    if len(reason) > MAX_REASON_CHARS:
        return _failed("이관 신청 사유가 너무 깁니다")
    ordered = _ordered(history)
    if ordered is None:
        return _failed(f"선택한 메시지가 없거나 형식이 잘못되었거나 {MAX_MESSAGES}건을 넘었습니다")
    if not any(h["who"] == "parent" for h in ordered):
        return _failed("선택한 대화에 학부모 메시지가 없습니다")
    if sum(len(h["text"]) for h in ordered) + len(reason) > MAX_RAW_CHARS:
        return _failed("선택한 대화가 너무 길어 보고서를 만들 수 없습니다")

    try:
        masker, masked, mp = _mask_all([h["text"] for h in ordered] + [reason], roster, adults)
    except Exception as e:
        log.exception("가명처리 실패")
        return _failed(f"가명처리 실패 ({type(e).__name__})")
    masked_messages, masked_reason = masked[:-1], masked[-1]
    payload = {
        "reason": masked_reason,
        "messages": [
            {"no": no, "conversation_id": h["conversation_id"], "at": _kst(h["at"]).isoformat(),
             "who": h["who"], "text": masked_messages[no - 1]}
            for no, h in enumerate(ordered, start=1)
        ],
    }
    user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(user) > MAX_INPUT_CHARS:
        return _failed("가명처리한 대화가 너무 길어 보고서를 만들 수 없습니다")

    parsed, error = call_and_parse(call, user, log)
    if error:
        return _failed(error)
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return _failed("검증 실패: summary 가 비어 있습니다")
    for field in ("rude_evidence", "repeated_demands", "reason_evidence"):
        if not isinstance(parsed.get(field), list):
            return _failed(f"검증 실패: {field} 형식이 잘못되었습니다")

    def evidence(item: dict) -> dict | None:
        if not isinstance(item, dict):
            return None
        no, quote = item.get("no"), item.get("quote")
        if type(no) is not int or no < 1 or no > len(ordered) or not isinstance(quote, str):
            return None
        quote = quote.strip()
        h = ordered[no - 1]
        if h["who"] != "parent" or not quote or len(quote) > MAX_QUOTE_CHARS \
                or quote not in masked_messages[no - 1]:
            return None
        original_quote = PiiMasker.unmask(quote, mp)
        if original_quote not in h["text"]:
            return None
        return {"conversation_id": h["conversation_id"], "message_id": h["id"],
                "at": _kst(h["at"]).isoformat(), "quote": original_quote}

    rude_evidence: list[dict] = []
    rude_seen: set[int] = set()
    for item in parsed["rude_evidence"]:
        ref = evidence(item)
        if ref is None or not isinstance(item.get("types"), list) or ref["message_id"] in rude_seen:
            continue
        types = list(dict.fromkeys(t for t in item["types"] if isinstance(t, str) and t in RUDE_TYPES))
        if not types:
            continue
        rude_seen.add(ref["message_id"])
        rude_evidence.append({**ref, "types": types})

    repeated_demands: list[dict] = []
    repeated_seen: set[str] = set()
    repeated_message_ids: set[int] = set()
    for group in parsed["repeated_demands"]:
        if not isinstance(group, dict) or not isinstance(group.get("theme"), str) \
                or not isinstance(group.get("evidence"), list):
            continue
        theme = group["theme"].strip()
        if not theme or theme.casefold() in repeated_seen:
            continue
        refs: list[dict] = []
        group_ids: set[int] = set()
        for item in group["evidence"]:
            ref = evidence(item)
            if ref is not None and ref["message_id"] not in group_ids:
                group_ids.add(ref["message_id"])
                refs.append(ref)
        if len(refs) < 2:
            continue
        repeated_seen.add(theme.casefold())
        repeated_message_ids.update(group_ids)
        repeated_demands.append({"theme": theme, "evidence": refs})

    reason_evidence: list[dict] = []
    reason_seen: set[tuple[int, str]] = set()
    for item in parsed["reason_evidence"]:
        ref = evidence(item)
        explanation = item.get("explanation") if isinstance(item, dict) else None
        if ref is None or not isinstance(explanation, str) or not explanation.strip():
            continue
        key = (ref["message_id"], ref["quote"])
        if key in reason_seen:
            continue
        reason_seen.add(key)
        reason_evidence.append({**ref, "explanation": explanation.strip()})

    written = ([summary] + [g["theme"] for g in repeated_demands]
               + [r["explanation"] for r in reason_evidence])
    problems = _invented_names(masker, written, mp, user)
    if problems:
        return _failed("검증 실패: " + " / ".join(problems))

    un = PiiMasker.unmask
    return {"status": "done", "error": None, "report": {
        "summary": un(summary.strip(), mp),
        "parent_messages": sum(h["who"] == "parent" for h in ordered),
        "rude_messages": len(rude_evidence),
        "repeated_demands_count": len(repeated_message_ids),
        "rude_evidence": rude_evidence,
        "repeated_demands": [{"theme": un(g["theme"], mp), "evidence": g["evidence"]} for g in repeated_demands],
        "reason_evidence": [{**r, "explanation": un(r["explanation"], mp)} for r in reason_evidence],
    }}
