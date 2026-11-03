"""Phase 2 — feed coding results into the shared Phase 0 SkillSignals / LearnerModel.

This is additive: it REUSES the Phase 0 primitives (db.insert_skill_signal, learner_model.update) exactly
as the interview path does, but with source_module="coding" (a value the skill_signal schema explicitly
reserves). It does NOT modify any Phase 0 file. A coding submission therefore contributes independent
evidence toward the SAME concept mastery as interviews — the intended cross-module unification.

Mapping (deterministic, conservative — no fabricated mastery):
  ACCEPTED            -> one "mastered"/strong signal per problem concept_id  (independent success)
  WRONG/TLE/RUNTIME   -> one "struggled"/medium signal per concept_id         (counts as evidence, not mastery)
  COMPILATION ERROR   -> no signal (a build failure is not evidence about the concept)

Signals are idempotent on dedup_key, so re-submitting the same problem does not inflate mastery unless the
outcome changes (a distinct dedup_key). No model, no AWS.
"""
from __future__ import annotations

import hashlib

from . import fairscore
from .skills import learner_model

SOURCE = "coding"


def _dedup_key(student_id: str, evidence_ref: str, concept_id: str, outcome: str) -> str:
    raw = f"{student_id}|{SOURCE}|{evidence_ref}|{concept_id}|{outcome}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def signals_from_verdict(student_id: str, submission_id: int, concept_ids: list[str], verdict: str,
                         created_at: str | None = None) -> list[dict]:
    """Build (but do not persist) skill-signal dicts for one graded submission."""
    valid = fairscore.concept_ids()
    evidence_ref = f"coding:{submission_id}"

    if verdict == "ACCEPTED":
        outcome, strength = "mastered", "strong"
    elif verdict in ("WRONG ANSWER", "TIME LIMIT EXCEEDED", "RUNTIME ERROR"):
        outcome, strength = "struggled", "medium"
    else:  # COMPILATION ERROR or anything else -> not evidence about the concept
        return []

    out: list[dict] = []
    for concept_id in concept_ids:
        if concept_id not in valid:
            continue  # fail-closed against the shared taxonomy
        out.append({
            "student_id": student_id,
            "concept_id": concept_id,
            "source_module": SOURCE,
            "outcome": outcome,
            "strength": strength,
            "confidence": 0.0,
            "evidence_ref": evidence_ref,
            "independent_key": f"cd:{evidence_ref}:{concept_id}",
            "dedup_key": _dedup_key(student_id, evidence_ref, concept_id, outcome),
            "created_at": created_at,
        })
    return out


def emit_from_verdict(student_id: str, submission_id: int, concept_ids: list[str], verdict: str,
                      created_at: str | None = None, db_path: str | None = None) -> list[str]:
    """Persist signals for one graded coding submission (idempotent) and update the affected concepts'
    mastery through the SAME learner_model state machine the interview path uses.
    Returns the list of concept_ids touched. Never raises on a taxonomy miss."""
    from . import db

    sigs = signals_from_verdict(student_id, submission_id, concept_ids, verdict, created_at)
    touched: set[str] = set()
    for sig in sigs:
        db.insert_skill_signal(sig, db_path)   # INSERT OR IGNORE on dedup_key
        touched.add(sig["concept_id"])
    for concept_id in touched:
        learner_model.update(student_id, concept_id, db_path)
    return sorted(touched)
