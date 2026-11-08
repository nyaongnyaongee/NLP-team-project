# 저장 · 조회  [어령]  (시험용: 모델 없이 SQL 직접)
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
