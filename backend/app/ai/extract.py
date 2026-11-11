"""할 일 · 일정 추출 (C).  [재관]

    result = extract_tasks(history, today, existing, roster, adults)
    # {"status": "done" | "failed", "tasks": [{"kind", "title", "due_text", "due_at"}], "error": str | None}

대화를 닫을 때 부른다. 정제 · 초안과 같은 틀: 명단으로 가명처리 → Claude → 검증 → 복원. DB 를 모른다.

- history: [{"who": "parent" | "teacher", "text": str, "at": datetime}, …] 오래된 것부터.
  학부모 글은 정제문(초안과 같은 선: 교사가 볼 수 있는 글만 보고 뽑는다).
- today: 대화를 닫은 날 (한국 날짜).
- existing: 이 대화에서 이미 추가 · 완료한 것 [{"kind", "title"}] — 같은 일을 또 뽑지 않게 Claude 에게 보여 준다.

날짜: Claude 가 「다음 주 화요일」을 메시지 보낸 날 기준으로 YYYY-MM-DD 로 바꾸고(달력을 같이 준다), 코드가 점검한다.
  due_text 가 대화에 그대로 없거나, 날짜 꼴이 틀렸거나, 대화 기간에서 크게 벗어나면 그 항목의 날짜만 버리고 제목은 남긴다
  (날짜는 담임이 화면에서 고칠 수 있지만, 틀린 날짜는 모르고 지나칠 수 있다).
지어낸 이름이 있으면 정제 · 초안처럼 전체를 실패로 한다.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

from app.ai.client import ClaudeReply, call_extract
from app.ai.draft import WHO, _invented_names, _mask_all
from app.ai.pii_mask import PiiMasker
from app.ai.refine import call_and_parse

log = logging.getLogger("ai.extract")

KST = ZoneInfo("Asia/Seoul")
DAYS = "월화수목금토일"
MAX_TASKS = 10
MAX_TITLE = 60
CALENDAR_WEEKS_AFTER = 4   # 달력: 첫 메시지가 있는 주 ~ 오늘에서 4주 뒤
CALENDAR_MAX_WEEKS = 12    # 대화가 아주 길어도 달력은 이만큼만 (앞쪽을 자른다)
DATE_SLACK_BEFORE = 7      # 첫 메시지보다 이만큼 이른 날짜까지는 받는다 (「지난주 금요일에 다쳤어요」 같은 일정은 드묾)
DATE_MAX_AHEAD = 400       # 오늘에서 이만큼 뒤까지


def _md(d: date) -> str:
    return f"{d.month}/{d.day}({DAYS[d.weekday()]})"


def _calendar(first: date, today: date) -> str:
    start = first - timedelta(days=first.weekday())
    end = today - timedelta(days=today.weekday()) + timedelta(weeks=CALENDAR_WEEKS_AFTER)
    weeks = []
    d = start
    while d <= end:
        weeks.append(" ".join(_md(d + timedelta(days=i)) for i in range(7)))
        d += timedelta(weeks=1)
    return "\n".join(weeks[-CALENDAR_MAX_WEEKS:])


def _kst_date(at: datetime) -> date:
    return (at if at.tzinfo else at.replace(tzinfo=KST)).astimezone(KST).date()


def _due_at(item: dict, masked_input: str, lo: date, hi: date) -> tuple[str | None, datetime | None]:
    """(due_text, due_at). 점검에 걸리면 (None, None) — 날짜만 버린다."""
    due_text, d, t = item.get("due_text"), item.get("date"), item.get("time")
    if not isinstance(due_text, str) or not due_text.strip():
        return None, None
    if due_text not in masked_input:
        return None, None
    if d is None:
        return due_text, None  # 「다음 달」처럼 날을 못 정한 것: 표현만 남긴다
    try:
        day = date.fromisoformat(d) if isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else None
    except ValueError:
        day = None
    if day is None or not lo <= day <= hi:
        return due_text, None
    clock = time(0, 0)
    if isinstance(t, str) and re.fullmatch(r"\d{2}:\d{2}", t):
        h, m = map(int, t.split(":"))
        if h < 24 and m < 60:
            clock = time(h, m)
    return due_text, datetime.combine(day, clock, tzinfo=KST)


def _norm(title: str) -> str:
    return re.sub(r"\s+", "", title)


def extract_tasks(
    history: list[dict],
    today: date,
    existing: list[dict],
    roster: list[str],
    adults: list[str],
    *,
    call: Callable[[str], ClaudeReply] = call_extract,
) -> dict:
    def failed(error: str) -> dict:
        return {"status": "failed", "tasks": [], "error": error}

    if not history:
        return {"status": "done", "tasks": [], "error": None}  # 읽을 글이 없으면 Claude 를 부르지 않는다

    titles = [e["title"] for e in existing]
    try:
        masker, masked, mp = _mask_all([h["text"] for h in history] + titles, roster, adults)
    except Exception as e:
        log.exception("가명처리 실패")
        return failed(f"가명처리 실패 ({type(e).__name__})")
    masked_hist, masked_titles = masked[:len(history)], masked[len(history):]

    days = [_kst_date(h["at"]) for h in history]
    lines = [f"{_md(d)} {WHO[h['who']]}: {t}" for h, d, t in zip(history, days, masked_hist)]
    kind_ko = {"todo": "할 일", "event": "일정"}
    done_lines = [f"- {kind_ko[e['kind']]}: {t}" for e, t in zip(existing, masked_titles)]
    user = (f"[오늘]\n{today.isoformat()} ({DAYS[today.weekday()]})\n"
            f"[달력]\n{_calendar(min(days), today)}\n"
            "[대화]\n" + "\n".join(lines) + "\n"
            "[이미 등록된 것]\n" + ("\n".join(done_lines) or "(없음)"))

    parsed, error = call_and_parse(call, user, log)
    if error:
        return failed(error)
    items = parsed.get("tasks")
    if not isinstance(items, list):
        return failed("검증 실패: tasks 가 목록이 아님")

    # 형식이 틀린 항목은 버리고(전체를 실패로 하지 않음), 같은 제목 · 이미 등록된 제목도 뺀다
    convo = "\n".join(masked_hist)  # due_text 는 대화 글에 있어야 한다 (달력 · 등록된 제목은 근거가 아님)
    lo, hi = min(days) - timedelta(days=DATE_SLACK_BEFORE), today + timedelta(days=DATE_MAX_AHEAD)
    seen = {_norm(t) for t in masked_titles}
    kept: list[dict] = []
    for it in items:
        if not isinstance(it, dict) or it.get("kind") not in ("todo", "event"):
            continue
        title = it.get("title")
        if not isinstance(title, str) or not title.strip() or _norm(title) in seen:
            continue
        seen.add(_norm(title))
        due_text, due_at = _due_at(it, convo, lo, hi)
        kept.append({"kind": it["kind"], "title": title.strip()[:MAX_TITLE], "due_text": due_text, "due_at": due_at})
        if len(kept) == MAX_TASKS:
            break
    if len(kept) < len(items):
        log.info("추출 항목 %d개 중 %d개만 씀", len(items), len(kept))

    problems = _invented_names(masker, [k["title"] for k in kept], mp, user)
    if problems:
        return failed("검증 실패: " + " / ".join(problems))

    un = PiiMasker.unmask
    for k in kept:
        k["title"] = un(k["title"], mp)
        if k["due_text"] is not None:
            k["due_text"] = un(k["due_text"], mp)
    return {"status": "done", "tasks": kept, "error": None}
