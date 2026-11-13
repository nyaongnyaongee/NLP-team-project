# 테스트 데이터 넣기  [어령]   실행: cd backend && python -m app.db.seed
# 여러 번 돌려도 된다: 없는 계정만 더하고, 대화는 처음 만들 때만 넣는다.
from sqlalchemy import text

from app.core.auth import hash_password
from app.db.database import SessionLocal

USERS = [  # (role, name, login_id)
    ("teacher", "김민지", "teacher1"),
    ("parent", "박서연", "parent1"),
    ("parent", "이도윤", "parent2"),
    ("complaint_team", "정하은", "team1"),  # 민원대응팀 (신고 보고서 D 를 본다)
]

with SessionLocal() as db:
    first_time = not db.execute(text("SELECT count(*) FROM users")).scalar()
    added = []
    for role, name, login in USERS:
        if db.execute(text("SELECT 1 FROM users WHERE login_id = :l"), {"l": login}).scalar():
            continue
        db.execute(
            text("INSERT INTO users (role, name, login_id, password_hash) VALUES (:r,:n,:l,:p)"),
            {"r": role, "n": name, "l": login, "p": hash_password("test1234")},
        )
        added.append(login)
    if first_time:
        ids = dict(db.execute(text("SELECT login_id, id FROM users")).all())
        for parent, student in (("parent1", "지민"), ("parent2", "민준")):  # 학생 이름은 ai/sample_roster.json 의 20명 중에서
            db.execute(
                text("INSERT INTO conversations (teacher_id, parent_id, student_name) VALUES (:t,:p,:s)"),
                {"t": ids["teacher1"], "p": ids[parent], "s": student},
            )
    db.commit()
    print("시드: " + (", ".join(added) + " 추가" if added else "이미 다 있음 (건너뜀)") + "  (비밀번호 모두 test1234)")
