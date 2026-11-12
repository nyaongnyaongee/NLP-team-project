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
        text("UPDATE messages SET status = 'pending', refined_text = NULL, analysis = NULL, needs_refinement = NULL "
             "WHERE id = :i RETURNING *"),
        {"i": msg_id},
    ).mappings().first()
    db.commit()
    return row


def save_refine_result(db: Session, msg_id: int, result: dict) -> None:
    """refine_message 의 반환값을 저장. 실패하면 analysis 에 {"error": 사유} 를 넣는다 (사유에는 원문이 없다).
    needs_refinement: true = 정제문, false = 원문 통과, 실패면 NULL."""
    failed = result["status"] != "done"
    analysis = {"error": result["error"]} if failed else result["analysis"]
    db.execute(
        text(
            "UPDATE messages SET status = :st, refined_text = :rt, analysis = CAST(:an AS JSONB), "
            "needs_refinement = :nr WHERE id = :i"
        ),
        {"st": "failed" if failed else "done", "rt": result["refined_text"],
         "nr": None if failed else result.get("needs_refinement"),
         "an": json.dumps(analysis, ensure_ascii=False), "i": msg_id},
    )
    db.commit()


def save_reply_draft(db: Session, msg_id: int, draft: dict) -> None:
    """자동 답장 추천(B)을 analysis.reply_draft 에 붙인다. 그사이 다시 정제가 눌려 done 이 아니면 안 붙인다."""
    db.execute(
        text("UPDATE messages SET analysis = analysis || jsonb_build_object('reply_draft', CAST(:d AS JSONB)) "
             "WHERE id = :i AND status = 'done'"),
        {"d": json.dumps(draft, ensure_ascii=False), "i": msg_id},
    )
    db.commit()


def adult_names(db: Session) -> list[str]:
    """가명처리 명단용 어른 실명 (교사 · 학부모, 성까지).  학생 명단은 DB 가 아니라 ai/sample_roster.json 으로 고정."""
    rows = db.execute(text("SELECT name FROM users WHERE role IN ('teacher', 'parent')")).mappings().all()
    return sorted({r["name"] for r in rows})


# ---- 대화 만들기 · 닫기 (C 추출은 닫을 때)

def create_conversation(db: Session, teacher_id: int, parent_id: int, student_name: str):
    row = db.execute(
        text("INSERT INTO conversations (teacher_id, parent_id, student_name) VALUES (:t, :p, :s) RETURNING *"),
        {"t": teacher_id, "p": parent_id, "s": student_name},
    ).mappings().first()
    db.commit()
    return row


def set_conversation_status(db: Session, conv_id: int, status: str):
    """open | closed. 닫으면 추출 상태를 pending 으로 둔다 (같은 줄에서 바꿔야 화면이 「추출 중」을 바로 본다)."""
    extract = "CAST('{\"status\": \"pending\"}' AS JSONB)" if status == "closed" else "extract"
    row = db.execute(
        text(f"UPDATE conversations SET status = :st, extract = {extract} WHERE id = :i RETURNING *"),
        {"st": status, "i": conv_id},
    ).mappings().first()
    db.commit()
    return row


def reopen_if_closed(db: Session, conv_id: int) -> bool:
    """닫힌 대화에 새 메시지가 오면 다시 연다. 열었으면 True."""
    n = db.execute(text("UPDATE conversations SET status = 'open' WHERE id = :i AND status = 'closed'"),
                   {"i": conv_id}).rowcount
    db.commit()
    return n > 0


def save_extract_result(db: Session, conv_id: int, result: dict) -> int:
    """추출(C) 결과 저장. 이 대화의 후보(candidate)는 새 후보로 바꾸고, 교사가 추가 · 완료한 것은 그대로 둔다.
    실패하면 후보를 건드리지 않고 상태에 사유만 적는다. 저장한 후보 수를 돌려준다."""
    if result["status"] != "done":
        state = {"status": "failed", "error": result["error"]}
        count = 0
    else:
        db.execute(text("DELETE FROM tasks WHERE conversation_id = :c AND status = 'candidate'"), {"c": conv_id})
        for t in result["tasks"]:
            db.execute(
                text("INSERT INTO tasks (conversation_id, kind, title, due_text, due_at) VALUES (:c, :k, :t, :dt, :da)"),
                {"c": conv_id, "k": t["kind"], "t": t["title"], "dt": t["due_text"], "da": t["due_at"]},
            )
        count = len(result["tasks"])
        state = {"status": "done", "count": count}
    db.execute(
        text("UPDATE conversations SET extract = CAST(:e AS JSONB) || jsonb_build_object('at', now()) WHERE id = :i"),
        {"e": json.dumps(state, ensure_ascii=False), "i": conv_id},
    )
    db.commit()
    return count


# ---- 할 일 · 일정 (tasks 한 테이블, kind 로 나눔)

def list_tasks(db: Session, teacher_id: int, kind: str, status: str | None = None, conv_id: int | None = None):
    """교사 한 명의 할 일(todo) 또는 일정(event). 날짜 있는 것 먼저(가까운 순), 그다음 만든 순."""
    sql = ("SELECT t.*, c.student_name FROM tasks t JOIN conversations c ON c.id = t.conversation_id "
           "WHERE c.teacher_id = :u AND t.kind = :k")
    params: dict = {"u": teacher_id, "k": kind}
    if status:
        sql += " AND t.status = :st"
        params["st"] = status
    if conv_id:
        sql += " AND t.conversation_id = :c"
        params["c"] = conv_id
    sql += " ORDER BY t.due_at NULLS LAST, t.id"
    return db.execute(text(sql), params).mappings().all()


def task_titles(db: Session, conv_id: int, statuses: tuple[str, ...]) -> list[dict]:
    """추출할 때 「이미 등록된 것」으로 보여 줄 목록 (같은 일을 또 뽑지 않게)."""
    return [dict(r) for r in db.execute(
        text("SELECT kind, title FROM tasks WHERE conversation_id = :c AND status = ANY(:s) ORDER BY id"),
        {"c": conv_id, "s": list(statuses)},
    ).mappings().all()]


def get_task(db: Session, task_id: int):
    return db.execute(
        text("SELECT t.*, c.student_name, c.teacher_id FROM tasks t JOIN conversations c ON c.id = t.conversation_id "
             "WHERE t.id = :i"), {"i": task_id},
    ).mappings().first()


def update_task(db: Session, task_id: int, fields: dict) -> None:
    """fields: title · due_text · due_at · status 중 바꿀 것만."""
    if not fields:
        return
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    db.execute(text(f"UPDATE tasks SET {sets} WHERE id = :i"), {**fields, "i": task_id})
    db.commit()


def delete_task(db: Session, task_id: int) -> None:
    db.execute(text("DELETE FROM tasks WHERE id = :i"), {"i": task_id})
    db.commit()


# ---- 시험용 초기화 (/dev/reset)

def dev_reset(db: Session) -> list[int]:
    """메시지 · 할 일/일정을 모두 지우고 대화를 처음 상태(열림, 추출 없음)로. 계정 · 대화 자체는 둔다. 대화 id 목록을 돌려준다."""
    db.execute(text("TRUNCATE messages, tasks RESTART IDENTITY"))
    db.execute(text("UPDATE conversations SET status = 'open', extract = NULL, report = NULL, reported_at = NULL"))
    ids = [r[0] for r in db.execute(text("SELECT id FROM conversations ORDER BY id")).all()]
    db.commit()
    return ids
