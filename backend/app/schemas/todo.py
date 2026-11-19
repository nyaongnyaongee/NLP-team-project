# 할일·일정 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TaskOut(BaseModel):
    id: int
    conversation_id: int | None  # None = 교사가 직접 등록한 반 전체 일정
    student_name: str | None
    kind: Literal["todo", "event"]
    shared: bool = True  # 일정: 학부모 캘린더에 보임
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
    shared: bool | None = None  # 일정만: 학부모와 공유


class EventIn(BaseModel):
    """교사가 직접 등록하는 반 전체 일정."""
    title: str = Field(min_length=1, max_length=100)
    due_at: datetime | None = None
    shared: bool = True


class TodoIn(BaseModel):
    """교사가 직접 등록하는 할 일."""
    title: str = Field(min_length=1, max_length=100)
    due_at: datetime | None = None


class ParentEventOut(BaseModel):
    """학부모 캘린더의 일정 (공유된 것만)."""
    id: int
    conversation_id: int | None
    student_name: str | None
    teacher_name: str
    title: str
    due_text: str | None
    due_at: datetime | None
    status: Literal["added", "done"]


class ConversationCloseIn(BaseModel):
    extract: bool = True  # False 면 할 일 · 일정을 뽑지 않고 닫기만 (나중에 POST /extract 로 뽑을 수 있음)


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
