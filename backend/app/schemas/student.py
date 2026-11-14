# 학생 · 학생 메모장 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime

from pydantic import BaseModel, Field


class StudentOut(BaseModel):
    id: int
    name: str
    has_memo: bool  # 내 메모장에 무엇이든 적혀 있는지


class MemoIn(BaseModel):
    body: str = Field(..., max_length=20000)  # 메모장 전체. 빈 글이면 비운다


class MemoOut(BaseModel):
    student_id: int
    body: str
    updated_at: datetime | None  # 한 번도 안 적었으면 null
