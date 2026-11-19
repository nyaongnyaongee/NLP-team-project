# 학생 · 학생 메모장 요청·응답 형식  [채원 + 어령]  (시험용으로 재관이 채움)
from datetime import datetime

from pydantic import BaseModel, Field


class StudentOut(BaseModel):
    id: int
    name: str
    has_memo: bool  # 내 메모장에 무엇이든 적혀 있는지
    parent_name: str | None = None  # 이어진 학부모 (없으면 null — 대화를 시작할 수 없음, 초대 코드로 잇는다)


class MemoIn(BaseModel):
    body: str = Field(..., max_length=20000)  # 메모장 전체. 빈 글이면 비운다


class MemoOut(BaseModel):
    student_id: int
    body: str
    updated_at: datetime | None  # 한 번도 안 적었으면 null


class InviteOut(BaseModel):
    code: str  # 교사의 반 초대 코드


class ChildIn(BaseModel):
    """학부모가 자녀 더하기: 그 반 담임의 초대 코드 + 자녀 이름"""
    invite_code: str = Field(..., max_length=40)
    student_name: str = Field(..., max_length=40)


class JoinIn(ChildIn):
    """가입 없이 들어오기 (시연): 초대 코드 + 자녀 이름 + 보호자 이름"""
    parent_name: str = Field(..., max_length=40)
