"""여러 대화를 묶은 민원 이관 신청서와 담당자 ↔ 교사/학부모 별도 채팅."""
import json
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.roster import class_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import SessionLocal, get_db
from app.routers import messages as messages_router
from app.routers.ws import hub
from app.schemas.complaint import (
    ComplaintChatIn, ComplaintChatMessage, ComplaintChatSummary, ComplaintDetail,
    ComplaintIn, ComplaintSummary,
)

log = logging.getLogger("routers.complaints")
router = APIRouter(prefix="/complaints", tags=["complaints"])
TEAM = "complaint_team"
MAX_REPORT_MESSAGES = 80
MAX_REPORT_CHARS = 30_000


def _case(db: Session, case_id: int):
    return db.execute(text(
        "SELECT cc.*, t.name AS teacher_name, p.name AS parent_name FROM complaint_cases cc "
        "JOIN users t ON t.id = cc.teacher_id JOIN users p ON p.id = cc.parent_id "
        "WHERE cc.id = :id"), {"id": case_id}).mappings().first()


def _sources(db: Session, case_id: int):
    return db.execute(text(
        "SELECT x.conversation_id AS id, x.max_message_id, c.student_name, c.status "
        "FROM complaint_case_conversations x JOIN conversations c ON c.id = x.conversation_id "
        "WHERE x.case_id = :id ORDER BY x.selected_order"), {"id": case_id}).mappings().all()


def _source_messages(db: Session, source):
    if source["max_message_id"] is None:
        return []
    return db.execute(text(
        "SELECT * FROM messages WHERE conversation_id = :c AND id <= :m ORDER BY id"),
        {"c": source["id"], "m": source["max_message_id"]}).mappings().all()


def _summary(db: Session, case) -> dict:
    d = dict(case)
    d["conversation_ids"] = [s["id"] for s in _sources(db, case["id"])]
    d.pop("report", None)
    d.pop("report_error", None)
    return d


def _authorized_case(db: Session, case_id: int, user):
    case = _case(db, case_id)
    if case is None or (user["role"] != TEAM and user["id"] != case["teacher_id"]):
        raise HTTPException(404, "민원 신청서를 찾을 수 없습니다")
    return case


def _team_ids(db: Session) -> list[int]:
    return crud.user_ids_with_role(db, TEAM)


def _parent_contacted(db: Session, case_id: int) -> bool:
    return bool(db.execute(text(
        "SELECT 1 FROM complaint_case_chat_messages m JOIN users u ON u.id = m.author_id "
        "WHERE m.case_id = :id AND m.channel = 'parent' AND u.role = 'complaint_team' LIMIT 1"),
        {"id": case_id}).scalar())


def _notify(db: Session, case, *, parent: bool = False) -> None:
    ids = [case["teacher_id"], *_team_ids(db)]
    if parent and _parent_contacted(db, case["id"]):
        ids.append(case["parent_id"])
    hub.notify_users(list(dict.fromkeys(ids)), {"type": "complaints", "case_id": case["id"]})


def _report_in_background(case_id: int, requested_at) -> None:
    """제출 당시 고정한 메시지만 보고 AI 보고서를 만든다. Claude 호출 중에는 DB 연결을 잡지 않는다."""
    try:
        if not messages_router._refine_state["enabled"]:
            result = {"status": "failed", "report": None, "error": "Claude 가 꺼져 있습니다"}
        else:
            with SessionLocal() as db:
                case = _case(db, case_id)
                sources = _sources(db, case_id)
                history = [
                    {"id": m["id"], "conversation_id": s["id"],
                     "who": "parent" if m["sender_id"] == case["parent_id"] else "teacher",
                     "text": m["raw_text"], "at": m["created_at"]}
                    for s in sources for m in _source_messages(db, s)
                ]
                history.sort(key=lambda h: (h["at"], h["id"]))
                roster = class_roster(crud.student_names(db, case["teacher_id"]), sources[0]["student_name"])
                roster = list(dict.fromkeys([*roster, *(s["student_name"] for s in sources)]))
                adults = crud.adult_names(db)
                reason = case["reason"]
            from app.ai.case_report import write_case_report

            result = write_case_report(history, reason, roster, adults)
    except Exception as e:
        log.exception("민원 보고서 생성 실패 (case %s)", case_id)
        result = {"status": "failed", "report": None, "error": f"보고서 작성 중 오류 ({type(e).__name__})"}
    try:
        with SessionLocal() as db:
            changed = db.execute(text(
                "UPDATE complaint_cases SET report_status = :status, report = CAST(:report AS JSONB), "
                "report_error = :error WHERE id = :id AND report_requested_at = :requested_at "
                "RETURNING id"),
                {"status": result["status"],
                 "report": json.dumps(result["report"], ensure_ascii=False) if result.get("report") is not None else None,
                 "error": result.get("error"), "id": case_id, "requested_at": requested_at}).scalar()
            db.commit()
            if changed is None:
                return  # 재시도가 시작된 뒤 늦게 끝난 이전 보고서 결과는 버린다.
            case = _case(db, case_id)
            if case:
                _notify(db, case)
    except Exception:
        log.exception("민원 보고서 저장 실패 (case %s)", case_id)


