# 저장 · 조회  [어령]  (시험용: 모델 없이 SQL 직접)
import json

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_user_by_login(db: Session, login_id: str):
    return db.execute(text("SELECT * FROM users WHERE login_id = :l"), {"l": login_id}).mappings().first()


def get_user(db: Session, user_id: int):
    return db.execute(text("SELECT * FROM users WHERE id = :i"), {"i": user_id}).mappings().first()


def user_name(db: Session, user_id: int) -> str | None:
    return db.execute(text("SELECT name FROM users WHERE id = :i"), {"i": user_id}).scalar()


def get_conversation(db: Session, conv_id: int):
    return db.execute(text("SELECT * FROM conversations WHERE id = :i"), {"i": conv_id}).mappings().first()


def list_conversations(db: Session, user_id: int, deleted: bool = False):
    """내 대화 목록. deleted=True 면 반대로 내 목록에서 지운 대화만 (행은 DB 에 남아 있으므로 다시 볼 수 있다)."""
    where = ("(c.teacher_id = :u AND c.teacher_deleted_at IS NOT NULL) OR (c.parent_id = :u AND c.parent_deleted_at IS NOT NULL)"
             if deleted else
             "(c.teacher_id = :u AND c.teacher_deleted_at IS NULL) OR (c.parent_id = :u AND c.parent_deleted_at IS NULL)")
    return db.execute(
        text("SELECT c.*, (SELECT max(m.created_at) FROM messages m WHERE m.conversation_id = c.id) AS last_message_at, "
             "(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id AND m.sender_id <> :u AND m.id > "
             " COALESCE(CASE WHEN c.teacher_id = :u THEN c.teacher_read_id ELSE c.parent_read_id END, 0)) AS unread "
             f"FROM conversations c WHERE {where} ORDER BY c.id"),
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
    """반 명단에 같은 이름이 있으면 student_id 를 이어 둔다 (없으면 NULL — 메모 칸이 안 보일 뿐)."""
    row = db.execute(
        text("INSERT INTO conversations (teacher_id, parent_id, student_name, student_id) VALUES (:t, :p, :s, "
             "(SELECT id FROM students WHERE teacher_id = :t AND name = :s)) RETURNING *"),
        {"t": teacher_id, "p": parent_id, "s": student_name},
    ).mappings().first()
    db.commit()
    return row


def startable_students(db: Session, user: dict):
    """대화를 시작할 수 있는 학생 (학부모가 등록된 학생만). 교사 = 자기 반, 학부모 = 자기 아이."""
    who = "s.teacher_id" if user["role"] == "teacher" else "s.parent_id"
    return db.execute(text(
        "SELECT s.id AS student_id, s.name AS student_name, s.teacher_id, t.name AS teacher_name, "
        "       s.parent_id, p.name AS parent_name "
        "FROM students s JOIN users t ON t.id = s.teacher_id JOIN users p ON p.id = s.parent_id "
        f"WHERE {who} = :u ORDER BY s.name"), {"u": user["id"]}).mappings().all()


def set_conversation_status(db: Session, conv_id: int, status: str, extract: bool = True):
    """open | closed. 추출하며 닫으면 추출 상태를 pending 으로 둔다 (같은 줄에서 바꿔야 화면이 「추출 중」을 바로 본다).
    추출 없이 닫으면 추출 상태는 그대로 둔다 (예전에 뽑은 후보 · 상태가 남음)."""
    extract = "CAST('{\"status\": \"pending\"}' AS JSONB)" if status == "closed" and extract else "extract"
    row = db.execute(
        text(f"UPDATE conversations SET status = :st, extract = {extract} WHERE id = :i RETURNING *"),
        {"st": status, "i": conv_id},
    ).mappings().first()
    db.commit()
    return row


def mark_read(db: Session, conv_id: int, role: str):
    """지금까지 온 메시지를 모두 읽음으로 (role = teacher | parent). 뒤로 가지 않게 큰 값만 남긴다."""
    col = {"teacher": "teacher_read_id", "parent": "parent_read_id"}[role]
    db.execute(text(f"UPDATE conversations SET {col} = GREATEST(COALESCE({col}, 0), "
                    "COALESCE((SELECT max(id) FROM messages WHERE conversation_id = :i), 0)) WHERE id = :i"),
               {"i": conv_id})
    db.commit()


def hide_conversation(db: Session, conv_id: int, role: str):
    """교사 또는 학부모 목록에서만 지운다 (role = teacher | parent). 행 · 메시지 · 할 일 · 보고서는 DB 에 그대로 남는다."""
    col = {"teacher": "teacher_deleted_at", "parent": "parent_deleted_at"}[role]
    db.execute(text(f"UPDATE conversations SET {col} = now() WHERE id = :i"), {"i": conv_id})
    db.commit()


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
    sql = ("SELECT t.*, c.student_name FROM tasks t LEFT JOIN conversations c ON c.id = t.conversation_id "
           "WHERE COALESCE(t.teacher_id, c.teacher_id) = :u AND t.kind = :k")
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
        text("SELECT t.*, c.student_name, c.parent_id, COALESCE(t.teacher_id, c.teacher_id) AS owner_id "
             "FROM tasks t LEFT JOIN conversations c ON c.id = t.conversation_id WHERE t.id = :i"), {"i": task_id},
    ).mappings().first()


