"""Activity events — idempotent, kind-dependent keys (PHASE_0_IMPLEMENTATION_SPEC §8.1).

Deterministic, local, no model/AWS. Keys:
  interview_scored      -> sha256(student | 'interview_scored' | answer:<id>)   (one per answer)
  misconception_opened  -> sha256(student | 'misconception_opened' | <signal_id>)   (one per grounded misconception signal, incl. recurrence)
  misconception_resolved-> sha256(student | 'misconception_resolved' | <signal_id>) (one per RESOLVE_N-completing signal)
"""
from __future__ import annotations

import hashlib

from . import db


def _key(student_id: str, kind: str, ref_id: str) -> str:
    return hashlib.sha256(f"{student_id}|{kind}|{ref_id}".encode("utf-8")).hexdigest()


def record(student_id: str, kind: str, ref_id: str, created_at: str | None = None,
           db_path: str | None = None) -> bool:
    """Record an activity event idempotently. Returns True if newly inserted, False if a duplicate no-op."""
    key = _key(student_id, kind, str(ref_id))
    return db.insert_activity_event(student_id, kind, str(ref_id), key, created_at, db_path)


def record_interview_scored(student_id: str, answer_id: int, created_at: str | None = None,
                            db_path: str | None = None) -> bool:
    return record(student_id, "interview_scored", f"answer:{answer_id}", created_at, db_path)


def record_transition(student_id: str, kind: str, signal_id: int, created_at: str | None = None,
                      db_path: str | None = None) -> bool:
    """Record a misconception lifecycle event keyed by the triggering/resolving signal id."""
    return record(student_id, kind, str(signal_id), created_at, db_path)
