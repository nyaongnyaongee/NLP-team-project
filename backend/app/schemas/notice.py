# 공지 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class NoticeIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=5000)


class NoticePatch(BaseModel):
    """보낸 필드만 바꾼다. 이미 보낸 공지도 고칠 수 있다."""
    title: str | None = Field(None, min_length=1, max_length=100)
    body: str | None = Field(None, min_length=1, max_length=5000)


class NoticeOut(BaseModel):
    id: int
    teacher_id: int
    title: str
    body: str
    status: Literal["draft", "sent"]  # 쓰는 중 → [보내기]
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
