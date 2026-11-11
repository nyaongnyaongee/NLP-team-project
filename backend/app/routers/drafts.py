# 답장·공지 초안(B)  [채원]  (시험용으로 재관이 채움)
# 버튼으로 만든 초안은 저장하지 않는다. 교사가 고쳐서 보통 메시지(POST /conversations/{id}/messages)로 보낸다.
# 자동 답장 추천: 학부모 메시지가 정제되면 auto_draft 가 메모 없이 초안을 만들어 그 메시지의 analysis.reply_draft 에 붙인다.
#   화면은 마지막 메시지가 학부모 글이면 입력칸 위에 띄운다. 실패하면 {"error": 사유}.
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.draft import draft_notice, draft_reply
from app.ai.roster import load_sample_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import SessionLocal, get_db
from app.routers import messages as messages_router
from app.routers.ws import hub

log = logging.getLogger("routers.drafts")
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
    """교사가 볼 수 있는 글만: 교사 글은 그대로, 학부모 글은 정제된(done) 것의 정제문. 정제 안 된 학부모 글은 뺀다.
    추출(C)도 같이 쓴다 (at = 보낸 시각, 「내일」을 날짜로 바꿀 때)."""
    out = []
    for m in msgs:
        if m["status"] == "skip":
            out.append({"who": "teacher", "text": m["raw_text"], "at": m["created_at"]})
        elif m["status"] == "done" and m["sender_id"] == parent_id:
            out.append({"who": "parent", "text": m["refined_text"], "at": m["created_at"]})
    return out[-limit:]


def auto_draft(msg_id: int, conv_id: int) -> None:
    """정제가 끝난 학부모 메시지에 답장 추천을 붙인다 (백그라운드, 정제 바로 뒤).
    그 뒤에 교사가 이미 답했으면(옛 메시지를 다시 정제한 경우 등) 만들지 않는다."""
    try:
        with SessionLocal() as db:
            msg = crud.get_message(db, msg_id)
            if msg is None or msg["status"] != "done":
                return
            conv = crud.get_conversation(db, msg["conversation_id"])
            all_msgs = crud.list_messages(db, conv["id"])
            if any(m["id"] > msg_id and m["status"] == "skip" for m in all_msgs):
                return
            msgs = [m for m in all_msgs if m["id"] <= msg_id]
            adults = crud.adult_names(db)
        result = draft_reply(_history(msgs, conv["parent_id"]), None, load_sample_roster(), adults)
        draft = ({"draft": result["draft"], "check": result["check"]} if result["status"] == "done"
                 else {"error": result["error"]})
    except Exception as e:
        log.exception("자동 답장 추천 중 오류 (message %s)", msg_id)
        draft = {"error": f"추천 중 오류 ({type(e).__name__})"}
    try:
        with SessionLocal() as db:
            crud.save_reply_draft(db, msg_id, draft)
    except Exception:
        log.exception("자동 답장 추천 저장 실패 (message %s)", msg_id)
        return
    hub.notify_conversation(conv_id)


@router.post("/conversations/{conv_id}/draft", response_model=ReplyDraftOut)
def make_reply_draft(conv_id: int, body: ReplyDraftIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """답장 초안. 몇 초 걸린다 (Claude 응답을 기다렸다가 돌려줌)."""
    conv = messages_router._my_conversation(db, conv_id, user)
    _need_teacher(user)
    history = _history(crud.list_messages(db, conv_id), conv["parent_id"])
    if not any(h["who"] == "parent" for h in history):
        raise HTTPException(409, "답장할 학부모 메시지가 없습니다 (정제된 메시지가 있어야 합니다)")
    _need_claude()
    adults = crud.adult_names(db)
    db.close()  # Claude 를 기다리는 동안 DB 연결을 잡고 있지 않는다
    result = draft_reply(history, body.memo, load_sample_roster(), adults)
    if result["status"] != "done":
        raise HTTPException(502, "초안을 만들지 못했습니다: " + result["error"])
    return {"draft": result["draft"], "check": result["check"]}


@router.post("/drafts/notice", response_model=NoticeDraftOut)
def make_notice_draft(body: NoticeDraftIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """공지 초안. 공지 테이블은 아직 없어서 초안만 돌려준다."""
    _need_teacher(user)
    _need_claude()
    adults = crud.adult_names(db)
    db.close()
    result = draft_notice(body.points, load_sample_roster(), adults)
    if result["status"] != "done":
        raise HTTPException(502, "초안을 만들지 못했습니다: " + result["error"])
    return {"title": result["title"], "body": result["body"], "check": result["check"]}
