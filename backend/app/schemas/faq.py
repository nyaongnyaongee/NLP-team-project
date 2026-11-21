# 자주 묻는 질문(Q&A) 요청 · 응답 형식  [재관]
from datetime import datetime

from pydantic import BaseModel, Field


class FaqIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=200)
    answer: str = Field(..., min_length=1, max_length=3000)


class FaqPatch(BaseModel):
    """보낸 필드만 바꾼다."""
    question: str | None = Field(None, min_length=1, max_length=200)
    answer: str | None = Field(None, min_length=1, max_length=3000)


class FaqOut(BaseModel):
    id: int
    teacher_id: int
    question: str
    answer: str
    created_at: datetime
    updated_at: datetime


class FaqDraftIn(BaseModel):
    memo: str = Field("", max_length=1000)  # 무엇을 Q&A 로 남길지 (짧게). 대화창에서는 없어도 됨 (대화를 보고 알아서)
    conversation_id: int | None = None  # 대화창에서 만들면 그 대화도 참고한다 (교사가 볼 수 있는 글만)


class FaqDraftOut(BaseModel):
    question: str
    answer: str
    check: list[str]  # 등록 전 교사가 확인할 것 ([ ] 자리, 뺀 이름 · 사정 …)
