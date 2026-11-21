# 자주 묻는 질문(Q&A)  [재관]
# 교사가 등록하면 바로 반 학부모(공지와 같은 받는 사람)에게 보인다. 쓰는 중 상태는 없다 (등록 전에 화면에서 고친다).
# 초안: POST /drafts/faq — 대화창이면 그 대화를 보고 알아서(메모는 선택), 아니면 교사 메모로 Claude 가 Q&A 꼴로. 저장은 하지 않는다.
# 알림: 등록 · 고치기 · 지우기 때 {"type": "faq"} (번호 없이, 받는 쪽은 목록을 다시 읽는다). 띵 소리는 없음
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.draft import draft_faq
from app.ai.roster import class_roster
from app.core.auth import current_user
from app.db import crud
from app.db.database import get_db
from app.routers import messages as messages_router
from app.routers.drafts import _history, _need_claude
from app.routers.ws import hub
from app.schemas.faq import FaqDraftIn, FaqDraftOut, FaqIn, FaqOut, FaqPatch

router = APIRouter(tags=["faqs"])


def _need_teacher(user):
    if user["role"] != "teacher":
        raise HTTPException(403, "교사만 할 수 있습니다")


def _my_faq(db: Session, faq_id: int, user):
    f = crud.get_faq(db, faq_id)
    if f is None or f["teacher_id"] != user["id"]:
        raise HTTPException(404, "찾을 수 없습니다")
    return f


def _notify(db: Session, teacher_id: int):
    hub.notify_users([*crud.notice_recipients(db, teacher_id), teacher_id], {"type": "faq"})


@router.get("/faqs", response_model=list[FaqOut])
def list_faqs(db: Session = Depends(get_db), user=Depends(current_user)):
    """교사: 자기가 등록한 것. 학부모: 내 아이 담임 · 대화가 있는 교사가 등록한 것."""
    if user["role"] == "teacher":
        return [dict(r) for r in crud.list_teacher_faqs(db, user["id"])]
    if user["role"] == "parent":
        return [dict(r) for r in crud.list_parent_faqs(db, user["id"])]
    raise HTTPException(403, "볼 수 있는 Q&A 가 없습니다")


@router.post("/faqs", response_model=FaqOut, status_code=201)
def create_faq(body: FaqIn, db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    q, a = body.question.strip(), body.answer.strip()
    if not q or not a:
        raise HTTPException(422, "질문과 답변을 모두 입력해 주세요")
    row = dict(crud.create_faq(db, user["id"], q, a))
    _notify(db, user["id"])
    return row


@router.patch("/faqs/{faq_id}", response_model=FaqOut)
def update_faq(faq_id: int, body: FaqPatch, db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    _my_faq(db, faq_id, user)
    fields = {k: getattr(body, k).strip() for k in body.model_fields_set if getattr(body, k) is not None}
    if any(not v for v in fields.values()):
        raise HTTPException(422, "질문과 답변을 비울 수 없습니다")
    crud.update_faq(db, faq_id, fields)
    if fields:
        _notify(db, user["id"])
    return dict(crud.get_faq(db, faq_id))


@router.delete("/faqs/{faq_id}", status_code=204)
def delete_faq(faq_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    _need_teacher(user)
    _my_faq(db, faq_id, user)
    crud.delete_faq(db, faq_id)
    _notify(db, user["id"])


@router.post("/drafts/faq", response_model=FaqDraftOut)
def make_faq_draft(body: FaqDraftIn, db: Session = Depends(get_db), user=Depends(current_user)):
    """Q&A 초안. 몇 초 걸린다. conversation_id 를 주면 그 대화(교사가 볼 수 있는 글)도 참고하고,
    그때는 메모가 없어도 된다 (대화에서 다른 학부모도 물을 만한 질문을 골라 쓴다)."""
    _need_teacher(user)
    memo = body.memo.strip()
    if not memo and body.conversation_id is None:
        raise HTTPException(422, "메모를 입력해 주세요")
    history, student = None, None
    if body.conversation_id is not None:
        conv = messages_router._my_conversation(db, body.conversation_id, user)
        history = _history(crud.list_messages(db, conv["id"]), conv["parent_id"])
        student = conv["student_name"]
        if not memo and not any(h["who"] == "parent" for h in history):
            raise HTTPException(409, "Q&A 로 만들 학부모 질문이 아직 없습니다 (메모를 적어 주세요)")
    _need_claude()
    adults = crud.adult_names(db)
    roster = class_roster(crud.student_names(db, user["id"]), student)
    db.close()  # Claude 를 기다리는 동안 DB 연결을 잡고 있지 않는다
    result = draft_faq(memo, history, roster, adults)
    if result["status"] != "done":
        raise HTTPException(502, "Q&A 초안을 만들지 못했습니다: " + result["error"])
    return {"question": result["question"], "answer": result["answer"], "check": result["check"]}
