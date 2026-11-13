# 신고 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReportIn(BaseModel):
    memo: str | None = Field(None, max_length=1000)  # 담임이 적는 신고 사유 (비워도 됨)


class ReportListItem(BaseModel):
    """민원대응팀 목록 한 줄."""
    conversation_id: int
    teacher_name: str
    parent_name: str
    student_name: str
    reported_at: datetime
    status: Literal["pending", "done", "failed"]
    severity: Literal["낮음", "보통", "높음"] | None = None
    summary: str | None = None


class ReportMessage(BaseModel):
    """민원대응팀이 보는 메시지: 학부모 글도 원문 그대로 (정제문은 참고로)."""
    id: int
    who: Literal["parent", "teacher"]
    raw_text: str
    refined_text: str | None
    status: str
    created_at: datetime


class ReportDetail(BaseModel):
    conversation_id: int
    teacher_name: str
    parent_name: str
    student_name: str
    reported_at: datetime
    report: dict  # {"status", "memo", "summary", "severity", "incidents": [{"message_id", "at", "types", "quote"}], …}
    messages: list[ReportMessage]
