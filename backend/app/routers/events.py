# 일정(C)  [채원]  (시험용으로 재관이 채움)  — 모양은 todos.py 와 같다 (tasks 테이블의 kind='event')
from app.routers.todos import task_router

router = task_router("event", "events", "events")
