"""SkillSignal emission from a persisted interview answer (PHASE_0_IMPLEMENTATION_SPEC §6.1, §6.2, §8.1).

Deterministic, local, NO model/AWS. Reads only persisted answer fields + the concept taxonomy.

Mapping (Phase 0, interview source):
  - each grounded misconception tag -> a `misconception` signal for that tag's concept (strength=strong);
  - per the "same-evidence precedence" rule, a concept with a misconception on THIS answer does NOT also
    get a positive signal from the same answer;
  - `mastered`/`partial` are emitted ONLY when actual persisted per-concept evaluation evidence exists.
    An overall technical band ALONE never establishes per-concept mastery, so with the current persisted
    schema (overall bands + misconception tags) the reliably-available positive evidence is absent and
    only misconception signals are produced. (Richer per-concept persistence is a later, separate change.)
"""
from __future__ import annotations

import hashlib

from .. import db, fairscore
from . import learner_model

SOURCE = "interview"


def _dedup_key(student_id: str, evidence_ref: str, concept_id: str, outcome: str) -> str:
    raw = f"{student_id}|{SOURCE}|{evidence_ref}|{concept_id}|{outcome}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _tag_to_concept() -> dict:
    return {m["id"]: m.get("about") for m in fairscore.concepts().get("misconceptions", [])}


def signals_from_answer(answer: dict) -> list[dict]:
    """Build the signal dicts for one persisted answer. Pure (no DB writes). `answer` must include
    id, misconception_tags, created_at, and the owning student_id (added by the caller)."""
    student_id = answer["student_id"]
    answer_id = answer["id"]
    evidence_ref = f"answer:{answer_id}"
    created_at = answer.get("created_at")
    valid_ids = fairscore.concept_ids()
    tag_concept = _tag_to_concept()

    # Concepts with a grounded misconception on THIS answer (precedence: these block positive signals).
    misconception_concepts: set[str] = set()
    out: list[dict] = []
    for tag in answer.get("misconception_tags", []) or []:
        concept_id = tag_concept.get(tag)
        if not concept_id or concept_id not in valid_ids:
            continue  # fail-closed on unknown taxonomy ids
        misconception_concepts.add(concept_id)
        out.append({
            "student_id": student_id, "concept_id": concept_id, "source_module": SOURCE,
            "outcome": "misconception", "strength": "strong", "confidence": 0.0,
            "evidence_ref": evidence_ref,
            "independent_key": f"iv:{evidence_ref}:{concept_id}",
            "dedup_key": _dedup_key(student_id, evidence_ref, concept_id, "misconception"),
            "created_at": created_at,
        })

    # Per-concept positive evidence: only if the answer carries persisted per-concept status. The current
    # schema does NOT persist per-concept supported/partial, so no mastered/partial is derived from an
    # overall band (spec §6.1 corrected). If a future answer row includes a `concept_status` map, it is
    # honored here; concepts with a misconception on this answer are skipped (precedence).
    per_concept = answer.get("concept_status") or {}
    for concept_id, status in per_concept.items():
        if concept_id in misconception_concepts:
            continue  # same-evidence precedence: misconception wins for this (answer, concept)
        if concept_id not in valid_ids:
            continue
        if status == "supported":
            outcome, strength = "mastered", "medium"
        elif status == "partial":
            outcome, strength = "partial", "weak"
        else:
            continue  # absent -> no signal
        out.append({
            "student_id": student_id, "concept_id": concept_id, "source_module": SOURCE,
            "outcome": outcome, "strength": strength, "confidence": 0.0,
            "evidence_ref": evidence_ref,
            "independent_key": f"iv:{evidence_ref}:{concept_id}",
            "dedup_key": _dedup_key(student_id, evidence_ref, concept_id, outcome),
            "created_at": created_at,
        })
    return out


def emit_from_answer(student_id: str, answer: dict, db_path: str | None = None) -> list[str]:
    """Persist signals for one answer (idempotent) and update affected concepts' mastery.
    Returns the list of concept_ids touched. NO model/AWS."""
    ans = {**answer, "student_id": student_id}
    sigs = signals_from_answer(ans)
    touched: set[str] = set()
    for sig in sigs:
        db.insert_skill_signal(sig, db_path)   # INSERT OR IGNORE on dedup_key
        touched.add(sig["concept_id"])
    for concept_id in touched:
        learner_model.update(student_id, concept_id, db_path)
    return sorted(touched)