@router.post("", response_model=ComplaintSummary, status_code=202)
def submit_complaint(body: ComplaintIn, background: BackgroundTasks,
                     db: Session = Depends(get_db), user=Depends(current_user)):
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 민원을 이관할 수 있습니다")
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(400, "이관 사유를 적어 주세요")
    ids = body.conversation_ids
    if len(set(ids)) != len(ids):
        raise HTTPException(400, "같은 대화를 두 번 선택할 수 없습니다")
    rows = db.execute(text(
        "SELECT c.id, c.teacher_id, c.parent_id, "
        "(SELECT max(m.id) FROM messages m WHERE m.conversation_id = c.id) AS max_message_id "
        "FROM conversations c WHERE c.id = ANY(:ids)"), {"ids": ids}).mappings().all()
    if len(rows) != len(ids) or any(r["teacher_id"] != user["id"] for r in rows):
        raise HTTPException(404, "선택한 대화를 찾을 수 없습니다")
    parent_ids = {r["parent_id"] for r in rows}
    if len(parent_ids) != 1:
        raise HTTPException(400, "같은 학부모와 나눈 대화만 함께 선택해 주세요")
    parent_id = next(iter(parent_ids))
    message_count, character_count, has_parent_message = 0, len(reason), False
    for row in rows:
        if row["max_message_id"] is None:
            continue
        stats = db.execute(text(
            "SELECT count(*) AS n, COALESCE(sum(length(raw_text)), 0) AS chars, "
            "COALESCE(bool_or(sender_id = :p), false) AS has_parent "
            "FROM messages WHERE conversation_id = :c AND id <= :max"),
            {"c": row["id"], "p": parent_id, "max": row["max_message_id"]}).mappings().one()
        message_count += stats["n"]
        character_count += stats["chars"]
        has_parent_message = has_parent_message or stats["has_parent"]
    if not has_parent_message:
        raise HTTPException(400, "학부모 메시지가 있는 대화를 선택해 주세요")
    if message_count > MAX_REPORT_MESSAGES or character_count > MAX_REPORT_CHARS:
        raise HTTPException(400, "한 신청서에는 메시지 80건, 원문과 사유 합계 3만 자까지만 담을 수 있습니다")
    by_id = {r["id"]: r for r in rows}
    case_id = db.execute(text(
        "INSERT INTO complaint_cases (teacher_id, parent_id, reason) VALUES (:t, :p, :r) RETURNING id"),
        {"t": user["id"], "p": parent_id, "r": reason}).scalar_one()
    for position, conv_id in enumerate(ids):
        db.execute(text(
            "INSERT INTO complaint_case_conversations (case_id, conversation_id, selected_order, max_message_id) "
            "VALUES (:case, :conv, :pos, :max)"),
            {"case": case_id, "conv": conv_id, "pos": position, "max": by_id[conv_id]["max_message_id"]})
    db.commit()
    case = _case(db, case_id)
    _notify(db, case)
    background.add_task(_report_in_background, case_id, case["report_requested_at"])
    return _summary(db, case)


@router.get("", response_model=list[ComplaintSummary])
def list_complaints(db: Session = Depends(get_db), user=Depends(current_user)):
    if user["role"] == TEAM:
        where, params = "", {}
    elif user["role"] == "teacher":
        where, params = "WHERE cc.teacher_id = :uid", {"uid": user["id"]}
    else:
        raise HTTPException(403, "교사 또는 민원 담당자만 볼 수 있습니다")
    rows = db.execute(text(
        "SELECT cc.*, t.name AS teacher_name, p.name AS parent_name FROM complaint_cases cc "
        "JOIN users t ON t.id = cc.teacher_id JOIN users p ON p.id = cc.parent_id "
        f"{where} ORDER BY cc.created_at DESC, cc.id DESC"), params).mappings().all()
    return [_summary(db, r) for r in rows]


