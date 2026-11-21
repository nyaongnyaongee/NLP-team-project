"""답장 · 공지 초안 (B).  [재관]

    result = draft_reply(history, memo, roster, adults)
    # {"status": "done" | "failed", "draft": str | None, "check": list[str], "error": str | None}
    result = draft_notice(points, roster, adults)
    # {"status": "done" | "failed", "title": str | None, "body": str | None, "check": list[str], "error": str | None}
    result = draft_faq(memo, history, roster, adults)
    # {"status": "done" | "failed", "question": str | None, "answer": str | None, "check": list[str], "error": str | None}

정제(A)와 같은 틀: 명단으로 가명처리 → Claude → 검증(지어낸 이름) → 복원. DB 를 모르고 저장도 안 한다
(초안은 교사가 고쳐서 보통 메시지로 보낸다).

history 의 학부모 글은 원문이 아니라 정제문(refined_text)을 넣는다 — 교사에게 원문을 주지 않는 정책과 같은 선에서,
초안도 교사가 볼 수 있는 글만 보고 쓴다.
가림표(Mapping)는 대화 전체에 하나: 같은 이름은 메시지가 달라도 같은 가짜 이름이 된다.
"""
from __future__ import annotations

import logging
from typing import Callable

from app.ai.client import ClaudeReply, call_draft_faq, call_draft_notice, call_draft_reply
from app.ai.pii_mask import Mapping, PiiMasker
from app.ai.refine import _mask_lock, call_and_parse, get_masker

log = logging.getLogger("ai.draft")

WHO = {"parent": "학부모", "teacher": "교사"}
MAX_CHECK = 5


def _mask_all(texts: list[str], roster: list[str], adults: list[str]) -> tuple[PiiMasker, list[str], Mapping]:
    masker = get_masker(roster, adults)
    mp = Mapping()
    with _mask_lock:
        masked = [masker.mask(t, mp)[0] for t in texts]
    return masker, masked, mp


def _invented_names(masker: PiiMasker, texts: list[str], mp: Mapping, masked_input: str) -> list[str]:
    problems: list[str] = []
    with _mask_lock:
        for t in texts:
            problems += masker.check_response(t, mp, masked_input)
    return problems


def _check_list(parsed: dict) -> list[str]:
    items = parsed.get("check") or []
    return [c for c in items if isinstance(c, str) and c.strip()][:MAX_CHECK]


def _warn_student_names(check: list[str], mp: Mapping, roster: list[str], texts: list[str], note: str) -> None:
    """반 전체가 보는 글(공지 · Q&A)에 학생 이름(가짜 이름)이 남았으면 check 에 알린다. 복원 전이라 {} 자리에 가짜 이름이 들어가고,
    나중에 check 를 복원할 때 진짜 이름으로 바뀐다."""
    students = set(roster)
    for fake, orig in mp.fake2orig.items():
        if mp.kinds.get(fake) == "NAME" and (orig in students or orig[1:] in students) and any(fake in t for t in texts):
            line = note.format(fake)
            if line not in check:
                check.append(line)


def draft_reply(
    history: list[dict],
    memo: str | None,
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_draft_reply,
) -> dict:
    """history: [{"who": "parent" | "teacher", "text": str}, …] 오래된 것부터. 학부모 글은 정제문.
    memo: 교사가 이번 답장에 담고 싶은 것 (없어도 됨)."""
    def failed(error: str) -> dict:
        return {"status": "failed", "draft": None, "check": [], "error": error}

    memo = (memo or "").strip()
    try:
        masker, masked, mp = _mask_all([h["text"] for h in history] + [memo], roster, adults)
    except Exception as e:
        log.exception("가명처리 실패")
        return failed(f"가명처리 실패 ({type(e).__name__})")
    *masked_hist, masked_memo = masked
    lines = [f"{WHO[h['who']]}: {t}" for h, t in zip(history, masked_hist)]
    user = "[대화]\n" + "\n".join(lines) + "\n\n[담임 메모]\n" + (masked_memo or "(없음)")

    parsed, error = call_and_parse(call, user, log)
    if error:
        return failed(error)
    draft = parsed.get("draft")
    if not isinstance(draft, str) or not draft.strip():
        return failed("검증 실패: draft 가 비어 있음")
    check = _check_list(parsed)
    problems = _invented_names(masker, [draft, *check], mp, user)
    if problems:
        return failed("검증 실패: " + " / ".join(problems))

    un = PiiMasker.unmask
    return {"status": "done", "draft": un(draft, mp).strip(), "check": [un(c, mp) for c in check], "error": None}


