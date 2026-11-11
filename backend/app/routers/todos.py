# 할일(C)  [채원]  (시험용으로 재관이 채움)
# 할 일(todo) · 일정(event) 은 DB 에서 tasks 한 테이블(kind). API 는 /todos · /events 로 나누고 모양은 같다.
# 대화를 닫으면 후보(candidate)가 생기고, 교사가 [추가](added) → [완료](done) 하거나 지운다. 담임 교사만 본다.
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.schemas.todo import TaskOut, TaskPatch


def task_router(kind: str, path: str, tag: str) -> APIRouter:
    router = APIRouter(tags=[tag])

    def _need_teacher(user):
        if user["role"] != "teacher":
            raise HTTPException(403, "교사만 볼 수 있습니다")

    def _my_task(db: Session, task_id: int, user):
        task = crud.get_task(db, task_id)
        if task is None or task["kind"] != kind or task["teacher_id"] != user["id"]:
            raise HTTPException(404, "찾을 수 없습니다")
        return task

    @router.get(f"/{path}", response_model=list[TaskOut])
    def list_(status: str | None = Query(None, pattern="^(candidate|added|done)$"),
              conversation_id: int | None = None,
              db: Session = Depends(get_db), user=Depends(current_user)):
        _need_teacher(user)
        return [dict(t) for t in crud.list_tasks(db, user["id"], kind, status, conversation_id)]

    @router.patch(f"/{path}/{{task_id}}", response_model=TaskOut)
    def update(task_id: int, body: TaskPatch, db: Session = Depends(get_db), user=Depends(current_user)):
        """[추가] = {"status": "added"}, [완료] = {"status": "done"}, 제목 · 날짜 고치기."""
        _need_teacher(user)
        _my_task(db, task_id, user)
        fields = {k: getattr(body, k) for k in body.model_fields_set}
        if fields.get("title") is None:
            fields.pop("title", None)  # 제목은 지울 수 없다
        if fields.get("status") is None:
            fields.pop("status", None)
        crud.update_task(db, task_id, fields)
        return dict(_my_task(db, task_id, user))

    @router.delete(f"/{path}/{{task_id}}", status_code=204)
    def delete(task_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
        _need_teacher(user)
        _my_task(db, task_id, user)
        crud.delete_task(db, task_id)

    return router


router = task_router("todo", "todos", "todos")
