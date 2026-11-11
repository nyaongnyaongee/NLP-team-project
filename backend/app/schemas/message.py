# 메시지 요청·응답 형식  [채원 + 어령]
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginIn(BaseModel):
    login_id: str
    password: str


class LoginOut(BaseModel):
    token: str
    name: str
    role: str


class MessageIn(BaseModel):
    text: str


class MessageIntakeIn(BaseModel):
    """Top-level A-1 intake request; existing conversation API stays intact."""

    model_config = ConfigDict(extra="forbid")

    conversation_id: int = Field(gt=0)
    text: str = Field(strict=True, min_length=1, max_length=10000)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class MessageAcceptedOut(BaseModel):
    id: int
    conversation_id: int
    status: Literal["pending"]


class MessageOut(BaseModel):
    id: int
    sender_id: int
    raw_text: str | None  # 교사에게는 학부모 글의 원문을 주지 않는다 (None). 원문은 DB 에만 있다
    refined_text: str | None  # 교사에게만
    analysis: dict | None = None  # 교사에게만. 주제 · 요청 · 위협 …, 실패하면 {"error": 사유}. 인용문(quotes)은 뺀다
    status: str
    created_at: datetime
