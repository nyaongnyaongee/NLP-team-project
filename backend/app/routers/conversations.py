# 대화 목록 · 만들기 · 닫기, 닫을 때 할 일 · 일정 추출(C)  [채원]  (시험용으로 재관이 채움)
# 닫기: 교사가 대화를 닫으면 백그라운드에서 ai/extract.py 가 할 일 · 일정 후보를 뽑아 tasks 에 넣는다.
#   상태는 conversations.extract = {"status": "pending" | "done" | "failed", "error", "count", "at"}.
#   종료된 대화에는 아무도 글을 보낼 수 없다(messages.py, 409). 「다시 뽑기」는 후보만 새로 뽑고, 추가 · 완료한 것은 둔다.
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
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
from app.schemas.todo import ConversationCloseIn, ConversationIn, ConversationStartIn, StartableOut

log = logging.getLogger("routers.conversations")
router = APIRouter(tags=["conversations"])

HISTORY_LIMIT = 40  # 추출은 초안보다 길게 본다 (대화 전체에서 챙길 것을 찾으므로)


def _conv_view(conv, user, db: Session) -> dict:
    d = dict(conv)
    # 대화 상대 이름: 학부모 화면 「김민지 선생님」, 교사 화면 「박서연 (박지민 부모)」
    d.setdefault("teacher_name", crud.user_name(db, d["teacher_id"]))
    d.setdefault("parent_name", crud.user_name(db, d["parent_id"]))  # 교사 화면 「박서연 (박지민 부모)」
    d.pop("teacher_deleted_at", None)  # 상대가 목록에서 지웠는지는 서로 모르게 (내가 지운 대화는 목록에 안 나옴)
    d.pop("parent_deleted_at", None)
    d.pop("teacher_read_id", None)  # 안 읽은 수는 목록의 unread 로 (내 것만)
    d.pop("parent_read_id", None)
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


PREVIEW_CHARS = 60   # 목록에 보이는 마지막 글 길이
SUMMARY_REQUESTS = 2  # 목록에 보이는 요청 수


def _preview(conv, msgs, user) -> dict:
    """목록 한 줄 요약. Claude 를 새로 부르지 않고 정제(A) 때 나온 분석을 다시 쓴다.
    - last: 마지막 글을 보는 사람 기준으로 (_view 를 거침 → 교사는 정제문 · 통과 원문, 학부모는 자기 원문 · 교사 글)
      처리 전 · 실패한 학부모 글은 교사에게 내용이 없으므로 last.text = None, last.status 로 화면이 문구를 고른다
    - summary · topic: 교사 · 학부모 둘 다. 정제가 끝난 학부모 글 중 summary 가 있는 첫 글 (문의마다 대화방이라 첫 글이 그 대화의 일)
      학부모에게는 자기 글의 요약이다. 정제문 · 인용 · 위협 목록은 여전히 안 준다 (요약에는 거친 말이 없게 프롬프트가 쓴다)
    - requests: summary 가 없는 예전 글용 — 요청이 있는 가장 최근 글 (없으면 가장 최근 글의 주제)"""
    out: dict = {"last": None}
    if msgs:
        m = messages_router._view(msgs[-1], user)
        body = m["raw_text"] if m["raw_text"] is not None else m["refined_text"]
        if body is not None:
            body = " ".join(body.split())
            body = body if len(body) <= PREVIEW_CHARS else body[:PREVIEW_CHARS].rstrip() + "…"
        out["last"] = {"text": body, "mine": msgs[-1]["sender_id"] == user["id"], "status": msgs[-1]["status"]}
    analyses = [m["analysis"] for m in msgs if m["sender_id"] == conv["parent_id"] and m["status"] == "done"
                and isinstance(m["analysis"], dict)]
    out["summary"], out["topic"], out["requests"] = None, None, []
    first = next((a for a in analyses if isinstance(a.get("summary"), str) and a["summary"]), None)
    if first:
        out["summary"], out["topic"] = first["summary"], first.get("topic")
        return out
    for a in reversed(analyses):
        out["topic"] = out["topic"] or a.get("topic")
        reqs = [r.get("text") for r in a.get("requests") or [] if isinstance(r, dict) and r.get("text")]
        if reqs:
            out["topic"] = a.get("topic") or out["topic"]
            out["requests"] = list(dict.fromkeys(reqs))[:SUMMARY_REQUESTS]
            break
    return out


@router.get("/conversations")
def my_conversations(db: Session = Depends(get_db), user=Depends(current_user)):
    convs = crud.list_conversations(db, user["id"])
    return [{**_conv_view(c, user, db), "preview": _preview(c, crud.list_messages(db, c["id"]), user)} for c in convs]


