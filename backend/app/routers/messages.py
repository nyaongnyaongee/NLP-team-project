# 메시지 전송·조회(A), 원문 보기  [채원]
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.refine import refine_message
from app.ai.roster import class_roster
from app.core.auth import current_user
from app.core.config import settings
from app.db import crud
from app.db.database import SessionLocal, get_db
from app.routers.ws import hub
from app.schemas.message import MessageIn, MessageOut

log = logging.getLogger("routers.messages")
router = APIRouter(tags=["messages"])

_refine_state = {"enabled": settings.refine_enabled}  # 시험 화면의 스위치가 바꾼다 (서버를 다시 켜면 설정값으로 돌아감)


def _my_conversation(db: Session, conv_id: int, user):
    conv = crud.get_conversation(db, conv_id)
    if conv is None or user["id"] not in (conv["teacher_id"], conv["parent_id"]):
        raise HTTPException(404, "대화를 찾을 수 없습니다")
    return conv


def _view(msg, user) -> dict:
    """보는 사람에 맞게 걸러서 돌려준다.
    - 교사가 보낸 글(skip): 양쪽 모두 있는 그대로
    - 학부모 글을 교사가 볼 때: 명시적으로 통과한 글은 원문, 그 외 완료된 글은 정제문. 분석은 둘 다 주되 인용문(quotes)은 뺌
    - 학부모가 자기 글을 볼 때: 자기가 쓴 원문만 (정제문 · 분석은 교사용이라 뺌)"""
    d = dict(msg)
    if d["status"] == "skip":
        return d
    if user["role"] == "teacher":
        if not _is_passthrough(d):
            d["raw_text"] = None
        if d.get("analysis"):
            d["analysis"] = {k: v for k, v in d["analysis"].items() if k != "quotes"}
    else:
        d["refined_text"] = None
        d["analysis"] = None
    return d


def _is_passthrough(msg) -> bool:
    """완료 상태이고 정제 여부(needs_refinement 열)가 명시적으로 false 여야 원문을 보여 준다."""
    return msg["status"] == "done" and msg.get("refined_text") is None and msg.get("needs_refinement") is False


def _result_for_storage(result: dict) -> dict:
    """최상위 판정을 우선하며, 현재 AI 결과의 analysis 안에 실린 판정도 받는다.
    판정은 analysis 에서 빼서 needs_refinement 열로 저장한다 (교사에게 가는 analysis 에 남지 않게).
    통과 판정이면 정제문만 버리고 분석(주제 · 요청 · 위협 · 시한)은 남긴다.
    통과인데 abusive 가 true 면 판정끼리 어긋난 것이라 정제문 쪽으로 처리한다 (거친 원문이 교사에게 가지 않게)."""
    if result["status"] != "done":
        return result
    analysis = dict(result["analysis"]) if isinstance(result.get("analysis"), dict) else {}
    in_analysis = analysis.pop("needs_refinement", None)
    decision = result["needs_refinement"] if "needs_refinement" in result else in_analysis
    if decision is False and not analysis.get("abusive"):
        return {"status": "done", "refined_text": None, "analysis": analysis, "needs_refinement": False,
                "error": None}
    if decision is False:
        log.warning("통과 판정인데 abusive=true → 정제문으로 처리")
    result = {**result, "analysis": analysis, "needs_refinement": True}
    if not isinstance(result.get("refined_text"), str) or not result["refined_text"]:
        return {"status": "failed", "refined_text": None, "analysis": None,
                "error": "정제 결과에 정제문이 없습니다"}
    return result


