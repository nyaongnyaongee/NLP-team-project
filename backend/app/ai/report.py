"""신고 보고서 (D).  [재관]

    result = write_report(history, memo, roster, adults)
    # {"status": "done" | "failed", "report": dict | None, "error": str | None}

담임이 대화를 「신고」하면 부른다. 정제 · 초안 · 추출과 같은 틀: 명단으로 가명처리 → Claude → 검증 → 복원. DB 를 모른다.

- history: [{"id": 메시지 id, "who": "parent" | "teacher", "text": str, "at": datetime}, …] 오래된 것부터.
  **학부모 글은 원문(raw_text)** 이다 — 초안 · 추출(교사가 볼 수 있는 글만)과 다르다.
  보고서는 민원대응팀이 읽고, 무슨 말을 했는지가 핵심이라 정제문으로는 쓸 수 없다. 정제 실패 · 처리 전 글도 원문으로 넣는다.
- memo: 담임이 신고하며 적은 사유 (없어도 됨).

검증
- incidents: 번호가 학부모 메시지를 가리키고, quote 가 그 메시지 글자 그대로여야 한다. 안 맞는 항목만 버린다
  (증거 인용이 틀리면 안 되지만, 하나 틀렸다고 보고서 전체를 버리면 민원대응팀이 아무것도 못 받는다).
- types · threats · severity: 목록에 없는 값은 버린다 (스키마로 막히지만 한 번 더).
- 지어낸 이름이 있으면 다른 기능처럼 전체 실패.
- 메시지 번호 → 메시지 id · 보낸 때는 코드가 붙인다 (Claude 가 날짜를 옮겨 적다 틀리지 않게).

보고서에는 원문 인용(incidents[].quote)이 들어간다. 교사에게 줄 때는 부르는 쪽(routers/reports.py)이 quote 를 뺀다.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from app.ai.client import REPORT_SCHEMA, ClaudeReply, call_report
from app.ai.draft import WHO, _invented_names, _mask_all
from app.ai.extract import DAYS, KST
from app.ai.pii_mask import PiiMasker
from app.ai.refine import call_and_parse

log = logging.getLogger("ai.report")

MAX_ITEMS = 10      # 목록 하나에 이만큼까지
MAX_QUOTE = 300

_props = REPORT_SCHEMA["properties"]
INCIDENT_TYPES = set(_props["incidents"]["items"]["properties"]["types"]["items"]["enum"])
THREATS = set(_props["threats"]["items"]["enum"])
SEVERITIES = set(_props["severity"]["enum"])


def _kst(at: datetime) -> datetime:
    return (at if at.tzinfo else at.replace(tzinfo=KST)).astimezone(KST)


def _stamp(at: datetime) -> str:
    k = _kst(at)
    return f"{k.month}/{k.day}({DAYS[k.weekday()]}) {k:%H:%M}"


def _strings(items, limit: int = MAX_ITEMS) -> list[str]:
    if not isinstance(items, list):
        return []
    return [s.strip() for s in items if isinstance(s, str) and s.strip()][:limit]


def write_report(
    history: list[dict],
    memo: str | None,
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_report,
) -> dict:
    def failed(error: str) -> dict:
        return {"status": "failed", "report": None, "error": error}

    if not any(h["who"] == "parent" for h in history):
        return failed("학부모가 보낸 메시지가 없습니다")  # 읽을 글이 없으면 Claude 를 부르지 않는다

    memo = (memo or "").strip()
    try:
        masker, masked, mp = _mask_all([h["text"] for h in history] + [memo], roster, adults)
    except Exception as e:
        log.exception("가명처리 실패")
        return failed(f"가명처리 실패 ({type(e).__name__})")
    masked_hist, masked_memo = masked[:-1], masked[-1]

    lines = [f"#{i} {_stamp(h['at'])} {WHO[h['who']]}: {t}"
             for i, (h, t) in enumerate(zip(history, masked_hist), start=1)]
    user = f"[담임 메모]\n{masked_memo or '(없음)'}\n[대화]\n" + "\n".join(lines)

    parsed, error = call_and_parse(call, user, log)
    if error:
        return failed(error)
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return failed("검증 실패: summary 가 비어 있음")

    # incidents: 번호 · 인용이 맞는 것만 (원문 인용은 증거라서 한 글자도 어긋나면 안 된다)
    incidents: list[dict] = []
    raw_incidents = parsed.get("incidents") if isinstance(parsed.get("incidents"), list) else []
    used: set[int] = set()
    for it in raw_incidents:
        if not isinstance(it, dict):
            continue
        no, quote = it.get("no"), it.get("quote")
        if not isinstance(no, int) or not 1 <= no <= len(history) or no in used:
            continue
        h = history[no - 1]
        if h["who"] != "parent" or not isinstance(quote, str) or not quote.strip() \
                or quote.strip() not in masked_hist[no - 1]:
            continue
        types = [t for t in (it.get("types") or []) if t in INCIDENT_TYPES]
        used.add(no)
        incidents.append({"no": no, "types": list(dict.fromkeys(types)) or ["기타"], "quote": quote.strip()[:MAX_QUOTE]})
        if len(incidents) == MAX_ITEMS:
            break
    if len(incidents) < len(raw_incidents):
        log.info("문제 메시지 %d개 중 %d개만 씀 (번호 · 인용 점검)", len(raw_incidents), len(incidents))
    incidents.sort(key=lambda x: x["no"])

    severity = parsed.get("severity") if parsed.get("severity") in SEVERITIES else None
    threats = list(dict.fromkeys(t for t in (parsed.get("threats") or []) if t in THREATS))
    texts = {
        "summary": summary.strip(),
        "severity_reason": parsed.get("severity_reason").strip() if isinstance(parsed.get("severity_reason"), str) else "",
    }
    lists = {k: _strings(parsed.get(k)) for k in ("parent_requests", "teacher_responses", "check")}

    # 인용(quote)은 입력 글자 그대로임을 위에서 확인했으니 이름 검사는 Claude 가 쓴 글에만
    written = list(texts.values()) + [s for v in lists.values() for s in v]
    problems = _invented_names(masker, written, mp, user)
    if problems:
        return failed("검증 실패: " + " / ".join(problems))

    un = PiiMasker.unmask
    parents = [h for h in history if h["who"] == "parent"]
    report = {
        "summary": un(texts["summary"], mp),
        "severity": severity,
        "severity_reason": un(texts["severity_reason"], mp),
        "threats": threats,
        "parent_requests": [un(s, mp) for s in lists["parent_requests"]],
        "teacher_responses": [un(s, mp) for s in lists["teacher_responses"]],
        "check": [un(s, mp) for s in lists["check"]],
        "incidents": [{"message_id": history[i["no"] - 1]["id"],
                       "at": _kst(history[i["no"] - 1]["at"]).isoformat(),
                       "types": i["types"],
                       "quote": un(i["quote"], mp)} for i in incidents],
        "parent_messages": len(parents),
        "period": {"from": _kst(history[0]["at"]).isoformat(), "to": _kst(history[-1]["at"]).isoformat()},
        "memo": memo or None,
    }
    return {"status": "done", "report": report, "error": None}
