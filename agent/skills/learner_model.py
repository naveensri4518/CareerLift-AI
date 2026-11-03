"""Mastery state machine — deterministic, reversible, reproducible (PHASE_0_IMPLEMENTATION_SPEC §6.3).

Pure function of a concept's ordered skill_signal rows. No model, no AWS. The label never depends on
recency (recency affects only recommendation ranking). "update" == "replay": every update replays all of
a concept's signals from scratch, so incremental results are identical to a full rebuild by construction.

The replay also collects EVERY misconception lifecycle event (opens — including recurrence-while-open —
and resolutions), each keyed by its triggering/resolving signal id, so the activity log is a faithful,
idempotent projection (spec §6.3.8).
"""
from __future__ import annotations

from .. import activity, db

# States (ordinal). Index is the ordinal value.
STATES = ["Not enough evidence", "Emerging", "Developing", "Proficient", "Strong"]
NOT_ENOUGH, EMERGING, DEVELOPING, PROFICIENT, STRONG = range(5)

# Calibrated constants (spec §6.3; defaults confirmed in §14).
EVIDENCE_FLOOR = 3   # independent successes -> Proficient
STRONG_FLOOR = 5     # independent successes -> Strong
RESOLVE_N = 2        # consecutive independent successes (no intervening reset) to resolve a misconception


def _ladder(isucc: int) -> int:
    if isucc >= STRONG_FLOOR:
        return STRONG
    if isucc >= EVIDENCE_FLOOR:
        return PROFICIENT
    if isucc == 2:
        return DEVELOPING
    if isucc == 1:
        return EMERGING
    return NOT_ENOUGH


def replay(signals: list[dict]) -> dict:
    """Replay ordered signals through the state machine. Returns the derived learner_concept fields plus
    the ordered list of misconception lifecycle events (kind, signal_id, created_at).

    `signals` must already be ordered by (created_at, id). Each: {id, outcome, independent_key, created_at}.
    """
    label = NOT_ENOUGH
    independent_success_keys: set[str] = set()
    evidence_count = 0
    open_misconception = False
    resolve_streak = 0
    last_seen = None
    saw_partial = False
    events: list[tuple[str, int, str]] = []

    for s in signals:
        outcome = s["outcome"]
        evidence_count += 1
        last_seen = s["created_at"]

        if outcome == "mastered":
            key = s["independent_key"]
            if key not in independent_success_keys:          # a genuine, not-yet-counted independent success
                independent_success_keys.add(key)
                if open_misconception:
                    resolve_streak += 1
                    if resolve_streak >= RESOLVE_N:
                        open_misconception = False
                        resolve_streak = 0
                        events.append(("misconception_resolved", s["id"], s["created_at"]))
                label = _ladder(len(independent_success_keys))
                if open_misconception:
                    label = min(label, DEVELOPING)
            # duplicate already-counted success: no change to independence/streak/label
        elif outcome == "partial":
            saw_partial = True
            if open_misconception:
                resolve_streak = 0                            # intervening non-success breaks the run
            if label == NOT_ENOUGH:
                label = EMERGING                              # engaged but not demonstrated
        elif outcome == "misconception":
            # EVERY grounded misconception signal (initial open OR recurrence) records its own event.
            resolve_streak = 0
            events.append(("misconception_opened", s["id"], s["created_at"]))
            open_misconception = True
            label = min(label, DEVELOPING)
        elif outcome == "struggled":
            # Not emitted in Phase 0; future-only. Drop one step, floored at Emerging if any success.
            if open_misconception:
                resolve_streak = 0
            if independent_success_keys:
                label = max(EMERGING, label - 1)
            else:
                label = NOT_ENOUGH

    # a lingering partial with no successes shows Emerging
    if label == NOT_ENOUGH and saw_partial:
        label = EMERGING

    return {
        "label": STATES[label],
        "label_ordinal": label,
        "evidence_count": evidence_count,
        "independent_success_count": len(independent_success_keys),
        "open_misconception": open_misconception,
        "last_seen": last_seen,
        "events": events,
    }


def update(student_id: str, concept_id: str, db_path: str | None = None) -> dict:
    """Recompute one concept's learner_concept from its signals (a full per-concept replay), persist it,
    and record any newly-detected misconception lifecycle events (idempotent via signal-id event keys)."""
    signals = db.signals_for_concept(student_id, concept_id, db_path)
    result = replay(signals)
    db.upsert_learner_concept(student_id, concept_id, {
        "label": result["label"],
        "confidence": 0.0,                      # unused in Phase 0
        "evidence_count": result["evidence_count"],
        "independent_success_count": result["independent_success_count"],
        "open_misconception": result["open_misconception"],
        "last_seen": result["last_seen"],
    }, db_path)
    # Record every collected lifecycle event; idempotent on repeat (keyed by signal id).
    for kind, signal_id, created_at in result["events"]:
        activity.record_transition(student_id, kind, signal_id, created_at, db_path)
    return result


def rebuild(student_id: str, db_path: str | None = None) -> None:
    """Recompute every concept the student has signals for. Equivalent to calling update() per concept."""
    for concept_id in db.signal_concepts_for_student(student_id, db_path):
        update(student_id, concept_id, db_path)
