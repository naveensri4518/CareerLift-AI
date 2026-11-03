"""Phase 4 — feed System Design results into the shared Phase 0 SkillSignals / LearnerModel.

Additive and non-invasive: REUSES the Phase 0 primitives (db.insert_skill_signal, learner_model.update)
exactly as the interview/coding/assessment paths do, with source_module="sysdesign". Concept ids validate
against the UNION of the FairScore, assessment and sysdesign taxonomies — WITHOUT modifying any of those
files. A graded design therefore contributes independent evidence toward the SAME concept mastery.

Mapping per dimension concept (from sysdesign_eval.dimension_outcomes):
  'correct'   (dimension score >= 0.75) -> "mastered"/medium signal
  'incorrect' (dimension score < 0.5)   -> "struggled"/medium signal
  'partial'                             -> no signal (ambiguous; conservative)

Signals are idempotent on dedup_key (student|sysdesign|evidence_ref|concept|outcome). No model / AWS.
This module does NOT modify signals.py, learner_model.py, activity.py or fairscore.py.
"""
from __future__ import annotations

import hashlib

from . import assessment_bank, fairscore, sysdesign_bank
from .skills import learner_model

SOURCE = "sysdesign"


def _valid_concepts() -> set[str]:
    return (set(fairscore.concept_ids())
            | set(assessment_bank.assessment_concept_ids())
            | set(sysdesign_bank.sysdesign_concept_ids()))


def _dedup_key(student_id: str, evidence_ref: str, concept_id: str, outcome: str) -> str:
    raw = f"{student_id}|{SOURCE}|{evidence_ref}|{concept_id}|{outcome}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def signals_from_result(student_id: str, attempt_id: int, outcomes: dict[str, str]) -> list[dict]:
    """Build (not persist) skill-signal dicts for one graded attempt.
    `outcomes`: {concept_id: 'correct'|'incorrect'|'partial'} from sysdesign_eval.dimension_outcomes."""
    valid = _valid_concepts()
    evidence_ref = f"sysdesign:{attempt_id}"
    out: list[dict] = []
    for concept_id, outcome in outcomes.items():
        if concept_id not in valid:
            continue  # fail-closed against the shared taxonomy
        if outcome == "correct":
            o, strength = "mastered", "medium"
        elif outcome == "incorrect":
            o, strength = "struggled", "medium"
        else:
            continue  # partial -> no signal
        out.append({
            "student_id": student_id,
            "concept_id": concept_id,
            "source_module": SOURCE,
            "outcome": o,
            "strength": strength,
            "confidence": 0.0,
            "evidence_ref": evidence_ref,
            "independent_key": f"sd:{evidence_ref}:{concept_id}",
            "dedup_key": _dedup_key(student_id, evidence_ref, concept_id, o),
            "created_at": None,
        })
    return out


def emit_from_result(student_id: str, attempt_id: int, outcomes: dict[str, str],
                     db_path: str | None = None) -> list[str]:
    """Persist signals for one graded design (idempotent) and update every touched concept's mastery
    through the SAME learner_model state machine. Returns the touched concept_ids."""
    from . import db

    sigs = signals_from_result(student_id, attempt_id, outcomes)
    touched: set[str] = set()
    for sig in sigs:
        db.insert_skill_signal(sig, db_path)   # INSERT OR IGNORE on dedup_key
        touched.add(sig["concept_id"])
    for concept_id in touched:
        learner_model.update(student_id, concept_id, db_path)
    return sorted(touched)
