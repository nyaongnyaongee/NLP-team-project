# 학생 명단 · 학생 메모  [채원]  (시험용으로 재관이 채움)
# 학생 = 담임 한 명의 반 (students.teacher_id). 「반」 테이블은 시연에서 만들지 않는다.
# 메모 = 담임만 보는 관찰 기록 (날짜 + 짧은 글 여러 개). 쓴 교사만 보고 고치고 지운다.
#   학부모 · 민원대응팀에게는 API 가 없고, Claude(정제 · 초안 · 추출 · 보고서)에도 넣지 않는다.
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.schemas.student import NoteIn, NoteOut, StudentOut

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


def _my_note(db: Session, note_id: int, user):
    _need_teacher(user)
    n = crud.get_note(db, note_id)
    if n is None or n["teacher_id"] != user["id"]:
        raise HTTPException(404, "메모를 찾을 수 없습니다")
    return n


def _text(body: NoteIn) -> str:
    t = body.body.strip()
    if not t:
        raise HTTPException(422, "메모가 비어 있습니다")
    return t


@router.get("/students", response_model=list[StudentOut])
def my_students(db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    counts = crud.note_counts(db, user["id"])
    return [{"id": s["id"], "name": s["name"], "note_count": counts.get(s["id"], 0)}
            for s in crud.list_students(db, user["id"])]


@router.get("/students/{student_id}/notes", response_model=list[NoteOut])
def student_notes(student_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_student(db, student_id, user)
    return [dict(n) for n in crud.list_notes(db, student_id, user["id"])]


@router.post("/students/{student_id}/notes", response_model=NoteOut, status_code=201)
def add_note(student_id: int, body: NoteIn, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_student(db, student_id, user)
    return dict(crud.create_note(db, student_id, user["id"], _text(body)))


@router.patch("/notes/{note_id}", response_model=NoteOut)
def edit_note(note_id: int, body: NoteIn, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_note(db, note_id, user)
    return dict(crud.update_note(db, note_id, _text(body)))


@router.delete("/notes/{note_id}", status_code=204)
def remove_note(note_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _my_note(db, note_id, user)
    crud.delete_note(db, note_id)
    return Response(status_code=204)
