"""민원 이관 신청서와 담당자 · 학부모 · 교사 채팅의 API 형식."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CaseStatus = Literal["received", "in_progress", "completed"]
ReportStatus = Literal["pending", "done", "failed"]
Channel = Literal["parent", "teacher"]


class ComplaintIn(BaseModel):
    conversation_ids: list[int] = Field(min_length=1, max_length=20)
    reason: str = Field(max_length=2000)


class ComplaintSummary(BaseModel):
    id: int
    teacher_id: int
    parent_id: int
    teacher_name: str
    parent_name: str
    reason: str
    status: CaseStatus
    report_status: ReportStatus
    report_requested_at: datetime
    conversation_ids: list[int]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ComplaintMessage(BaseModel):
    id: int
    who: Literal["parent", "teacher"]
    text: str | None
    raw_text: str | None
    refined_text: str | None
    status: str
    created_at: datetime


class ComplaintConversation(BaseModel):
    id: int
    student_name: str
    status: str
    messages: list[ComplaintMessage]


class ComplaintDetail(ComplaintSummary):
    report: dict | None
    report_error: str | None
    conversations: list[ComplaintConversation]


class ComplaintChatIn(BaseModel):
    text: str = Field(max_length=4000)


class ComplaintChatReadIn(BaseModel):
    message_id: int = Field(ge=1)


class ComplaintChatMessage(BaseModel):
    id: int
    case_id: int
    channel: Channel
    author_id: int
    author_name: str
    author_role: str
    text: str
    created_at: datetime


class ComplaintChatSummary(BaseModel):
    case_id: int
    channel: Channel
    status: CaseStatus
    counterpart_name: str
    last_message_at: datetime | None
    last_message_text: str | None
    unread_count: int
