# 테스트 데이터 넣기  [어령]   실행: cd backend && python -m app.db.seed
from sqlalchemy import text

from app.core.auth import hash_password
from app.db.database import SessionLocal

USERS = [  # (role, name, login_id)
    ("teacher", "김민지", "teacher1"),
    ("parent", "박서연", "parent1"),
    ("parent", "이도윤", "parent2"),
]

with SessionLocal() as db:
    if db.execute(text("SELECT count(*) FROM users")).scalar():
        raise SystemExit("이미 데이터가 있습니다 (건너뜀)")
    ids = {}
    for role, name, login in USERS:
        ids[login] = db.execute(
            text("INSERT INTO users (role, name, login_id, password_hash) VALUES (:r,:n,:l,:p) RETURNING id"),
            {"r": role, "n": name, "l": login, "p": hash_password("test1234")},
        ).scalar()
    for parent, student in (("parent1", "지민"), ("parent2", "민준")):  # 학생 이름은 ai/sample_roster.json 의 20명 중에서
        db.execute(
            text("INSERT INTO conversations (teacher_id, parent_id, student_name) VALUES (:t,:p,:s)"),
            {"t": ids["teacher1"], "p": ids[parent], "s": student},
        )
    db.commit()
    print("시드 완료: teacher1 / parent1 / parent2  (비밀번호 모두 test1234)")
