# 메시지 전송·조회(A), 원문 보기  [채원]
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.schemas.message import MessageIn, MessageOut

router = APIRouter(tags=["messages"])


def _my_conversation(db: Session, conv_id: int, user):
    conv = crud.get_conversation(db, conv_id)
    if conv is None or user["id"] not in (conv["teacher_id"], conv["parent_id"]):
        raise HTTPException(404, "대화를 찾을 수 없습니다")
    return conv


@router.get("/conversations")
def my_conversations(db: Session = Depends(get_db), user=Depends(current_user)):
    return [dict(c) for c in crud.list_conversations(db, user["id"])]


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut, status_code=201)
def send_message(conv_id: int, body: MessageIn, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_conversation(db, conv_id, user)
    # 학부모 메시지는 정제 대기(pending), 교사 메시지는 그대로(skip)
    status = "pending" if user["role"] == "parent" else "skip"
    return crud.add_message(db, conv_id, user["id"], body.text, status)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def read_messages(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_conversation(db, conv_id, user)
    return crud.list_messages(db, conv_id)
