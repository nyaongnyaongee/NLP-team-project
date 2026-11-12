# 공지사항  [채원]  (시험용으로 재관이 채움)
# 교사: 쓰기(draft) → 고치기 → [보내기](sent). 보낸 공지는 고치거나 지울 수 없다.
# 받는 사람 = 그 교사와 대화가 있는 학부모 전부 (DB 에 「반」 이 없어서). 학부모는 보낸 공지만 본다.
# 초안(Claude)은 POST /drafts/notice — 여기서는 저장 · 보내기만 한다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers.ws import hub
from app.schemas.notice import NoticeIn, NoticeOut, NoticePatch

router = APIRouter(tags=["notices"])


def _need_teacher(user):
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 할 수 있습니다")


def _my_notice(db: Session, notice_id: int, user):
    n = crud.get_notice(db, notice_id)
    if n is None or n["teacher_id"] != user["id"]:
        raise HTTPException(404, "찾을 수 없습니다")
    return n


def _not_sent(n):
    if n["status"] == "sent":
        raise HTTPException(409, "이미 보낸 공지는 고치거나 지울 수 없습니다")


@router.get("/notices", response_model=list[NoticeOut])
def list_notices(db: Session = Depends(get_db), user=Depends(current_user)):
    """교사: 자기 공지 전부(쓰는 중 먼저). 학부모: 받은 공지(보낸 것만)."""
    if user["role"] == "teacher":
        rows = crud.list_teacher_notices(db, user["id"])
    elif user["role"] == "parent":
        rows = crud.list_parent_notices(db, user["id"])
    else:
        raise HTTPException(403, "볼 수 있는 공지가 없습니다")
    return [dict(r) for r in rows]


@router.get("/notices/{notice_id}", response_model=NoticeOut)
def get_notice(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    if user["role"] == "teacher":
        return dict(_my_notice(db, notice_id, user))
    for r in crud.list_parent_notices(db, user["id"]) if user["role"] == "parent" else []:
        if r["id"] == notice_id:
            return dict(r)
    raise HTTPException(404, "찾을 수 없습니다")


@router.post("/notices", response_model=NoticeOut, status_code=201)
def create_notice(body: NoticeIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """저장 (쓰는 중). 학부모에게는 아직 안 보인다."""
    _need_teacher(user)
    return dict(crud.create_notice(db, user["id"], body.title.strip(), body.body.strip()))


@router.patch("/notices/{notice_id}", response_model=NoticeOut)
def update_notice(notice_id: int, body: NoticePatch, db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    _not_sent(_my_notice(db, notice_id, user))
    fields = {k: getattr(body, k).strip() for k in body.model_fields_set if getattr(body, k) is not None}
    if not crud.update_notice(db, notice_id, fields):
        raise HTTPException(409, "이미 보낸 공지는 고치거나 지울 수 없습니다")
    return dict(crud.get_notice(db, notice_id))


@router.delete("/notices/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    _not_sent(_my_notice(db, notice_id, user))
    if not crud.delete_notice(db, notice_id):
        raise HTTPException(409, "이미 보낸 공지는 고치거나 지울 수 없습니다")


@router.post("/notices/{notice_id}/send", response_model=NoticeOut)
def send_notice(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """보내기: 그 교사와 대화가 있는 학부모 모두에게 보인다. 실시간 연결이 있으면 알림(번호만)."""
    _need_teacher(user)
    _not_sent(_my_notice(db, notice_id, user))
    if not crud.send_notice(db, notice_id):
        raise HTTPException(409, "이미 보낸 공지입니다")
    parents = crud.notice_recipients(db, user["id"])
    hub.notify_users([*parents, user["id"]], {"type": "notice", "notice_id": notice_id})
    return dict(crud.get_notice(db, notice_id))
