# 학생 명단 · 학생 메모장  [채원]  (시험용으로 재관이 채움)
# 학생 = 담임 한 명의 반 (students.teacher_id). 「반」 테이블은 시연에서 만들지 않는다.
# 메모장 = 학생 한 명에 하나, 담임이 자유롭게 적는 글 한 덩어리. 통째로 읽고 통째로 저장한다 (화면이 적는 대로 저장).
#   쓴 교사만 본다. 학부모 · 민원대응팀에게는 API 가 없고, Claude(정제 · 초안 · 추출 · 보고서)에도 넣지 않는다.
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers.ws import hub
from app.schemas.student import ChildIn, InviteOut, MemoIn, MemoOut, StudentOut
from app.schemas.todo import StartableOut

router = APIRouter(tags=["students"])

NAME_RE = re.compile(r"[가-힣A-Za-z]+( [가-힣A-Za-z]+)*")


def clean_name(name: str, what: str) -> str:
    """사람 이름: 앞뒤 · 겹친 띄어쓰기를 정리하고 한글 · 영문 2~20자만 받는다 (400 + 알림 문장)."""
    name = " ".join(name.split())
    if not (2 <= len(name) <= 20 and NAME_RE.fullmatch(name)):
        raise HTTPException(400, f"{what}을 한글 또는 영문 2~20자로 적어 주세요")
    return name


def invite_teacher(db: Session, code: str):
    t = crud.teacher_by_invite(db, code)
    if t is None:
        raise HTTPException(400, "초대 코드가 맞지 않습니다. 선생님께 받은 코드를 확인해 주세요")
    return t


def _need_teacher(user):
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 볼 수 있습니다")


def _my_student(db: Session, student_id: int, user):
    _need_teacher(user)
    s = crud.get_student(db, student_id)
    if s is None or s["teacher_id"] != user["id"]:
        raise HTTPException(404, "학생을 찾을 수 없습니다")
    return s


@router.get("/students", response_model=list[StudentOut])
def my_students(db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    with_memo = crud.memo_students(db, user["id"])
    return [{"id": s["id"], "name": s["name"], "has_memo": s["id"] in with_memo}
            for s in crud.list_students(db, user["id"])]


@router.get("/students/{student_id}/memo", response_model=MemoOut)
def read_memo(student_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_student(db, student_id, user)
    m = crud.get_memo(db, student_id, user["id"])
    return {"student_id": student_id, "body": m["body"] if m else "", "updated_at": m["updated_at"] if m else None}


@router.put("/students/{student_id}/memo", response_model=MemoOut)
def write_memo(student_id: int, body: MemoIn, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_student(db, student_id, user)
    m = crud.save_memo(db, student_id, user["id"], body.body.rstrip())
    return {"student_id": student_id, "body": m["body"], "updated_at": m["updated_at"]}


# ---- 초대 코드 (교사가 알려 주고, 학부모가 자녀를 잇는다)

@router.get("/students/invite", response_model=InviteOut)
def my_invite(db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    return {"code": crud.teacher_invite_code(db, user["id"])}


@router.post("/children", response_model=StartableOut)
def add_child(body: ChildIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """학부모가 초대 코드로 자녀를 하나 더 잇는다 (자녀가 여럿이거나 담임이 다를 때). 돌려주는 것 = 대화 시작 목록의 한 줄."""
    if user["role"] != "parent":
        raise HTTPException(403, "학부모만 자녀를 추가할 수 있습니다")
    teacher = invite_teacher(db, body.invite_code)
    name = clean_name(body.student_name, "자녀 이름")
    problem = crud.child_link_problem(db, teacher["id"], user["id"], name)
    if problem:
        raise HTTPException(409, problem)
    sid = crud.link_child(db, teacher["id"], user["id"], name)
    db.commit()
    hub.notify_users([teacher["id"]], {"type": "students"})  # 담임 「학생」 탭이 다시 읽게
    return next(s for s in crud.startable_students(db, user) if s["student_id"] == sid)
