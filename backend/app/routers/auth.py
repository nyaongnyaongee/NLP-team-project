# 로그인  [채원]
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth import make_token, verify_password
from app.db import crud
from app.db.database import get_db
from app.routers.students import clean_name, invite_teacher
from app.routers.ws import hub
from app.schemas.message import LoginIn, LoginOut
from app.schemas.student import JoinIn

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


@router.post("/join", response_model=LoginOut)
def join(body: JoinIn, db: Session = Depends(get_db)):
    """가입 없이 들어오기 (시연): 담임의 초대 코드 + 자녀 이름 + 보호자 이름 → 학부모 계정을 만들고 자녀를 이어 바로 로그인.
    아이디 · 비밀번호가 없으므로 토큰(12시간)이 끝나면 다시 들어올 수 없다. 진짜 가입은 여기에 아이디 · 비밀번호만 더하면 된다."""
    teacher = invite_teacher(db, body.invite_code)
    student = clean_name(body.student_name, "자녀 이름")
    parent = clean_name(body.parent_name, "보호자 이름")
    problem = crud.child_link_problem(db, teacher["id"], None, student)
    if problem:
        raise HTTPException(409, problem)
    user = crud.create_guest_parent(db, parent)
    crud.link_child(db, teacher["id"], user["id"], student)
    db.commit()
    hub.notify_users([teacher["id"]], {"type": "students"})  # 담임 「학생」 탭이 다시 읽게
    return LoginOut(token=make_token(user["id"]), name=user["name"], role=user["role"])
