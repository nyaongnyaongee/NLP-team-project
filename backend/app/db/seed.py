# 테스트 데이터 넣기  [어령]   실행: cd backend && python -m app.db.seed
# 여러 번 돌려도 된다: 없는 계정 · 학생만 더하고, 대화는 처음 만들 때만 넣는다.
# 학생: teacher1 반 = ai/sample_roster.json 20명 (가명처리 명단과 같은 이름). 예전 DB 의 대화 학생도 반에 넣는다.
# 가족: 학생 20명마다 학부모 계정 하나 (parent1 ↔ 지민 … parent20 ↔ 은우, sample_roster.json 순서). 비밀번호 모두 test1234
from sqlalchemy import text

from app.ai.roster import load_sample_roster
from app.core.auth import hash_password
from app.db.database import SessionLocal

# (학부모 login_id, 학부모 이름, 아이 이름). 학부모 이름에는 학생 이름이 들어가지 않게 골랐다 (가명처리가 헷갈리지 않게).
# parent2 「이도윤」 만 예외 — 예전부터 쓰던 계정이라 그대로 둠 (학생 「도윤」 = parent7 의 아이)
FAMILIES = [
    ("parent1", "박서연", "지민"), ("parent2", "이도윤", "민준"), ("parent3", "최은영", "현우"),
    ("parent4", "정민호", "수아"), ("parent5", "강지혜", "유나"), ("parent6", "조성민", "채원"),
    ("parent7", "윤미경", "도윤"), ("parent8", "장현철", "태호"), ("parent9", "임수진", "소율"),
    ("parent10", "한정우", "나윤"), ("parent11", "오세영", "예린"), ("parent12", "서동훈", "건우"),
    ("parent13", "신혜원", "서윤"), ("parent14", "권재석", "시우"), ("parent15", "황보람", "다은"),
    ("parent16", "안소희", "하린"), ("parent17", "송태준", "준서"), ("parent18", "류경아", "주원"),
    ("parent19", "전상훈", "지우"), ("parent20", "홍미라", "은우"),
]
assert [child for _, _, child in FAMILIES] == load_sample_roster(), "FAMILIES 아이 이름은 sample_roster.json 과 같은 순서여야 함"
USERS = [  # (role, name, login_id)
    ("teacher", "김민지", "teacher1"),
    *[("parent", name, login) for login, name, _ in FAMILIES],
    ("complaint_team", "정하은", "team1"),  # 민원대응팀 (신고 보고서 D 를 본다)
]
SEED_CHILDREN = [(login, child) for login, _, child in FAMILIES]  # 학부모 ↔ 아이
FIRST_CONVERSATIONS = SEED_CHILDREN[:2]  # 처음 만들 때 대화 2개 (parent1 ↔ 지민, parent2 ↔ 민준)

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
        for parent, student in FIRST_CONVERSATIONS:
            db.execute(
                text("INSERT INTO conversations (teacher_id, parent_id, student_name) VALUES (:t,:p,:s)"),
                {"t": ids["teacher1"], "p": ids[parent], "s": student},
            )
    teacher = db.execute(text("SELECT id FROM users WHERE login_id = 'teacher1'")).scalar()
    names = load_sample_roster() + [r[0] for r in db.execute(
        text("SELECT DISTINCT student_name FROM conversations WHERE teacher_id = :t"), {"t": teacher}).all()]
    new_students = 0
    for name in dict.fromkeys(names):
        new_students += db.execute(
            text("INSERT INTO students (teacher_id, name) VALUES (:t, :n) ON CONFLICT DO NOTHING"), {"t": teacher, "n": name},
        ).rowcount
    db.execute(text(  # 대화 ↔ 학생 잇기 (이름이 같으면)
        "UPDATE conversations c SET student_id = s.id FROM students s "
        "WHERE c.student_id IS NULL AND s.teacher_id = c.teacher_id AND s.name = c.student_name"))
    db.execute(text(  # 학생 ↔ 학부모: 이미 있는 대화에서
        "UPDATE students s SET parent_id = c.parent_id FROM conversations c "
        "WHERE s.parent_id IS NULL AND c.student_id = s.id"))
    linked = 0
    for parent, student in SEED_CHILDREN:  # 대화가 없어도 시드 학부모는 아이가 있게
        linked += db.execute(text("UPDATE students SET parent_id = (SELECT id FROM users WHERE login_id = :p) "
                        "WHERE teacher_id = :t AND name = :n AND parent_id IS NULL"), {"p": parent, "t": teacher, "n": student}).rowcount
    if len(added) > 4:  # 계정이 많으면 줄여서
        added = [f"계정 {len(added)}개 ({added[0]} … {added[-1]})"]
    if new_students:
        added.append(f"학생 {new_students}명")
    if linked:
        added.append(f"학생 ↔ 학부모 {linked}쌍")
    db.commit()
    print("시드: " + (", ".join(added) + " 추가" if added else "이미 다 있음 (건너뜀)") + "  (비밀번호 모두 test1234)")
