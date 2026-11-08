# 메시지 요청·응답 형식  [채원 + 어령]
from datetime import datetime

from pydantic import BaseModel


class LoginIn(BaseModel):
    login_id: str
    password: str


class LoginOut(BaseModel):
    token: str
    name: str
    role: str


class MessageIn(BaseModel):
    text: str


class MessageOut(BaseModel):
    id: int
    sender_id: int
    raw_text: str | None  # 교사에게는 학부모 글의 원문을 주지 않는다 (None). 원문은 DB 에만 있다
    refined_text: str | None  # 교사에게만
    analysis: dict | None = None  # 교사에게만. 주제 · 요청 · 위협 …, 실패하면 {"error": 사유}. 인용문(quotes)은 뺀다
    status: str
    created_at: datetime
