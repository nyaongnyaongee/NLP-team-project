# 신고 · 이관(D)  [채원]  (시험용으로 재관이 채움)
# 담임이 대화를 「신고」하면 백그라운드에서 ai/report.py 가 민원대응팀용 보고서를 쓴다.
#   상태는 conversations.report = {"status": "pending" | "done" | "failed", "memo", …보고서 | "error", "at"},
#   처음 신고한 때는 conversations.reported_at (다시 만들어도 안 바뀜). 민원대응팀 화면 = reported_at 이 있는 대화.
#
# 원문: 보고서는 학부모 원문으로 쓰고, 민원대응팀은 원문 · 인용을 모두 본다 (확인 · 조치에 필요해서).
#   담임에게는 지금처럼 원문을 주지 않는다 → 담임이 보는 보고서에서는 인용(incidents[].quote)을 뺀다 (teacher_view).
#   학부모에게는 신고 여부 자체를 주지 않는다 (conversations._conv_view).
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.report import write_report
from app.ai.roster import class_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import SessionLocal, get_db
from app.routers import messages as messages_router
from app.routers.ws import hub
from app.schemas.report import ReportDetail, ReportIn, ReportListItem

log = logging.getLogger("routers.reports")
router = APIRouter(tags=["reports"])

HISTORY_LIMIT = 80  # 보고서는 대화 전체를 본다 (아주 길면 최근 것만)
TEAM = "complaint_team"


def teacher_view(report: dict | None) -> dict | None:
    """담임이 보는 보고서: 원문 인용만 뺀다 (요약 · 심각도 · 어느 메시지가 문제인지는 준다)."""
    if not report:
        return report
    d = dict(report)
    if isinstance(d.get("incidents"), list):
        d["incidents"] = [{k: v for k, v in i.items() if k != "quote"} for i in d["incidents"]]
    return d


def _history(msgs, parent_id: int) -> list[dict]:
    """보고서용: 학부모 글은 상태와 관계없이 원문 (정제 실패 · 처리 전 글도 증거다). 교사 글은 그대로."""
    out = [{"id": m["id"], "who": "parent" if m["sender_id"] == parent_id else "teacher",
            "text": m["raw_text"], "at": m["created_at"]} for m in msgs]
    return out[-HISTORY_LIMIT:]


def _notify(db: Session, conv_id: int) -> None:
    hub.notify_conversation(conv_id)  # 담임 화면 (학부모 화면도 다시 읽지만 신고 정보는 안 받는다)
    hub.notify_users(crud.user_ids_with_role(db, TEAM), {"type": "report", "conversation_id": conv_id})


def _report_in_background(conv_id: int, memo: str | None) -> None:
    """요청의 DB 연결은 닫혔으니 직접 연다. Claude 를 기다리는 동안 DB 연결을 잡지 않는다."""
    try:
        if not messages_router._refine_state["enabled"]:
            result = {"status": "failed", "report": None,
                      "error": "Claude 가 꺼져 있습니다 (시험용 스위치). 켠 뒤 「다시 만들기」를 누르세요"}
        else:
            with SessionLocal() as db:
                conv = crud.get_conversation(db, conv_id)
                history = _history(crud.list_messages(db, conv_id), conv["parent_id"])
                adults = crud.adult_names(db)
                roster = class_roster(crud.student_names(db, conv["teacher_id"]), conv["student_name"])
            result = write_report(history, memo, roster, adults)
    except Exception as e:
        log.exception("보고서 준비 중 오류 (conversation %s)", conv_id)
        result = {"status": "failed", "report": None, "error": f"보고서 작성 중 오류 ({type(e).__name__})"}
    try:
        with SessionLocal() as db:
            crud.save_report_result(db, conv_id, result, memo)
            _notify(db, conv_id)
    except Exception:
        log.exception("보고서 저장 실패 (conversation %s)", conv_id)


@router.post("/conversations/{conv_id}/report", status_code=202)
def report_conversation(conv_id: int, body: ReportIn, background: BackgroundTasks,
                        db: Session = Depends(get_db), user=Depends(current_user)):
    """담임이 신고한다 (이미 신고했으면 「다시 만들기」: 그 사이 메시지까지 넣어 새로 쓴다). 만드는 중이면 그대로 돌려준다."""
    conv = messages_router._my_conversation(db, conv_id, user)
    if user["id"] != conv["teacher_id"]:
        raise HTTPException(403, "담임 교사만 신고할 수 있습니다")
    if (conv["report"] or {}).get("status") == "pending":
        return {"conversation_id": conv_id, "reported_at": conv["reported_at"], "report": teacher_view(conv["report"])}
    memo = (body.memo or "").strip() or None
    conv = crud.set_report_pending(db, conv_id, memo)
    _notify(db, conv_id)
    background.add_task(_report_in_background, conv_id, memo)
    return {"conversation_id": conv_id, "reported_at": conv["reported_at"], "report": teacher_view(conv["report"])}


def _need_team(user):
    if user["role"] != TEAM:
        raise HTTPException(403, "민원대응팀만 볼 수 있습니다")


@router.get("/reports", response_model=list[ReportListItem])
def list_reports(db: Session = Depends(get_db), user=Depends(current_user)):
    _need_team(user)
    out = []
    for c in crud.list_reported(db):
        r = c["report"] or {}
        out.append(ReportListItem(conversation_id=c["id"], teacher_name=c["teacher_name"], parent_name=c["parent_name"],
                                  student_name=c["student_name"], reported_at=c["reported_at"],
                                  status=r.get("status", "pending"), severity=r.get("severity"), summary=r.get("summary")))
    return out


@router.get("/reports/{conv_id}", response_model=ReportDetail)
def one_report(conv_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """보고서 + 대화 전체 (학부모 글 원문 포함)."""
    _need_team(user)
    conv = next((c for c in crud.list_reported(db) if c["id"] == conv_id), None)
    if conv is None:
        raise HTTPException(404, "신고된 대화를 찾을 수 없습니다")
    msgs = [{"id": m["id"], "who": "parent" if m["sender_id"] == conv["parent_id"] else "teacher",
             "raw_text": m["raw_text"], "refined_text": m["refined_text"], "status": m["status"],
             "created_at": m["created_at"]} for m in crud.list_messages(db, conv_id)]
    return ReportDetail(conversation_id=conv_id, teacher_name=conv["teacher_name"], parent_name=conv["parent_name"],
                        student_name=conv["student_name"], reported_at=conv["reported_at"],
                        report=conv["report"] or {"status": "pending"}, messages=msgs)