@router.get("/chats/{channel}", response_model=list[ComplaintChatSummary])
def list_chats(channel: Literal["parent", "teacher"], db: Session = Depends(get_db), user=Depends(current_user)):
    if user["role"] == TEAM:
        where, params = "", {}
    elif user["role"] == channel:
        column = "parent_id" if channel == "parent" else "teacher_id"
        where, params = f"AND cc.{column} = :uid", {"uid": user["id"]}
    else:
        raise HTTPException(403, "이 채팅 목록을 볼 수 없습니다")
    rows = db.execute(text(
        "SELECT cc.*, t.name AS teacher_name, p.name AS parent_name FROM complaint_cases cc "
        "JOIN users t ON t.id = cc.teacher_id JOIN users p ON p.id = cc.parent_id "
        f"WHERE cc.status IN ('in_progress', 'completed') {where} "
        "ORDER BY cc.created_at DESC, cc.id DESC"), params).mappings().all()
    out = []
    for case in rows:
        if user["role"] == "parent" and not _parent_contacted(db, case["id"]):
            continue  # 담당자가 먼저 연락하기 전에는 신청 사실을 알리지 않는다.
        last = db.execute(text(
            "SELECT body, created_at FROM complaint_case_chat_messages "
            "WHERE case_id = :id AND channel = :ch ORDER BY id DESC LIMIT 1"),
            {"id": case["id"], "ch": channel}).mappings().first()
        counterpart = case["parent_name"] if user["role"] == TEAM and channel == "parent" else (
            case["teacher_name"] if user["role"] == TEAM else "민원 담당자")
        out.append({"case_id": case["id"], "channel": channel, "status": case["status"],
                    "counterpart_name": counterpart, "last_message_at": last["created_at"] if last else None,
                    "last_message_text": last["body"] if last else None})
    return out


@router.get("/{case_id}", response_model=ComplaintDetail)
def get_complaint(case_id: int, response: Response, db: Session = Depends(get_db), user=Depends(current_user)):
    case = _authorized_case(db, case_id, user)
    response.headers["Cache-Control"] = "no-store"
    if user["role"] == TEAM and case["status"] == "received":
        db.execute(text(
            "UPDATE complaint_cases SET status = 'in_progress', started_at = now() "
            "WHERE id = :id AND status = 'received'"), {"id": case_id})
        db.commit()
        case = _case(db, case_id)
        _notify(db, case)
    team = user["role"] == TEAM
    conversations = []
    for source in _sources(db, case_id):
        messages = []
        for m in _source_messages(db, source):
            who = "parent" if m["sender_id"] == case["parent_id"] else "teacher"
            if team:
                display = m["raw_text"]
                raw = m["raw_text"]
                refined = m["refined_text"]
            else:
                visible = messages_router._view(m, user)
                display = visible["raw_text"] if visible["raw_text"] is not None else visible["refined_text"]
                raw = m["raw_text"] if who == "teacher" else None
                refined = visible["refined_text"]
            messages.append({"id": m["id"], "who": who, "text": display, "raw_text": raw,
                             "refined_text": refined, "status": m["status"], "created_at": m["created_at"]})
        conversations.append({"id": source["id"], "student_name": source["student_name"],
                              "status": source["status"], "messages": messages})
    return {**_summary(db, case), "report": case["report"] if team else None,
            "report_error": case["report_error"] if team else None, "conversations": conversations}


