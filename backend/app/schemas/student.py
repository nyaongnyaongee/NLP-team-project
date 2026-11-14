# 학생 · 학생 메모 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime

from pydantic import BaseModel, Field


class StudentOut(BaseModel):
    id: int
    name: str
    note_count: int  # 내가 쓴 메모 수


class NoteIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class NoteOut(BaseModel):
    id: int
    student_id: int
    body: str
    created_at: datetime
    updated_at: datetime
