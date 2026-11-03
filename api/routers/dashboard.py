"""Career Dashboard router (Phase 0). Deterministic, no model/AWS. All metrics from stored data only.

Endpoints (owner-authorized):
  GET /students/{id}/overview
  GET /students/{id}/activity?days=90
"""
from __future__ import annotations

import collections
import datetime as dt

from fastapi import APIRouter, Depends

from agent import db

from ..deps import require_owner

router = APIRouter(tags=["dashboard"])

_LABEL_ORDINAL = {"Not enough evidence": 0, "Emerging": 1, "Developing": 2, "Proficient": 3, "Strong": 4}


def _streak_days(event_dates: list[str]) -> int:
    """Consecutive-day streak ending today (UTC) from distinct activity dates. Real timestamps only."""
    days = set()
    for ts in event_dates:
        try:
            days.add(dt.datetime.fromisoformat(ts).date())
        except ValueError:
            continue
    if not days:
        return 0
    today = dt.datetime.now(dt.timezone.utc).date()
    # streak counts only if there is activity today or yesterday (grace of 1 day)
    start = today if today in days else (today - dt.timedelta(days=1))
    if start not in days:
        return 0
    streak, cur = 0, start
    while cur in days:
        streak += 1
        cur -= dt.timedelta(days=1)
    return streak


@router.get("/students/{student_id}/overview")
def overview(student_id: str, authed: str = Depends(require_owner)) -> dict:
    history = db.interview_history(authed)
    answers_scored = sum(
        1 for h in history if not h.get("abstained_technical") or not h.get("abstained_communication")
    )
    concepts = db.learner_concepts_for_student(authed)
    events = db.activity_events_for_student(authed)
    recent = [{"kind": e["kind"], "when": e["created_at"]} for e in events[-5:]][::-1]
    return {
        "interviews_completed": len(history),
        "answers_scored": answers_scored,
        "skills": {
            "tracked": len(concepts),
            "proficient_or_above": sum(1 for c in concepts if _LABEL_ORDINAL.get(c["label"], 0) >= 3),
            "open_misconceptions": sum(1 for c in concepts if c["open_misconception"]),
        },
        "streak_days": _streak_days([e["created_at"] for e in events]),
        "recent": recent,
    }


@router.get("/students/{student_id}/activity")
def activity(student_id: str, days: int = 90, authed: str = Depends(require_owner)) -> dict:
    days = max(1, min(days, 366))
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    events = db.activity_events_for_student(authed, since=since)
    per_day: collections.Counter = collections.Counter()
    for e in events:
        try:
            d = dt.datetime.fromisoformat(e["created_at"]).date().isoformat()
            per_day[d] += 1
        except ValueError:
            continue
    return {"events": [{"date": d, "count": per_day[d]} for d in sorted(per_day)]}
