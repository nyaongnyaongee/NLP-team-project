# 대화 목록 · 만들기 · 닫기, 닫을 때 할 일 · 일정 추출(C)  [채원]  (시험용으로 재관이 채움)
# 닫기: 교사가 대화를 닫으면 백그라운드에서 ai/extract.py 가 할 일 · 일정 후보를 뽑아 tasks 에 넣는다.
#   상태는 conversations.extract = {"status": "pending" | "done" | "failed", "error", "count", "at"}.
#   닫힌 대화에 누가 메시지를 보내면 다시 열린다(messages.py). 다시 닫으면 후보만 새로 뽑고, 추가 · 완료한 것은 둔다.
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.ai.extract import KST, extract_tasks
from app.ai.roster import class_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import SessionLocal, get_db
from app.routers import drafts as drafts_router
from app.routers import messages as messages_router
from app.routers import reports as reports_router
from app.routers.ws import hub
from app.schemas.todo import ConversationIn, ConversationStartIn, StartableOut

log = logging.getLogger("routers.conversations")
router = APIRouter(tags=["conversations"])

HISTORY_LIMIT = 40  # 추출은 초안보다 길게 본다 (대화 전체에서 챙길 것을 찾으므로)


def _conv_view(conv, user) -> dict:
    d = dict(conv)
    if user["role"] != "teacher":
        d.pop("extract", None)  # 추출 상태는 교사용
        d.pop("report", None)   # 신고 여부도 학부모에게는 주지 않는다
        d.pop("reported_at", None)
    else:
        d["report"] = reports_router.teacher_view(d.get("report"))  # 원문 인용은 뺀다
    return d


def _need_owner_teacher(conv, user):
    if user["id"] != conv["teacher_id"]:
        raise HTTPException(403, "담임 교사만 할 수 있습니다")


def _extract_in_background(conv_id: int) -> None:
    """닫은 뒤 돌아간다. 요청의 DB 연결은 닫혔으니 직접 연다. Claude 를 기다리는 동안 DB 연결을 잡지 않는다."""
    try:
        if not messages_router._refine_state["enabled"]:
            result = {"status": "failed", "tasks": [],
                      "error": "Claude 가 꺼져 있습니다 (시험용 스위치). 켠 뒤 「다시 뽑기」를 누르세요"}
        else:
            with SessionLocal() as db:
                conv = crud.get_conversation(db, conv_id)
                history = drafts_router._history(crud.list_messages(db, conv_id), conv["parent_id"], HISTORY_LIMIT)
                existing = crud.task_titles(db, conv_id, ("added", "done"))
                adults = crud.adult_names(db)
                roster = class_roster(crud.student_names(db, conv["teacher_id"]), conv["student_name"])
            today = datetime.now(KST).date()
            result = extract_tasks(history, today, existing, roster, adults)
    except Exception as e:
        log.exception("추출 준비 중 오류 (conversation %s)", conv_id)
        result = {"status": "failed", "tasks": [], "error": f"추출 중 오류 ({type(e).__name__})"}
    try:
        with SessionLocal() as db:
            crud.save_extract_result(db, conv_id, result)
    except Exception:
        log.exception("추출 결과 저장 실패 (conversation %s)", conv_id)
        return
    hub.notify_conversation(conv_id)


@router.get("/conversations")
def my_conversations(db: Session = Depends(get_db), user=Depends(current_user)):
    return [_conv_view(c, user) for c in crud.list_conversations(db, user["id"])]


@router.get("/conversations/startable", response_model=list[StartableOut])
def startable(db: Session = Depends(get_db), user=Depends(current_user)):
    """대화를 시작할 수 있는 학생. 교사 = 반 학생 중 학부모가 등록된 학생, 학부모 = 자기 아이."""
    if user["role"] not in ("teacher", "parent"):
        raise HTTPException(403, "교사 · 학부모만 대화를 시작할 수 있습니다")
    return [dict(r) for r in crud.startable_students(db, user)]


@router.post("/conversations/start")
def start_conversation(body: ConversationStartIn, response: Response, db: Session = Depends(get_db),
                       user=Depends(current_user)):
    """학생 하나로 대화 시작 (교사 · 학부모 둘 다). 열린 대화가 있으면 그것을 돌려주고(200), 없으면 만든다(201)."""
    if user["role"] not in ("teacher", "parent"):
        raise HTTPException(403, "교사 · 학부모만 대화를 시작할 수 있습니다")
    row = next((r for r in crud.startable_students(db, user) if r["student_id"] == body.student_id), None)
    if row is None:
        raise HTTPException(404, "대화를 시작할 수 있는 학생이 아닙니다 (학부모가 등록되지 않았거나 내 학생이 아님)")
    if row["open_conversation_id"] is not None:
        return _conv_view(crud.get_conversation(db, row["open_conversation_id"]), user)
    conv = crud.create_conversation(db, row["teacher_id"], row["parent_id"], row["student_name"])
    hub.notify_conversation(conv["id"])  # 상대 화면의 대화 목록도 다시 불러오게
    response.status_code = 201
    return _conv_view(conv, user)


@router.get("/conversations/{conv_id}")
def one_conversation(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return _conv_view(messages_router._my_conversation(db, conv_id, user), user)


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """교사가 학부모 한 명과 대화를 연다. 같은 학부모 · 학생의 열린 대화가 있으면 409."""
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 대화를 만들 수 있습니다")
    parent = crud.get_user(db, body.parent_id)
    if parent is None or parent["role"] != "parent":
        raise HTTPException(404, "학부모를 찾을 수 없습니다")
    student = body.student_name.strip()
    for c in crud.list_conversations(db, user["id"]):
        if c["parent_id"] == body.parent_id and c["student_name"] == student and c["status"] == "open":
            raise HTTPException(409, f"이미 열린 대화가 있습니다 (#{c['id']})")
    conv = crud.create_conversation(db, user["id"], body.parent_id, student)
    hub.notify_conversation(conv["id"])
    return _conv_view(conv, user)


@router.post("/conversations/{conv_id}/close", status_code=202)
def close_conversation(conv_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
                       user=Depends(current_user)):
    """대화 닫기 → 백그라운드에서 할 일 · 일정 후보를 뽑는다. 이미 닫혀 있으면 그대로 돌려준다."""
    conv = messages_router._my_conversation(db, conv_id, user)
    _need_owner_teacher(conv, user)
    if conv["status"] == "closed":
        return _conv_view(conv, user)
    conv = crud.set_conversation_status(db, conv_id, "closed")
    hub.notify_conversation(conv_id)
    background.add_task(_extract_in_background, conv_id)
    return _conv_view(conv, user)


@router.post("/conversations/{conv_id}/extract", status_code=202)
def extract_again(conv_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
                  user=Depends(current_user)):
    """「다시 뽑기」: 닫힌 대화에서 후보를 새로 뽑는다 (실패했을 때 · 스위치를 켠 뒤)."""
    conv = messages_router._my_conversation(db, conv_id, user)
    _need_owner_teacher(conv, user)
    if conv["status"] != "closed":
        raise HTTPException(409, "닫힌 대화에서만 뽑을 수 있습니다")
    if (conv["extract"] or {}).get("status") == "pending":
        return _conv_view(conv, user)  # 이미 뽑는 중
    conv = crud.set_conversation_status(db, conv_id, "closed")  # extract 를 pending 으로
    hub.notify_conversation(conv_id)
    background.add_task(_extract_in_background, conv_id)
    return _conv_view(conv, user)