def create_event(db: Session, teacher_id: int, title: str, due_at, shared: bool) -> int:
    """교사가 직접 등록하는 반 전체 일정 (대화 없음). 바로 「추가됨」."""
    new_id = db.execute(
        text("INSERT INTO tasks (teacher_id, kind, title, due_at, status, shared) "
             "VALUES (:t, 'event', :ti, :d, 'added', :s) RETURNING id"),
        {"t": teacher_id, "ti": title, "d": due_at, "s": shared},
    ).scalar()
    db.commit()
    return new_id


def parent_events(db: Session, parent_id: int):
    """학부모 캘린더: 공유한 일정 중 추가 · 완료한 것.
    대화에서 나온 일정은 그 대화의 학부모만, 반 전체 일정은 공지와 같은 기준(반 학생의 학부모 + 그 교사와 대화가 있는 학부모)."""
    return db.execute(text(
        "SELECT t.id, t.conversation_id, c.student_name, t.title, t.due_text, t.due_at, t.status, t.created_at, "
        "u.name AS teacher_name FROM tasks t LEFT JOIN conversations c ON c.id = t.conversation_id "
        "JOIN users u ON u.id = COALESCE(t.teacher_id, c.teacher_id) "
        "WHERE t.kind = 'event' AND t.status IN ('added', 'done') AND t.shared AND ("
        " c.parent_id = :p OR (t.conversation_id IS NULL AND t.teacher_id IN ("
        "  SELECT teacher_id FROM students WHERE parent_id = :p UNION SELECT teacher_id FROM conversations WHERE parent_id = :p))) "
        "ORDER BY t.due_at NULLS LAST, t.id"), {"p": parent_id}).mappings().all()


def event_audience(db: Session, task) -> list[int]:
    """이 일정이 보이는 (보일 수 있는) 학부모 — 바뀌었을 때 알림을 보낼 곳."""
    if task["conversation_id"] is not None:
        return [task["parent_id"]]
    return notice_recipients(db, task["owner_id"])


def update_task(db: Session, task_id: int, fields: dict) -> None:
    """fields: title · due_text · due_at · status · shared 중 바꿀 것만."""
    if not fields:
        return
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    db.execute(text(f"UPDATE tasks SET {sets} WHERE id = :i"), {**fields, "i": task_id})
    db.commit()


def delete_task(db: Session, task_id: int) -> None:
    db.execute(text("DELETE FROM tasks WHERE id = :i"), {"i": task_id})
    db.commit()


# ---- 공지

def create_notice(db: Session, teacher_id: int, title: str, body: str):
    row = db.execute(
        text("INSERT INTO notices (teacher_id, title, body) VALUES (:t, :ti, :b) RETURNING *"),
        {"t": teacher_id, "ti": title, "b": body},
    ).mappings().first()
    db.commit()
    return row


def get_notice(db: Session, notice_id: int):
    return db.execute(text("SELECT * FROM notices WHERE id = :i"), {"i": notice_id}).mappings().first()


