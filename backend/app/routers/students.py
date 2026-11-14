# 학생 명단 · 학생 메모장  [채원]  (시험용으로 재관이 채움)
# 학생 = 담임 한 명의 반 (students.teacher_id). 「반」 테이블은 시연에서 만들지 않는다.
# 메모장 = 학생 한 명에 하나, 담임이 자유롭게 적는 글 한 덩어리. 통째로 읽고 통째로 저장한다 (화면이 적는 대로 저장).
#   쓴 교사만 본다. 학부모 · 민원대응팀에게는 API 가 없고, Claude(정제 · 초안 · 추출 · 보고서)에도 넣지 않는다.
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.schemas.student import MemoIn, MemoOut, StudentOut

router = APIRouter(tags=["students"])


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
