"""반 학생 명단 (가명처리용).  [재관]

명단 = 그 담임의 students 테이블 (부르는 쪽이 crud.student_names 로 읽어 넘긴다 — 이 파일은 DB 를 모른다).
반에 학생이 아직 없으면(예전 DB · 시험 DB) 시연용 JSON(sample_roster.json, 20명)을 쓴다.
대화의 학생 이름(conversations.student_name)이 명단에 없으면 더한다 — 그 아이 이름만은 꼭 가려야 하므로.
"""
import json
from pathlib import Path

SAMPLE_ROSTER = Path(__file__).parent / "sample_roster.json"


def load_sample_roster() -> list[str]:
    return json.loads(SAMPLE_ROSTER.read_text(encoding="utf-8"))["students"]


def class_roster(students: list[str], student_name: str | None = None) -> list[str]:
    names = list(students) or load_sample_roster()
    if student_name and student_name.strip() and student_name.strip() not in names:
        names.append(student_name.strip())
    return names
