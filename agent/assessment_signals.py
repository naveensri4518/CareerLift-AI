"""Phase 3 — feed assessment results into the shared Phase 0 SkillSignals / LearnerModel.

Additive and non-invasive: it REUSES the Phase 0 primitives (db.insert_skill_signal, learner_model.update)
exactly as the interview and coding paths do, with source_module="assessment". It validates concept ids
against the UNION of the FairScore taxonomy (agent/data/concepts.json) and the assessment taxonomy
(agent/data/assessment_concepts.json) — WITHOUT modifying either file, so the measured FairScore surface
is untouched. A single assessment attempt therefore contributes independent evidence toward the SAME
concept mastery as interviews and coding.

Mapping per question (deterministic, conservative):
  correct question   -> "mastered"/medium signal for each of its concept_ids   (independent success)
  incorrect question -> "struggled"/medium signal for each of its concept_ids  (evidence, not mastery)
  unanswered         -> no signal (no evidence about the concept)

Signals are idempotent on dedup_key (student|assessment|evidence_ref|concept|outcome), so re-grading the
same attempt never inflates mastery. No model / AWS.
"""
from __future__ import annotations

import hashlib

from . import assessment_bank, fairscore
from .skills import learner_model

SOURCE = "assessment"


def _valid_concepts() -> set[str]:
    # union of FairScore + assessment taxonomies; fail-closed against anything else.
    return set(fairscore.concept_ids()) | set(assessment_bank.assessment_concept_ids())


def _dedup_key(student_id: str, evidence_ref: str, concept_id: str, outcome: str) -> str:
    raw = f"{student_id}|{SOURCE}|{evidence_ref}|{concept_id}|{outcome}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def signals_from_attempt(student_id: str, attempt_id: int, question_ids: list[str],
                         per_question: dict[str, dict]) -> list[dict]:
    """Build (not persist) skill-signal dicts for one graded attempt.

    per_question: {question_id: {"status": correct|incorrect|unanswered, ...}} from assessment_eval.
    One evidence ref per (attempt, question) so each question is independent evidence.
    """
    valid = _valid_concepts()
    out: list[dict] = []
    for qid in question_ids:
        status = (per_question.get(qid) or {}).get("status")
        if status == "correct":
            outcome, strength = "mastered", "medium"
        elif status == "incorrect":
            outcome, strength = "struggled", "medium"
        else:
            continue  # unanswered -> no evidence
        q = assessment_bank.get_question(qid)
        if q is None:
            continue
        evidence_ref = f"assessment:{attempt_id}:{qid}"
        for concept_id in q.get("concept_ids", []):
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
                "independent_key": f"as:{evidence_ref}:{concept_id}",
                "dedup_key": _dedup_key(student_id, evidence_ref, concept_id, outcome),
                "created_at": None,
            })
    return out


def emit_from_attempt(student_id: str, attempt_id: int, question_ids: list[str],
                      per_question: dict[str, dict], db_path: str | None = None) -> list[str]:
    """Persist signals for one graded attempt (idempotent) and update every touched concept's mastery
    through the SAME learner_model state machine. Returns the touched concept_ids. Never raises on a
    taxonomy miss."""
    from . import db

    sigs = signals_from_attempt(student_id, attempt_id, question_ids, per_question)
    touched: set[str] = set()
    for sig in sigs:
        db.insert_skill_signal(sig, db_path)   # INSERT OR IGNORE on dedup_key
        touched.add(sig["concept_id"])
    for concept_id in touched:
        learner_model.update(student_id, concept_id, db_path)
    return sorted(touched)
