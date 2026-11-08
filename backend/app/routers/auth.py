# 로그인  [채원]
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth import make_token, verify_password
from app.db import crud
from app.db.database import get_db
from app.schemas.message import LoginIn, LoginOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _check(db: Session, login_id: str, password: str):
    user = crud.get_user_by_login(db, login_id)
    if user is None or not verify_password(password, user["password_hash"]):
        raise HTTPException(401, "아이디 또는 비밀번호가 틀렸습니다")
    return user


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = _check(db, body.login_id, body.password)
    return LoginOut(token=make_token(user["id"]), name=user["name"], role=user["role"])


@router.post("/token")
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """/docs 의 [Authorize] 창이 부르는 곳 (폼 형식). 직접 부를 일은 없음"""
    user = _check(db, form.username, form.password)
    return {"access_token": make_token(user["id"]), "token_type": "bearer"}
