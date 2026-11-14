# 답장·공지 초안(B)  [채원]  (시험용으로 재관이 채움)
# 버튼으로 만든 초안은 저장하지 않는다. 교사가 고쳐서 보통 메시지(POST /conversations/{id}/messages)로 보낸다.
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.draft import draft_notice, draft_reply
from app.ai.roster import class_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers import messages as messages_router

router = APIRouter(tags=["drafts"])

HISTORY_LIMIT = 20  # 최근 메시지 몇 개까지 Claude 에게 보여 줄지


class ReplyDraftIn(BaseModel):
    memo: str | None = Field(None, max_length=1000)  # 교사가 이번 답장에 담고 싶은 사실 · 결정


class ReplyDraftOut(BaseModel):
    draft: str
    check: list[str]  # 보내기 전 교사가 확인할 것 ([ ] 자리, 답하지 않은 요청, 위협 …)


class NoticeDraftIn(BaseModel):
    points: str = Field(..., min_length=1, max_length=2000)


class NoticeDraftOut(BaseModel):
    title: str
    body: str
    check: list[str]


def _need_teacher(user):
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 초안을 만들 수 있습니다")


def _need_claude():
    # 시험 화면의 스위치가 꺼져 있으면 초안도 Claude 를 부르지 않는다 (일반 서버에서는 REFINE_ENABLED 기본 true)
    if not messages_router._refine_state["enabled"]:
        raise HTTPException(503, "Claude 가 꺼져 있습니다 (시험용 스위치)")


def _history(msgs, parent_id: int, limit: int = HISTORY_LIMIT) -> list[dict]:
    """교사가 볼 수 있는 글만: 통과한 학부모 글은 원문, 정제한 글은 정제문. 미처리 글은 뺀다.
    추출(C)도 같이 쓴다 (at = 보낸 시각, 「내일」을 날짜로 바꿀 때)."""
    out = []
    for m in msgs:
        if m["status"] == "skip":
            out.append({"who": "teacher", "text": m["raw_text"], "at": m["created_at"]})
        elif m["status"] == "done" and m["sender_id"] == parent_id:
            text = m["raw_text"] if messages_router._is_passthrough(m) else m["refined_text"]
            if text is not None:
                out.append({"who": "parent", "text": text, "at": m["created_at"]})
    return out[-limit:]


@router.post("/conversations/{conv_id}/draft", response_model=ReplyDraftOut)
def make_reply_draft(conv_id: int, body: ReplyDraftIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """답장 초안. 몇 초 걸린다 (Claude 응답을 기다렸다가 돌려줌)."""
    conv = messages_router._my_conversation(db, conv_id, user)
    _need_teacher(user)
    history = _history(crud.list_messages(db, conv_id), conv["parent_id"])
    if not any(h["who"] == "parent" for h in history):
        raise HTTPException(409, "답장할 학부모 메시지가 없습니다 (처리 완료된 메시지가 있어야 합니다)")
    _need_claude()
    adults = crud.adult_names(db)
    roster = class_roster(crud.student_names(db, conv["teacher_id"]), conv["student_name"])
    db.close()  # Claude 를 기다리는 동안 DB 연결을 잡고 있지 않는다
    result = draft_reply(history, body.memo, roster, adults)
    if result["status"] != "done":
        raise HTTPException(502, "초안을 만들지 못했습니다: " + result["error"])
    return {"draft": result["draft"], "check": result["check"]}


@router.post("/drafts/notice", response_model=NoticeDraftOut)
def make_notice_draft(body: NoticeDraftIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """공지 초안. 공지 테이블은 아직 없어서 초안만 돌려준다."""
    _need_teacher(user)
    _need_claude()
    adults = crud.adult_names(db)
    roster = class_roster(crud.student_names(db, user["id"]))
    db.close()
    result = draft_notice(body.points, roster, adults)
    if result["status"] != "done":
        raise HTTPException(502, "초안을 만들지 못했습니다: " + result["error"])
    return {"title": result["title"], "body": result["body"], "check": result["check"]}
