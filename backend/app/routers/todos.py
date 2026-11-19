# 할일(C)  [채원]  (시험용으로 재관이 채움)
# 할 일(todo) · 일정(event) 은 DB 에서 tasks 한 테이블(kind). API 는 /todos · /events 로 나누고 모양은 같다.
# 대화를 닫으면 후보(candidate)가 생기고, 교사가 [추가](added) → [완료](done) 하거나 지운다. 담임 교사만 본다.
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers.ws import hub
from app.schemas.todo import ParentEventOut, TaskOut, TaskPatch, TodoIn


def task_router(kind: str, path: str, tag: str) -> APIRouter:
    router = APIRouter(tags=[tag])

    def _need_teacher(user):
        if user["role"] != "teacher":
            raise HTTPException(403, "교사만 볼 수 있습니다")

    def _my_task(db: Session, task_id: int, user):
        task = crud.get_task(db, task_id)
        if task is None or task["kind"] != kind or task["owner_id"] != user["id"]:
            raise HTTPException(404, "찾을 수 없습니다")
        return task

    def _notify_parents(db: Session, task) -> None:
        """일정이 바뀌면 그 일정을 볼 수 있는 학부모 화면이 다시 불러오게 (내용은 GET 으로)."""
        if kind == "event" and task is not None:
            hub.notify_users(crud.event_audience(db, task), {"type": "events"})

    @router.get(f"/{path}", response_model=list[TaskOut] | list[ParentEventOut])
    def list_(status: str | None = Query(None, pattern="^(candidate|added|done)$"),
              conversation_id: int | None = None,
              db: Session = Depends(get_db), user=Depends(current_user)):
        if kind == "event" and user["role"] == "parent":  # 학부모 캘린더: 공유된 일정만
            return [ParentEventOut(**t) for t in crud.parent_events(db, user["id"])]
        _need_teacher(user)
        return [TaskOut(**t) for t in crud.list_tasks(db, user["id"], kind, status, conversation_id)]

    @router.patch(f"/{path}/{{task_id}}", response_model=TaskOut)
    def update(task_id: int, body: TaskPatch, db: Session = Depends(get_db), user=Depends(current_user)):
        """[추가] = {"status": "added"}, [완료] = {"status": "done"}, 제목 · 날짜 고치기, 일정 공유 켜고 끄기."""
        _need_teacher(user)
        _my_task(db, task_id, user)
        fields = {k: getattr(body, k) for k in body.model_fields_set}
        for key in ("title", "status", "shared"):  # 제목은 지울 수 없고, 상태 · 공유는 값이 있어야
            if fields.get(key) is None:
                fields.pop(key, None)
        crud.update_task(db, task_id, fields)
        task = _my_task(db, task_id, user)
        _notify_parents(db, task)
        return TaskOut(**task)

    @router.delete(f"/{path}/{{task_id}}", status_code=204)
    def delete(task_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
        _need_teacher(user)
        task = _my_task(db, task_id, user)
        crud.delete_task(db, task_id)
        _notify_parents(db, task)

    return router


router = task_router("todo", "todos", "todos")


@router.post("/todos", response_model=TaskOut, status_code=201)
def create_todo(body: TodoIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """교사가 직접 등록하는 할 일 (대화 없음, 바로 「추가됨」). 할 일은 교사만 보므로 알림은 없다."""
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 할 일을 등록할 수 있습니다")
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "제목을 입력해 주세요")
    return TaskOut(**crud.get_task(db, crud.create_task(db, user["id"], "todo", title, body.due_at, False)))