def list_teacher_notices(db: Session, teacher_id: int):
    """교사 자기 공지 전부. 쓰는 중(draft) 먼저, 그다음 최근 것부터."""
    return db.execute(
        text("SELECT * FROM notices WHERE teacher_id = :t "
             "ORDER BY status = 'sent', COALESCE(sent_at, updated_at) DESC, id DESC"),
        {"t": teacher_id},
    ).mappings().all()


def list_parent_notices(db: Session, parent_id: int):
    """학부모가 받는 공지: 내 아이 담임(students) 또는 대화가 있는 교사가 보낸 것만, 최근 것부터."""
    return db.execute(
        text("SELECT * FROM notices WHERE status = 'sent' "
             "AND teacher_id IN (SELECT teacher_id FROM students WHERE parent_id = :p "
             "                   UNION SELECT teacher_id FROM conversations WHERE parent_id = :p) "
             "ORDER BY sent_at DESC, id DESC"),
        {"p": parent_id},
    ).mappings().all()


def update_notice(db: Session, notice_id: int, fields: dict) -> bool:
    """공지를 고친다 (보낸 공지도). 없으면 False. 보낸 뒤 고치면 updated_at > sent_at 이 되어 「수정됨」으로 보인다."""
    if not fields:
        return True
    sets = ", ".join(f"{k} = :{k}" for k in fields)
    n = db.execute(text(f"UPDATE notices SET {sets}, updated_at = now() WHERE id = :i"),
                   {**fields, "i": notice_id}).rowcount
    db.commit()
    return n == 1


def send_notice(db: Session, notice_id: int) -> bool:
    """draft → sent. 동시에 두 번 눌러도 한 번만 보낸다 (이미 보냈으면 False)."""
    n = db.execute(text("UPDATE notices SET status = 'sent', sent_at = now() WHERE id = :i AND status = 'draft'"),
                   {"i": notice_id}).rowcount
    db.commit()
    return n == 1


def delete_notice(db: Session, notice_id: int) -> bool:
    """공지를 지운다 (보낸 공지도 — 학부모 화면에서도 사라진다). 없으면 False."""
    n = db.execute(text("DELETE FROM notices WHERE id = :i"), {"i": notice_id}).rowcount
    db.commit()
    return n == 1


def notice_recipients(db: Session, teacher_id: int) -> list[int]:
    """공지를 받는 학부모 id = 반 학생의 학부모 전원 (students.parent_id) + 그 교사와 대화가 있는 학부모
    (반 명단에 없는 학생의 예전 대화도 빠지지 않게). list_parent_notices 와 같은 기준."""
    return [r[0] for r in db.execute(
        text("SELECT parent_id FROM students WHERE teacher_id = :t AND parent_id IS NOT NULL "
             "UNION SELECT parent_id FROM conversations WHERE teacher_id = :t ORDER BY 1"), {"t": teacher_id},
    ).all()]


# ---- 공지 댓글

def list_notice_comments(db: Session, notice_id: int):
    """오래된 것부터. 쓴 사람 이름: 교사는 교사 이름, 학부모는 「(그 담임 반) 아이 이름 학부모」 (없으면 학부모 이름)."""
    return db.execute(
        text("SELECT c.id, c.notice_id, c.author_id, u.role AS author_role, c.body, c.created_at, "
             "  CASE WHEN u.role = 'teacher' THEN u.name || ' 선생님' "
             "       ELSE COALESCE((SELECT string_agg(s.name, ', ' ORDER BY s.name) FROM students s "
             "                      WHERE s.parent_id = u.id AND s.teacher_id = n.teacher_id) || ' 학부모', "
             "                     u.name || ' 학부모') END AS author_name "
             "FROM notice_comments c JOIN users u ON u.id = c.author_id JOIN notices n ON n.id = c.notice_id "
             "WHERE c.notice_id = :n ORDER BY c.created_at, c.id"),
        {"n": notice_id},
    ).mappings().all()


def add_notice_comment(db: Session, notice_id: int, author_id: int, body: str) -> int:
    cid = db.execute(text("INSERT INTO notice_comments (notice_id, author_id, body) VALUES (:n, :a, :b) RETURNING id"),
                     {"n": notice_id, "a": author_id, "b": body}).scalar()
    db.commit()
    return cid


def get_notice_comment(db: Session, comment_id: int):
    return db.execute(text("SELECT * FROM notice_comments WHERE id = :i"), {"i": comment_id}).mappings().first()