@router.get("/conversations/startable", response_model=list[StartableOut])
def startable(db: Session = Depends(get_db), user=Depends(current_user)):
    """대화를 시작할 수 있는 학생. 교사 = 반 학생 중 학부모가 등록된 학생, 학부모 = 자기 아이."""
    if user["role"] not in ("teacher", "parent"):
        raise HTTPException(403, "교사 · 학부모만 대화를 시작할 수 있습니다")
    return [dict(r) for r in crud.startable_students(db, user)]


@router.post("/conversations/start", status_code=201)
def start_conversation(body: ConversationStartIn, db: Session = Depends(get_db),
                       user=Depends(current_user)):
    """학생 하나로 새 대화방을 연다 (교사 · 학부모 둘 다). 문의마다 새 대화 — 열린 대화가 있어도 새로 만든다."""
    if user["role"] not in ("teacher", "parent"):
        raise HTTPException(403, "교사 · 학부모만 대화를 시작할 수 있습니다")
    row = next((r for r in crud.startable_students(db, user) if r["student_id"] == body.student_id), None)
    if row is None:
        raise HTTPException(404, "대화를 시작할 수 있는 학생이 아닙니다 (학부모가 등록되지 않았거나 내 학생이 아님)")
    conv = crud.create_conversation(db, row["teacher_id"], row["parent_id"], row["student_name"])
    hub.notify_conversation(conv["id"])  # 상대 화면의 대화 목록도 다시 불러오게
    return _conv_view(conv, user, db)


@router.get("/conversations/{conv_id}")
def one_conversation(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    return _conv_view(messages_router._my_conversation(db, conv_id, user), user, db)


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
    return _conv_view(conv, user, db)


@router.post("/conversations/{conv_id}/close", status_code=202)
def close_conversation(conv_id: int, background: BackgroundTasks, body: ConversationCloseIn | None = None,
                       db: Session = Depends(get_db), user=Depends(current_user)):
    """대화 닫기. 본문 {"extract": true}(기본 · 본문 없음)이면 백그라운드에서 할 일 · 일정 후보를 뽑고,
    false 면 닫기만 한다 (Claude 안 부름). 이미 닫혀 있으면 그대로 돌려준다."""
    extract = body.extract if body else True
    conv = messages_router._my_conversation(db, conv_id, user)
    _need_owner_teacher(conv, user)
    if conv["status"] == "closed":
        return _conv_view(conv, user, db)
    conv = crud.set_conversation_status(db, conv_id, "closed", extract)
    hub.notify_conversation(conv_id)
    if extract:
        background.add_task(_extract_in_background, conv_id)
    return _conv_view(conv, user, db)


@router.post("/conversations/{conv_id}/read", status_code=204)
def read_conversation(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """대화방을 보고 있을 때 화면이 부른다 → 지금까지 온 메시지를 읽음으로. 목록의 unread 가 0 이 된다."""
    conv = messages_router._my_conversation(db, conv_id, user)
    crud.mark_read(db, conv_id, "teacher" if user["id"] == conv["teacher_id"] else "parent")


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """내 목록에서 지우기 (종료된 대화만, 담임 · 학부모 각자). DB 에는 남는다 — 상대 목록 · 민원대응팀 보고서 · 할 일은 그대로."""
    conv = messages_router._my_conversation(db, conv_id, user)
    if conv["status"] != "closed":
        raise HTTPException(409, "종료된 대화만 지울 수 있습니다")
    crud.hide_conversation(db, conv_id, "teacher" if user["id"] == conv["teacher_id"] else "parent")
    hub.notify_conversation(conv_id)


@router.post("/conversations/{conv_id}/extract", status_code=202)
def extract_again(conv_id: int, background: BackgroundTasks, db: Session = Depends(get_db),
                  user=Depends(current_user)):
    """「다시 뽑기」 · 「할 일 · 일정 뽑기」: 닫힌 대화에서 후보를 새로 뽑는다 (실패했을 때 · 스위치를 켠 뒤 · 뽑지 않고 닫았을 때)."""
    conv = messages_router._my_conversation(db, conv_id, user)
    _need_owner_teacher(conv, user)
    if conv["status"] != "closed":
        raise HTTPException(409, "닫힌 대화에서만 뽑을 수 있습니다")
    if (conv["extract"] or {}).get("status") == "pending":
        return _conv_view(conv, user, db)  # 이미 뽑는 중
    conv = crud.set_conversation_status(db, conv_id, "closed")  # extract 를 pending 으로
    hub.notify_conversation(conv_id)
    background.add_task(_extract_in_background, conv_id)
    return _conv_view(conv, user, db)
