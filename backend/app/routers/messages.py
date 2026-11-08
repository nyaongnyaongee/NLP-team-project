# 메시지 전송·조회(A), 원문 보기  [채원]
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.refine import refine_message
from app.ai.roster import load_sample_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import SessionLocal, get_db
from app.schemas.message import MessageIn, MessageOut

log = logging.getLogger("routers.messages")
router = APIRouter(tags=["messages"])


def _my_conversation(db: Session, conv_id: int, user):
    conv = crud.get_conversation(db, conv_id)
    if conv is None or user["id"] not in (conv["teacher_id"], conv["parent_id"]):
        raise HTTPException(404, "대화를 찾을 수 없습니다")
    return conv


def _refine_in_background(msg_id: int, raw_text: str) -> None:
    """응답을 보낸 뒤 돌아간다 (요청의 DB 연결은 이미 닫혔으니 직접 연다).
    명단(시연용 고정): 학생 = ai/sample_roster.json 20명, 어른 = 교사 · 학부모 실명(DB users)."""
    try:
        with SessionLocal() as db:
            adults = crud.adult_names(db)
        result = refine_message(raw_text, load_sample_roster(), adults)  # 몇 초 걸리므로 DB 연결을 잡고 있지 않는다
    except Exception as e:  # 명단 조회 등 예기치 못한 오류도 pending 으로 멈추지 않게 실패로 기록
        log.exception("정제 준비 중 오류")
        result = {"status": "failed", "refined_text": None, "analysis": None, "error": f"정제 중 오류 ({type(e).__name__})"}
    try:
        with SessionLocal() as db:
            crud.save_refine_result(db, msg_id, result)
    except Exception:
        log.exception("정제 결과 저장 실패 (message %s)", msg_id)


@router.get("/conversations")
def my_conversations(db: Session = Depends(get_db), user=Depends(current_user)):
    return [dict(c) for c in crud.list_conversations(db, user["id"])]


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut, status_code=201)
def send_message(conv_id: int, body: MessageIn, background: BackgroundTasks,
                 db: Session = Depends(get_db), user=Depends(current_user)):
    _my_conversation(db, conv_id, user)
    # 학부모 메시지는 정제 대기(pending) → 백그라운드에서 정제, 교사 메시지는 그대로(skip)
    status = "pending" if user["role"] == "parent" else "skip"
    msg = crud.add_message(db, conv_id, user["id"], body.text, status)
    if status == "pending":
        background.add_task(_refine_in_background, msg["id"], body.text)
    return msg


@router.post("/conversations/{conv_id}/messages/{msg_id}/refine", response_model=MessageOut, status_code=202)
def refine_again(conv_id: int, msg_id: int, background: BackgroundTasks,
                 db: Session = Depends(get_db), user=Depends(current_user)):
    """「다시 정제」: 교사만, 학부모가 보낸 메시지에만."""
    conv = _my_conversation(db, conv_id, user)
    if user["id"] != conv["teacher_id"]:
        raise HTTPException(403, "교사만 다시 정제할 수 있습니다")
    msg = crud.get_message(db, msg_id)
    if msg is None or msg["conversation_id"] != conv_id or msg["status"] == "skip":
        raise HTTPException(404, "정제할 메시지를 찾을 수 없습니다")
    if msg["status"] == "pending":
        return msg  # 이미 정제 중
    raw_text = msg["raw_text"]
    msg = crud.set_message_pending(db, msg_id)
    background.add_task(_refine_in_background, msg_id, raw_text)
    return msg


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def read_messages(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_conversation(db, conv_id, user)
    return crud.list_messages(db, conv_id)
