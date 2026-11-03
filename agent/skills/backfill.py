"""One-time, idempotent backfill of SkillSignals from persisted answers (PHASE_0_IMPLEMENTATION_SPEC §9).

Reads ONLY persisted answer rows. NEVER re-runs the evaluator/model. Idempotent via UNIQUE dedup_key.
Does NOT backfill historical `interview_scored` activity events (spec §9.1) — the activity calendar
begins from Phase 0 activation onward; we never invent timestamps.

Run:  python -m agent.skills.backfill
"""
from __future__ import annotations

from .. import db
from . import learner_model, signals


def backfill_student(student_id: str, db_path: str | None = None) -> dict:
    answers = db.answers_for_student(student_id, db_path)
    created = 0
    for ans in answers:
        row = {**ans, "student_id": student_id}
        sigs = signals.signals_from_answer(row)
        for sig in sigs:
            if db.insert_skill_signal(sig, db_path) is not None:
                created += 1
    learner_model.rebuild(student_id, db_path)
    return {"student_id": student_id, "answers": len(answers), "signals_created": created}


def backfill_all(db_path: str | None = None) -> list[dict]:
    return [backfill_student(sid, db_path) for sid in db.all_student_ids(db_path)]


def main() -> int:
    db.init_db()
    results = backfill_all()
    total = sum(r["signals_created"] for r in results)
    print(f"Backfill complete: {len(results)} students, {total} new signals.")
    for r in results:
        print(f"  {r['student_id']}: {r['answers']} answers -> {r['signals_created']} new signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