def delete_notice_comment(db: Session, comment_id: int) -> bool:
    n = db.execute(text("DELETE FROM notice_comments WHERE id = :i"), {"i": comment_id}).rowcount
    db.commit()
    return n == 1


def count_notice_comments(db: Session, notice_ids: list[int]) -> dict[int, int]:
    if not notice_ids:
        return {}
    return dict(db.execute(text("SELECT notice_id, count(*) FROM notice_comments WHERE notice_id = ANY(:ids) "
                                "GROUP BY notice_id"), {"ids": list(notice_ids)}).all())


# ---- 신고 보고서 (D).  conversations.report = {"status": "pending" | "done" | "failed", "memo", …보고서 | "error", "at"}

def set_report_pending(db: Session, conv_id: int, memo: str | None):
    """신고(또는 다시 만들기). 처음 신고한 때(reported_at)는 바꾸지 않는다."""
    row = db.execute(
        text("UPDATE conversations SET report = jsonb_build_object('status', 'pending', 'memo', CAST(:m AS TEXT)), "
             "reported_at = COALESCE(reported_at, now()) WHERE id = :i RETURNING *"),
        {"m": memo, "i": conv_id},
    ).mappings().first()
    db.commit()
    return row


def save_report_result(db: Session, conv_id: int, result: dict, memo: str | None) -> None:
    if result["status"] == "done":
        state = {**result["report"], "status": "done", "memo": memo}
    else:
        state = {"status": "failed", "error": result["error"], "memo": memo}
    db.execute(
        text("UPDATE conversations SET report = CAST(:r AS JSONB) || jsonb_build_object('at', now()) WHERE id = :i"),
        {"r": json.dumps(state, ensure_ascii=False), "i": conv_id},
    )
    db.commit()


def list_reported(db: Session):
    """민원대응팀 목록: 신고된 대화 전부, 최근 신고 먼저. 교사 · 학부모 이름을 붙인다."""
    return db.execute(text(
        "SELECT c.*, t.name AS teacher_name, p.name AS parent_name FROM conversations c "
        "JOIN users t ON t.id = c.teacher_id JOIN users p ON p.id = c.parent_id "
        "WHERE c.reported_at IS NOT NULL ORDER BY c.reported_at DESC, c.id DESC"
    )).mappings().all()


def user_ids_with_role(db: Session, role: str) -> list[int]:
    return [r[0] for r in db.execute(text("SELECT id FROM users WHERE role = :r ORDER BY id"), {"r": role}).all()]


# ---- 학생 · 학생 메모

def list_students(db: Session, teacher_id: int):
    """반 학생 (이름 순). parent_name = 이어진 학부모 이름 (없으면 NULL)."""
    return db.execute(text("SELECT s.*, p.name AS parent_name FROM students s LEFT JOIN users p ON p.id = s.parent_id "
                           "WHERE s.teacher_id = :t ORDER BY s.name"), {"t": teacher_id}).mappings().all()


def student_names(db: Session, teacher_id: int) -> list[str]:
    """가명처리 학생 명단 = 그 교사의 반."""
    return [s["name"] for s in list_students(db, teacher_id)]


def get_student(db: Session, student_id: int):
    return db.execute(text("SELECT * FROM students WHERE id = :i"), {"i": student_id}).mappings().first()


def get_memo(db: Session, student_id: int, teacher_id: int):
    return db.execute(text("SELECT * FROM student_memos WHERE student_id = :s AND teacher_id = :t"),
                      {"s": student_id, "t": teacher_id}).mappings().first()


def memo_students(db: Session, teacher_id: int) -> set[int]:
    """메모장에 무엇이든 적힌 학생 id."""
    rows = db.execute(text("SELECT student_id FROM student_memos WHERE teacher_id = :t AND body <> ''"), {"t": teacher_id}).all()
    return {r[0] for r in rows}


def save_memo(db: Session, student_id: int, teacher_id: int, body: str):
    """메모장 통째로 저장 (없으면 만든다). 빈 글이면 비운 채로 둔다."""
    row = db.execute(
        text("INSERT INTO student_memos (student_id, teacher_id, body) VALUES (:s, :t, :b) "
             "ON CONFLICT (student_id, teacher_id) DO UPDATE SET body = EXCLUDED.body, updated_at = now() RETURNING *"),
        {"s": student_id, "t": teacher_id, "b": body},
    ).mappings().first()
    db.commit()
    return row