@router.post("/{case_id}/complete", response_model=ComplaintSummary)
def complete_complaint(case_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    if user["role"] != TEAM:
        raise HTTPException(403, "민원 담당자만 처리 완료할 수 있습니다")
    case = _case(db, case_id)
    if case is None:
        raise HTTPException(404, "민원 신청서를 찾을 수 없습니다")
    if case["status"] == "received":
        raise HTTPException(409, "신청서를 먼저 열람해 주세요")
    if case["status"] == "in_progress":
        db.execute(text(
            "UPDATE complaint_cases SET status = 'completed', completed_at = now() "
            "WHERE id = :id AND status = 'in_progress'"), {"id": case_id})
        db.commit()
        case = _case(db, case_id)
        _notify(db, case, parent=True)
    return _summary(db, case)


@router.post("/{case_id}/report/retry", response_model=ComplaintSummary, status_code=202)
def retry_report(case_id: int, background: BackgroundTasks,
                 db: Session = Depends(get_db), user=Depends(current_user)):
    """실패 또는 서버 중단으로 10분 넘게 멈춘 보고서만 다시 생성한다."""
    if user["role"] != TEAM:
        raise HTTPException(403, "민원 담당자만 보고서를 다시 만들 수 있습니다")
    case = _case(db, case_id)
    if case is None:
        raise HTTPException(404, "민원 신청서를 찾을 수 없습니다")
    changed = db.execute(text(
        "UPDATE complaint_cases SET report_status = 'pending', report = NULL, report_error = NULL, "
        "report_requested_at = now() WHERE id = :id AND "
        "(report_status = 'failed' OR (report_status = 'pending' AND "
        "report_requested_at < now() - INTERVAL '10 minutes')) RETURNING id"),
        {"id": case_id}).scalar()
    if changed is None:
        raise HTTPException(409, "보고서가 이미 생성되었거나 아직 생성 중입니다")
    db.commit()
    case = _case(db, case_id)
    _notify(db, case)
    background.add_task(_report_in_background, case_id, case["report_requested_at"])
    return _summary(db, case)


def _chat_case(db: Session, case_id: int, channel: str, user):
    case = _case(db, case_id)
    if case is None:
        raise HTTPException(404, "채팅을 찾을 수 없습니다")
    if user["role"] != TEAM:
        owner = case["parent_id"] if channel == "parent" else case["teacher_id"]
        if user["role"] != channel or user["id"] != owner:
            raise HTTPException(404, "채팅을 찾을 수 없습니다")
    if case["status"] == "received":
        raise HTTPException(404, "채팅을 찾을 수 없습니다")
    if user["role"] == "parent" and not _parent_contacted(db, case_id):
        raise HTTPException(404, "채팅을 찾을 수 없습니다")
    return case


@router.get("/{case_id}/chats/{channel}/messages", response_model=list[ComplaintChatMessage])
def chat_messages(case_id: int, channel: Literal["parent", "teacher"],
                  db: Session = Depends(get_db), user=Depends(current_user)):
    _chat_case(db, case_id, channel, user)
    rows = db.execute(text(
        "SELECT m.id, m.case_id, m.channel, m.author_id, u.name AS author_name, "
        "u.role AS author_role, m.body AS text, m.created_at "
        "FROM complaint_case_chat_messages m JOIN users u ON u.id = m.author_id "
        "WHERE m.case_id = :id AND m.channel = :ch ORDER BY m.id"),
        {"id": case_id, "ch": channel}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{case_id}/chats/{channel}/messages", response_model=ComplaintChatMessage, status_code=201)
def send_chat_message(case_id: int, channel: Literal["parent", "teacher"], body: ComplaintChatIn,
                      db: Session = Depends(get_db), user=Depends(current_user)):
    case = _chat_case(db, case_id, channel, user)
    # 완료 처리와 메시지 전송이 동시에 들어와도, 완료된 채팅에 새 글이 남지 않게 직렬화한다.
    current_status = db.execute(text("SELECT status FROM complaint_cases WHERE id = :id FOR UPDATE"),
                                {"id": case_id}).scalar_one()
    if current_status != "in_progress":
        raise HTTPException(409, "처리 완료된 채팅은 읽기만 할 수 있습니다")
    message = body.text.strip()
    if not message:
        raise HTTPException(400, "메시지를 적어 주세요")
    msg_id = db.execute(text(
        "INSERT INTO complaint_case_chat_messages (case_id, channel, author_id, body) "
        "VALUES (:id, :ch, :author, :body) RETURNING id"),
        {"id": case_id, "ch": channel, "author": user["id"], "body": message}).scalar_one()
    db.commit()
    row = db.execute(text(
        "SELECT m.id, m.case_id, m.channel, m.author_id, u.name AS author_name, "
        "u.role AS author_role, m.body AS text, m.created_at "
        "FROM complaint_case_chat_messages m JOIN users u ON u.id = m.author_id WHERE m.id = :id"),
        {"id": msg_id}).mappings().one()
    audience = [*_team_ids(db), case["parent_id"] if channel == "parent" else case["teacher_id"]]
    hub.notify_users(list(dict.fromkeys(audience)), {"type": "complaints", "case_id": case_id})
    return dict(row)
