# 할일·일정 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: int
    conversation_id: int
    student_name: str
    kind: Literal["todo", "event"]
    title: str
    due_text: str | None  # 대화에 적힌 표현 그대로 (「다음 주 화요일」)
    due_at: datetime | None  # 바꾼 날짜. 시각이 없으면 그날 00:00 (한국 시각)
    status: Literal["candidate", "added", "done"]  # 후보 → [추가] → 완료
    created_at: datetime


class TaskPatch(BaseModel):
    """보낸 것만 바꾼다. due_at 에 null 을 보내면 날짜를 지운다."""
    title: str | None = Field(None, min_length=1, max_length=100)
    due_at: datetime | None = None
    status: Literal["candidate", "added", "done"] | None = None


class ConversationStartIn(BaseModel):
    student_id: int


class StartableOut(BaseModel):
    student_id: int
    student_name: str
    teacher_name: str
    parent_name: str


class ConversationIn(BaseModel):
    parent_id: int
    student_name: str = Field(..., min_length=1, max_length=20)