def draft_notice(
    points: str,
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_draft_notice,
) -> dict:
    """points: 교사가 적은 공지 요점 (자유 형식)."""
    def failed(error: str) -> dict:
        return {"status": "failed", "title": None, "body": None, "check": [], "error": error}

    try:
        masker, (masked,), mp = _mask_all([points.strip()], roster, adults)
    except Exception as e:
        log.exception("가명처리 실패")
        return failed(f"가명처리 실패 ({type(e).__name__})")

    parsed, error = call_and_parse(call, masked, log)
    if error:
        return failed(error)
    title, body = parsed.get("title"), parsed.get("body")
    if not isinstance(title, str) or not title.strip() or not isinstance(body, str) or not body.strip():
        return failed("검증 실패: 제목이나 본문이 비어 있음")
    check = _check_list(parsed)
    problems = _invented_names(masker, [title, body, *check], mp, masked)
    if problems:
        return failed("검증 실패: " + " / ".join(problems))

    # 반 전체가 받는 공지에 학생 이름이 남았으면 (프롬프트가 빼라고 했어도) 교사에게 꼭 알린다
    _warn_student_names(check, mp, roster, [title, body], "공지에 학생 이름({})이 들어 있습니다. 빼고 보내세요")

    un = PiiMasker.unmask
    return {"status": "done", "title": un(title, mp).strip(), "body": un(body, mp).strip(),
            "check": [un(c, mp) for c in check], "error": None}


def draft_faq(
    memo: str,
    history: list[dict] | None,
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_draft_faq,
) -> dict:
    """memo: 교사가 적은 짧은 메모 (무엇을 Q&A 로 남길지). history: 메모를 쓰게 된 대화 (교사가 볼 수 있는 글만, 없어도 됨).
    반 학부모 모두가 보므로 학생 · 학부모 이름이 남으면 check 에 알린다 (공지와 같음)."""
    def failed(error: str) -> dict:
        return {"status": "failed", "question": None, "answer": None, "check": [], "error": error}

    history = history or []
    try:
        masker, masked, mp = _mask_all([h["text"] for h in history] + [memo.strip()], roster, adults)
    except Exception as e:
        log.exception("가명처리 실패")
        return failed(f"가명처리 실패 ({type(e).__name__})")
    *masked_hist, masked_memo = masked
    user = "[담임 메모]\n" + masked_memo
    if history:
        lines = [f"{WHO[h['who']]}: {t}" for h, t in zip(history, masked_hist)]
        user = "[대화]\n" + "\n".join(lines) + "\n\n" + user

    parsed, error = call_and_parse(call, user, log)
    if error:
        return failed(error)
    question, answer = parsed.get("question"), parsed.get("answer")
    if not isinstance(question, str) or not question.strip() or not isinstance(answer, str) or not answer.strip():
        return failed("검증 실패: 질문이나 답변이 비어 있음")
    check = _check_list(parsed)
    problems = _invented_names(masker, [question, answer, *check], mp, user)
    if problems:
        return failed("검증 실패: " + " / ".join(problems))
    _warn_student_names(check, mp, roster, [question, answer], "Q&A 에 학생 이름({})이 들어 있습니다. 빼고 등록하세요")
    # 학부모 · 교사 이름도 모두에게 보이면 안 된다
    for fake, orig in mp.fake2orig.items():
        if mp.kinds.get(fake) == "NAME" and orig in adults and (fake in question or fake in answer):
            line = f"Q&A 에 어른 이름({fake})이 들어 있습니다. 빼고 등록하세요"
            if line not in check:
                check.append(line)

    un = PiiMasker.unmask
    return {"status": "done", "question": un(question, mp).strip(), "answer": un(answer, mp).strip(),
            "check": [un(c, mp) for c in check], "error": None}
