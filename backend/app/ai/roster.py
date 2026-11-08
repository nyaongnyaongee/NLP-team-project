"""반 학생 명단 불러오기.  [재관]

지금은 시연용 JSON 하나(sample_roster.json). DB 에 「반」이 생기거나 팀이 명단 출처를 정하면 여기만 바꾼다.
"""
import json
from pathlib import Path

SAMPLE_ROSTER = Path(__file__).parent / "sample_roster.json"


def load_sample_roster() -> list[str]:
    return json.loads(SAMPLE_ROSTER.read_text(encoding="utf-8"))["students"]
