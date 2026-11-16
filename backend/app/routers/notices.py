# 공지사항  [채원]  (시험용으로 재관이 채움)
# 교사: 쓰기(draft) → 고치기 → [보내기](sent). 보낸 공지도 고치거나 지울 수 있다 (학부모에게 알림). 다시 보내기만 안 됨.
# 받는 사람 = 반 학생(students.parent_id)의 학부모 전원 + 그 교사와 대화가 있는 학부모. 학부모는 보낸 공지만 본다.
# 초안(Claude)은 POST /drafts/notice — 여기서는 저장 · 보내기만 한다.
# 댓글: 보낸 공지에 그 교사와 받는 학부모가 단다 (서로 다 보임, 정제하지 않음). 지우기 = 쓴 사람 또는 공지를 쓴 교사.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers.ws import hub
from app.schemas.notice import CommentIn, CommentOut, NoticeIn, NoticeOut, NoticePatch

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
        raise HTTPException(409, "이미 보낸 공지입니다")


@router.get("/notices", response_model=list[NoticeOut])
def list_notices(db: Session = Depends(get_db), user=Depends(current_user)):
    """교사: 자기 공지 전부(쓰는 중 먼저). 학부모: 받은 공지(보낸 것만)."""
    if user["role"] == "teacher":
        rows = crud.list_teacher_notices(db, user["id"])
    elif user["role"] == "parent":
        rows = crud.list_parent_notices(db, user["id"])
    else:
        raise HTTPException(403, "볼 수 있는 공지가 없습니다")
    return _with_counts(db, rows)


def _with_counts(db: Session, rows) -> list[dict]:
    counts = crud.count_notice_comments(db, [r["id"] for r in rows])
    return [{**dict(r), "comment_count": counts.get(r["id"], 0)} for r in rows]


@router.get("/notices/{notice_id}", response_model=NoticeOut)
def get_notice(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    if user["role"] == "teacher":
        return _with_counts(db, [_my_notice(db, notice_id, user)])[0]
    for r in crud.list_parent_notices(db, user["id"]) if user["role"] == "parent" else []:
        if r["id"] == notice_id:
            return _with_counts(db, [r])[0]
    raise HTTPException(404, "찾을 수 없습니다")


@router.post("/notices", response_model=NoticeOut, status_code=201)
def create_notice(body: NoticeIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """저장 (쓰는 중). 학부모에게는 아직 안 보인다."""
    _need_teacher(user)
    return dict(crud.create_notice(db, user["id"], body.title.strip(), body.body.strip()))


def _notify_if_sent(db: Session, n, user):
    """보낸 공지가 바뀌거나 지워지면 받는 학부모 화면도 다시 불러오게 (번호만)."""
    if n["status"] == "sent":
        parents = crud.notice_recipients(db, user["id"])
        hub.notify_users([*parents, user["id"]], {"type": "notice", "notice_id": n["id"]})


@router.patch("/notices/{notice_id}", response_model=NoticeOut)
def update_notice(notice_id: int, body: NoticePatch, db: Session = Depends(get_db), user=Depends(current_user)):
    """고치기. 보낸 공지도 고칠 수 있고, 학부모에게 바로 바뀐 내용이 보인다 (「수정됨」 = updated_at > sent_at)."""
    _need_teacher(user)
    n = _my_notice(db, notice_id, user)
    fields = {k: getattr(body, k).strip() for k in body.model_fields_set if getattr(body, k) is not None}
    if not crud.update_notice(db, notice_id, fields):
        raise HTTPException(404, "찾을 수 없습니다")
    if fields:
        _notify_if_sent(db, n, user)
    return _with_counts(db, [crud.get_notice(db, notice_id)])[0]


@router.delete("/notices/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """지우기. 보낸 공지면 학부모 화면에서도 사라진다."""
    _need_teacher(user)
    n = _my_notice(db, notice_id, user)
    if not crud.delete_notice(db, notice_id):
        raise HTTPException(404, "찾을 수 없습니다")
    _notify_if_sent(db, n, user)


@router.post("/notices/{notice_id}/send", response_model=NoticeOut)
def send_notice(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    """보내기: 반 학부모 모두에게 보인다 (crud.notice_recipients). 실시간 연결이 있으면 알림(번호만)."""
    _need_teacher(user)
    _not_sent(_my_notice(db, notice_id, user))
    if not crud.send_notice(db, notice_id):
        raise HTTPException(409, "이미 보낸 공지입니다")
    parents = crud.notice_recipients(db, user["id"])
    hub.notify_users([*parents, user["id"]], {"type": "notice", "notice_id": notice_id})
    return _with_counts(db, [crud.get_notice(db, notice_id)])[0]


# ---- 댓글

def _commentable(db: Session, notice_id: int, user):
    """댓글을 보고 쓸 수 있는 공지: 교사 = 자기가 보낸 공지, 학부모 = 받은 공지. 쓰는 중(초안)에는 댓글 없음."""
    if user["role"] == "teacher":
        n = _my_notice(db, notice_id, user)
        if n["status"] != "sent":
            raise HTTPException(409, "게시한 공지에만 댓글을 달 수 있습니다")
        return n
    if user["role"] == "parent":
        for r in crud.list_parent_notices(db, user["id"]):
            if r["id"] == notice_id:
                return r
        raise HTTPException(404, "찾을 수 없습니다")
    raise HTTPException(403, "댓글을 볼 수 없습니다")


def _comment_view(c, notice, user) -> dict:
    mine = c["author_id"] == user["id"]
    return {**dict(c), "mine": mine, "can_delete": mine or notice["teacher_id"] == user["id"]}


def _notify_comment(db: Session, n):
    parents = crud.notice_recipients(db, n["teacher_id"])
    hub.notify_users([*parents, n["teacher_id"]], {"type": "notice", "notice_id": n["id"]})


@router.get("/notices/{notice_id}/comments", response_model=list[CommentOut])
def list_comments(notice_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    n = _commentable(db, notice_id, user)
    return [_comment_view(c, n, user) for c in crud.list_notice_comments(db, notice_id)]


@router.post("/notices/{notice_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(notice_id: int, body: CommentIn, db: Session = Depends(get_db), user=Depends(current_user)):
    n = _commentable(db, notice_id, user)
    text_ = body.body.strip()
    if not text_:
        raise HTTPException(422, "댓글을 입력해 주세요")
    cid = crud.add_notice_comment(db, notice_id, user["id"], text_)
    _notify_comment(db, n)
    c = next(c for c in crud.list_notice_comments(db, notice_id) if c["id"] == cid)
    return _comment_view(c, n, user)


@router.delete("/notices/{notice_id}/comments/{comment_id}", status_code=204)
def delete_comment(notice_id: int, comment_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    n = _commentable(db, notice_id, user)
    c = crud.get_notice_comment(db, comment_id)
    if c is None or c["notice_id"] != notice_id:
        raise HTTPException(404, "찾을 수 없습니다")
    if not _comment_view(c, n, user)["can_delete"]:
        raise HTTPException(403, "내 댓글만 지울 수 있습니다")
    crud.delete_notice_comment(db, comment_id)
    _notify_comment(db, n)
