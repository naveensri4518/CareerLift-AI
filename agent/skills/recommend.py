"""Recommendation engine — deterministic ranking + explanation contract (PHASE_0_IMPLEMENTATION_SPEC §7).

No model, no AWS. Focus = the student's attempted concepts + open misconceptions (no invented
prerequisites). Every recommendation carries a non-empty reason + real evidence_summary. When there is no
evidence, returns an empty list (the /next route still returns a full NextExerciseResponse — see planner).
"""
from __future__ import annotations

import datetime as dt

from .. import db, fairscore

# Spaced-repetition interval per label (days). Deterministic table (spec §7.1).
INTERVAL_DAYS = {"Emerging": 1, "Developing": 3, "Proficient": 7, "Strong": 16}
RECENCY_WINDOW_DAYS = 30

_LABEL_ORDINAL = {"Not enough evidence": 0, "Emerging": 1, "Developing": 2, "Proficient": 3, "Strong": 4}


def _concept_title(concept_id: str) -> str:
    c = fairscore.concept_by_id().get(concept_id, {})
    return c.get("canonical_name", concept_id)


def _topic_for_concept(concept_id: str) -> str | None:
    # map a concept to a practice topic via the interview question bank
    from .. import interview
    for q in interview.QUESTION_BANK:
        if concept_id in q["concepts"]:
            return q["topic"]
    return None


def _parse(ts: str | None):
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts)
    except ValueError:
        return None


def _misconception_counts(student_id: str, db_path):
    return {m["concept_id"]: m for m in db.misconception_tally(student_id, db_path)}


def rank(student_id: str, now: dt.datetime | None = None, db_path: str | None = None) -> list[dict]:
    """Return ranked recommendations (highest priority first). Empty when there is no evidence."""
    now = now or dt.datetime.now(dt.timezone.utc)
    concepts = db.learner_concepts_for_student(student_id, db_path)
    if not concepts:
        return []
    misc = _misconception_counts(student_id, db_path)
    recs: list[dict] = []

    # Tier 1: open misconceptions
    tier1 = [c for c in concepts if c["open_misconception"]]
    tier1.sort(key=lambda c: (-(misc.get(c["concept_id"], {}).get("count", 0)),
                              -( _parse(c["last_seen"]).timestamp() if _parse(c["last_seen"]) else 0),
                              c["concept_id"]))
    for c in tier1:
        cid = c["concept_id"]
        count = misc.get(cid, {}).get("count", 0)
        recs.append(_rec("revise", cid, "misconception",
                         f"You showed a misconception about {_concept_title(cid)}"
                         + (f" (seen {count}x)" if count else "") + ". Revisit the concept, then try a fresh question.",
                         {"misconception_count": count,
                          "independent_successes": c["independent_success_count"],
                          "last_seen": c["last_seen"]}))

    # Tier 2: low-mastery attempted concepts (not already in tier 1)
    tier1_ids = {c["concept_id"] for c in tier1}
    tier2 = [c for c in concepts if c["concept_id"] not in tier1_ids
             and _LABEL_ORDINAL.get(c["label"], 0) <= _LABEL_ORDINAL["Developing"]]
    tier2.sort(key=lambda c: (_LABEL_ORDINAL.get(c["label"], 0),
                              _parse(c["last_seen"]).timestamp() if _parse(c["last_seen"]) else 0,
                              c["concept_id"]))
    for c in tier2:
        cid = c["concept_id"]
        recs.append(_rec("practice", cid, "prerequisite",
                         f"Your mastery of {_concept_title(cid)} is {c['label']}. "
                         f"Practising it will strengthen your foundation.",
                         {"label": c["label"],
                          "independent_successes": c["independent_success_count"],
                          "last_seen": c["last_seen"]}))

    # Tier 3: spaced-repetition due (proficient/strong not practised within interval)
    handled = tier1_ids | {c["concept_id"] for c in tier2}
    due = []
    for c in concepts:
        if c["concept_id"] in handled:
            continue
        interval = INTERVAL_DAYS.get(c["label"])
        seen = _parse(c["last_seen"])
        if interval is None or seen is None:
            continue
        due_at = seen + dt.timedelta(days=interval)
        if due_at <= now and (now - due_at).days <= RECENCY_WINDOW_DAYS:
            due.append((c, (now - due_at)))
    due.sort(key=lambda t: (-t[1].total_seconds(), t[0]["concept_id"]))
    for c, overdue in due:
        cid = c["concept_id"]
        recs.append(_rec("revise", cid, "spaced_due",
                         f"It's a good time to refresh {_concept_title(cid)} to keep it sharp.",
                         {"label": c["label"], "last_seen": c["last_seen"],
                          "overdue_days": overdue.days}))
    return recs


def _rec(action: str, concept_id: str, priority: str, reason: str, evidence_summary: dict) -> dict:
    return {
        "action": action,
        "target_module": "interview",
        "target_ref": _topic_for_concept(concept_id),
        "concept_id": concept_id,
        "reason": reason,
        "priority": priority,
        "evidence_summary": evidence_summary,
    }


def top(student_id: str, db_path: str | None = None) -> dict | None:
    """The single highest-priority recommendation, or None when there is no evidence."""
    recs = rank(student_id, db_path=db_path)
    return recs[0] if recs else None