# ---- 초대 코드: 학부모가 교사의 반 코드 + 자녀 이름으로 자녀를 잇는다

INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 헷갈리는 I · O · 0 · 1 은 뺌


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def teacher_by_invite(db: Session, code: str):
    code = normalize_code(code)
    if not code:
        return None
    return db.execute(text("SELECT * FROM users WHERE role = 'teacher' AND invite_code = :c"), {"c": code}).mappings().first()


def teacher_invite_code(db: Session, teacher_id: int) -> str:
    """교사의 초대 코드. 없으면 새로 만든다 (6자리)."""
    import secrets

    code = db.execute(text("SELECT invite_code FROM users WHERE id = :i"), {"i": teacher_id}).scalar()
    while not code:
        cand = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(6))
        if db.execute(text("SELECT 1 FROM users WHERE invite_code = :c"), {"c": cand}).scalar():
            continue
        db.execute(text("UPDATE users SET invite_code = :c WHERE id = :i"), {"c": cand, "i": teacher_id})
        db.commit()
        code = cand
    return code


def create_guest_parent(db: Session, name: str):
    """가입 없이 들어온 학부모 (시연). 아이디 · 비밀번호는 아무도 모르게 만들고 토큰으로만 쓴다. commit 은 부르는 쪽이."""
    import secrets

    from app.core.auth import hash_password

    return db.execute(
        text("INSERT INTO users (role, name, login_id, password_hash) VALUES ('parent', :n, :l, :p) RETURNING *"),
        {"n": name, "l": "guest-" + secrets.token_hex(6), "p": hash_password(secrets.token_urlsafe(24))},
    ).mappings().first()


def child_link_problem(db: Session, teacher_id: int, parent_id: int | None, name: str) -> str | None:
    """잇지 못하는 까닭 (되면 None). 같은 반에 같은 이름의 학생이 다른 학부모와 이어져 있으면 안 된다."""
    s = db.execute(text("SELECT parent_id FROM students WHERE teacher_id = :t AND name = :n"),
                   {"t": teacher_id, "n": name}).mappings().first()
    if s is None or s["parent_id"] is None:
        return None
    if s["parent_id"] == parent_id:
        return "이미 연결된 자녀입니다"
    return "이미 다른 보호자와 연결된 학생입니다. 자녀 이름을 확인해 주세요"


def link_child(db: Session, teacher_id: int, parent_id: int, name: str) -> int:
    """반 명단에 그 이름이 있고 학부모가 없으면 잇고, 없으면 반에 새로 넣는다 (시연: 반은 하나, 들어온 학부모의 아이가 반에 더해짐).
    child_link_problem 으로 먼저 확인할 것. commit 은 부르는 쪽이. 학생 id 를 돌려준다."""
    sid = db.execute(text("UPDATE students SET parent_id = :p WHERE teacher_id = :t AND name = :n AND parent_id IS NULL "
                          "RETURNING id"), {"p": parent_id, "t": teacher_id, "n": name}).scalar()
    if sid is None:
        sid = db.execute(text("INSERT INTO students (teacher_id, name, parent_id) VALUES (:t, :n, :p) RETURNING id"),
                         {"t": teacher_id, "n": name, "p": parent_id}).scalar()
    return sid


# ---- 시험용 초기화 (/dev/reset)

def dev_reset(db: Session) -> list[int]:
    """메시지 · 할 일/일정 · 공지를 모두 지우고 대화를 처음 상태(열림, 추출 없음)로. 계정 · 대화 자체는 둔다. 대화 id 목록을 돌려준다."""
    db.execute(text("TRUNCATE messages, tasks, notice_comments, notices RESTART IDENTITY"))
    db.execute(text("UPDATE conversations SET status = 'open', extract = NULL, report = NULL, reported_at = NULL, "
                    "teacher_deleted_at = NULL, parent_deleted_at = NULL, teacher_read_id = NULL, parent_read_id = NULL"))
    ids = [r[0] for r in db.execute(text("SELECT id FROM conversations ORDER BY id")).all()]
    db.commit()
    return ids
