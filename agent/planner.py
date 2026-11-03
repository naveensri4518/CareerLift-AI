"""Learning Planner (DESIGN.md section 11).

Deterministic selection: the next exercise targets the student's highest-frequency open misconception,
read from the SQLite tally. The model is NOT used to decide — only (optionally, later) to phrase. Selection
is a pure function of the tally, so it is fully testable with no model call.
"""
from __future__ import annotations

from . import db, fairscore, interview


def _concept_to_topic(concept_id: str) -> str | None:
    for q in interview.QUESTION_BANK:
        if concept_id in q["concepts"]:
            return q["topic"]
    return None


def next_exercise(student_id: str, db_path: str | None = None) -> dict:
    """Pick the next exercise. Delegates to the Phase 0 recommender (one ranking source) when it has a
    recommendation; otherwise falls back to the tally/general logic. Return shape is unchanged so the
    existing /next route still adapts it into NextExerciseResponse. Deterministic; no model call."""
    # Phase 0: prefer the unified recommender. It ranks open misconceptions > low-mastery > spaced-due.
    try:
        from .skills import recommend
        rec = recommend.top(student_id, db_path=db_path)
    except Exception:  # noqa: BLE001 — recommender must never break the existing planner
        rec = None
    if rec and rec.get("target_ref"):
        topic = rec["target_ref"]
        q = interview.generate_question(topic=topic)
        return {"topic": topic, "concept_id": rec["concept_id"], "question": q, "reason": rec["reason"]}

    tally = db.misconception_tally(student_id, db_path)
    misconception_meta = {m["id"]: m for m in fairscore.concepts().get("misconceptions", [])}

    if tally:
        top = tally[0]  # highest count, then most recent (ordered by the query)
        concept_id = top["concept_id"]
        topic = _concept_to_topic(concept_id)
        reason = misconception_meta.get(top["tag"], {}).get("text", top["tag"])
        if topic:
            q = interview.generate_question(topic=topic)
            return {"topic": topic, "concept_id": concept_id, "question": q,
                    "reason": f"Most frequent gap: {reason} (seen {top['count']}x)."}

    # no misconceptions yet -> a general question
    q = interview.generate_question(topic=None, seed=len(tally))
    return {"topic": q["topic"], "concept_id": q["expected_concepts"][0], "question": q,
            "reason": "No recurring gaps yet; here is a general question to continue practising."}