def _refine_in_background(msg_id: int, raw_text: str, conv_id: int) -> None:
    """응답을 보낸 뒤 돌아간다 (요청의 DB 연결은 이미 닫혔으니 직접 연다).
    명단: 학생 = 그 담임의 반(students, 비어 있으면 ai/sample_roster.json) + 이 대화의 학생, 어른 = 교사 · 학부모 실명(DB users)."""
    try:
        if not _refine_state["enabled"]:  # 꺼져 있으면 Claude 를 부르지 않는다. 켠 뒤 「다시 정제」로 정제할 수 있다
            result = {"status": "failed", "refined_text": None, "analysis": None,
                      "error": "정제가 꺼져 있습니다 (시험용 스위치). 켠 뒤 「다시 정제」를 누르세요"}
        else:
            with SessionLocal() as db:
                adults = crud.adult_names(db)
                conv = crud.get_conversation(db, conv_id)
                roster = class_roster(crud.student_names(db, conv["teacher_id"]), conv["student_name"])
            result = refine_message(raw_text, roster, adults)  # 몇 초 걸리므로 DB 연결을 잡고 있지 않는다
    except Exception as e:  # 명단 조회 등 예기치 못한 오류도 pending 으로 멈추지 않게 실패로 기록
        log.exception("정제 준비 중 오류")
        result = {"status": "failed", "refined_text": None, "analysis": None, "error": f"정제 중 오류 ({type(e).__name__})"}
    try:
        with SessionLocal() as db:
            crud.save_refine_result(db, msg_id, _result_for_storage(result))
    except Exception:
        log.exception("정제 결과 저장 실패 (message %s)", msg_id)
        return
    hub.notify_conversation(conv_id)


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut, status_code=201)
def send_message(conv_id: int, body: MessageIn, background: BackgroundTasks,
                 db: Session = Depends(get_db), user=Depends(current_user)):
    _my_conversation(db, conv_id, user)
    # 학부모 메시지는 정제 대기(pending) → 백그라운드에서 정제, 교사 메시지는 그대로(skip)
    status = "pending" if user["role"] == "parent" else "skip"
    crud.reopen_if_closed(db, conv_id)  # 닫힌 대화에 새 글이 오면 다시 연다 (뽑아 둔 할 일 · 일정은 그대로)
    msg = crud.add_message(db, conv_id, user["id"], body.text, status)
    hub.notify_conversation(conv_id)
    if status == "pending":
        background.add_task(_refine_in_background, msg["id"], body.text, conv_id)
    return _view(msg, user)


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
        return _view(msg, user)  # 이미 정제 중
    raw_text = msg["raw_text"]
    msg = crud.set_message_pending(db, msg_id)
    hub.notify_conversation(conv_id)
    background.add_task(_refine_in_background, msg_id, raw_text, conv_id)
    return _view(msg, user)


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
def read_messages(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_conversation(db, conv_id, user)
    return [_view(m, user) for m in crud.list_messages(db, conv_id)]


# ---- 시험용 스위치: dev.py 로 켰을 때(DEV_TOOLS=1)만 열린다. 일반 서버에서는 404

class RefineSwitch(BaseModel):
    enabled: bool


def _need_dev_tools():
    if not settings.dev_tools:
        raise HTTPException(404, "Not Found")


@router.get("/dev/refine")
def dev_refine_state():
    _need_dev_tools()
    return {"enabled": _refine_state["enabled"]}


@router.post("/dev/refine")
def dev_refine_set(body: RefineSwitch):
    _need_dev_tools()
    _refine_state["enabled"] = body.enabled
    log.info("정제 %s", "켬" if body.enabled else "끔")
    return {"enabled": _refine_state["enabled"]}


@router.post("/dev/reset")
def dev_reset(db: Session = Depends(get_db)):
    """시험용 초기화: 모든 대화의 메시지 · 할 일 · 일정 · 공지를 지우고 대화를 다시 연다 (계정 · 대화는 둔다)."""
    _need_dev_tools()
    conv_ids = crud.dev_reset(db)
    log.info("시험용 초기화: 대화 %d개 비움", len(conv_ids))
    for cid in conv_ids:
        hub.notify_conversation(cid)  # 열려 있는 화면들이 바로 비워진다
    hub.notify_users(list(hub.conns), {"type": "notice", "notice_id": None})  # 공지 목록도
    return {"conversations": len(conv_ids)}
