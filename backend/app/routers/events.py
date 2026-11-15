# 일정(C)  [채원]  (시험용으로 재관이 채움)  — 모양은 todos.py 와 같다 (tasks 테이블의 kind='event')
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers.todos import task_router
from app.routers.ws import hub
from app.schemas.todo import EventIn, TaskOut

router = task_router("event", "events", "events")
# GET /events 를 학부모가 부르면 공유된 일정만 온다 (학부모 캘린더). 교사는 자기 일정 전부.


@router.post("/events", response_model=TaskOut, status_code=201)
def create_event(body: EventIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """교사가 직접 등록하는 반 전체 일정. shared 면 반 학부모 캘린더에도 보인다."""
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 일정을 등록할 수 있습니다")
    task = crud.get_task(db, crud.create_event(db, user["id"], body.title.strip(), body.due_at, body.shared))
    if task["shared"]:
        hub.notify_users(crud.event_audience(db, task), {"type": "events"})
    return TaskOut(**task)
