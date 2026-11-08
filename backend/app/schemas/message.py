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
    raw_text: str
    refined_text: str | None
    status: str
    created_at: datetime
