"""요약(summary)이 없는 예전 학부모 메시지에 요약만 채운다 (정제문 · 판정 · 다른 분석은 그대로 둔다).

    cd backend && .venv/bin/python dev/backfill_summary.py          # 몇 건인지만 보여 줌
    cd backend && .venv/bin/python dev/backfill_summary.py --run    # Claude 로 채움 (건당 약 $0.006)

요약은 정제 호출이 같이 쓰므로, 정제를 한 번 더 돌려 summary 만 가져온다. 서버를 끄지 않아도 된다
(화면은 다음 갱신 때 · 새로 고침하면 보임). 정제 스위치와 상관없이 부른다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.ai.refine import refine_message  # noqa: E402
from app.ai.roster import class_roster  # noqa: E402
from app.db import crud  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402

FIND = text(
    "SELECT m.id, m.raw_text, c.id AS conv_id FROM messages m JOIN conversations c ON c.id = m.conversation_id "
    "WHERE m.sender_id = c.parent_id AND m.status = 'done' AND m.analysis IS NOT NULL "
    "AND NOT (m.analysis ? 'summary') ORDER BY m.id"
)


def main(run: bool) -> None:
    with SessionLocal() as db:
        rows = db.execute(FIND).mappings().all()
    print(f"요약이 없는 학부모 메시지 {len(rows)}건")
    if not run or not rows:
        if rows:
            print("채우려면 --run")
        return
    ok = 0
    for r in rows:
        with SessionLocal() as db:
            conv = crud.get_conversation(db, r["conv_id"])
            adults = crud.adult_names(db)
            roster = class_roster(crud.student_names(db, conv["teacher_id"]), conv["student_name"])
        result = refine_message(r["raw_text"], roster, adults)
        summary = (result.get("analysis") or {}).get("summary")
        if result["status"] != "done" or not summary:
            print(f"  #{r['id']} 실패: {result.get('error') or '요약 없음'}")
            continue
        with SessionLocal() as db:
            db.execute(text("UPDATE messages SET analysis = analysis || jsonb_build_object('summary', CAST(:s AS TEXT)) "
                            "WHERE id = :i"), {"s": summary, "i": r["id"]})
            db.commit()
        ok += 1
        print(f"  #{r['id']} → {summary}")
    print(f"{ok}/{len(rows)}건 채움")


if __name__ == "__main__":
    main("--run" in sys.argv)
