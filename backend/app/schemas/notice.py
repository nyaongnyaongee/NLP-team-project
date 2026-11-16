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
    comment_count: int = 0


class CommentIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=1000)


class CommentOut(BaseModel):
    id: int
    notice_id: int
    author_id: int
    author_role: Literal["teacher", "parent"]
    author_name: str  # 「김민지 선생님」 · 「박지민 학부모」
    body: str
    created_at: datetime
    mine: bool  # 내가 쓴 댓글 (지우기 버튼)
    can_delete: bool  # 내 댓글이거나, 내 공지에 달린 댓글(교사)
