# 저장 · 조회  [어령]  (시험용: 모델 없이 SQL 직접)
import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_user_by_login(db: Session, login_id: str):
    return db.execute(text("SELECT * FROM users WHERE login_id = :l"), {"l": login_id}).mappings().first()


def get_user(db: Session, user_id: int):
    return db.execute(text("SELECT * FROM users WHERE id = :i"), {"i": user_id}).mappings().first()


def get_conversation(db: Session, conv_id: int):
    return db.execute(text("SELECT * FROM conversations WHERE id = :i"), {"i": conv_id}).mappings().first()


def list_conversations(db: Session, user_id: int):
    return db.execute(
        text("SELECT * FROM conversations WHERE teacher_id = :u OR parent_id = :u ORDER BY id"),
        {"u": user_id},
    ).mappings().all()


def add_message(db: Session, conv_id: int, sender_id: int, raw_text: str, status: str):
    row = db.execute(
        text(
            "INSERT INTO messages (conversation_id, sender_id, raw_text, status) "
            "VALUES (:c, :s, :t, :st) RETURNING *"
        ),
        {"c": conv_id, "s": sender_id, "t": raw_text, "st": status},
    ).mappings().first()
    db.commit()
    return row


def list_messages(db: Session, conv_id: int):
    return db.execute(
        text("SELECT * FROM messages WHERE conversation_id = :c ORDER BY id"), {"c": conv_id}
    ).mappings().all()


# ---- 정제(A) 결과

def get_message(db: Session, msg_id: int):
    return db.execute(text("SELECT * FROM messages WHERE id = :i"), {"i": msg_id}).mappings().first()


def set_message_pending(db: Session, msg_id: int):
    """「다시 정제」: 이전 결과를 지우고 정제 대기로 되돌린다."""
    row = db.execute(
        text("UPDATE messages SET status = 'pending', refined_text = NULL, analysis = NULL WHERE id = :i RETURNING *"),
        {"i": msg_id},
    ).mappings().first()
    db.commit()
    return row


def save_refine_result(db: Session, msg_id: int, result: dict) -> None:
    """refine_message 의 반환값을 저장. 실패하면 analysis 에 {"error": 사유} 를 넣는다 (사유에는 원문이 없다)."""
    failed = result["status"] != "done"
    analysis = {"error": result["error"]} if failed else result["analysis"]
    db.execute(
        text(
            "UPDATE messages SET status = :st, refined_text = :rt, analysis = CAST(:an AS JSONB) WHERE id = :i"
        ),
        {"st": "failed" if failed else "done", "rt": result["refined_text"],
         "an": json.dumps(analysis, ensure_ascii=False), "i": msg_id},
    )
    db.commit()


def class_people(db: Session, teacher_id: int) -> tuple[list[str], list[str]]:
    """가명처리 명단용: 이 교사의 대화에 나오는 학생 이름들, 어른(교사 · 학부모) 실명들.
    DB 에 「반」이 없어서 지금은 교사 한 명의 대화 전체를 한 반으로 본다."""
    rows = db.execute(
        text(
            "SELECT c.student_name, t.name AS teacher_name, p.name AS parent_name "
            "FROM conversations c JOIN users t ON t.id = c.teacher_id JOIN users p ON p.id = c.parent_id "
            "WHERE c.teacher_id = :t"
        ),
        {"t": teacher_id},
    ).mappings().all()
    students = sorted({r["student_name"] for r in rows})
    adults = sorted({r["teacher_name"] for r in rows} | {r["parent_name"] for r in rows})
    return students, adults
