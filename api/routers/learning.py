"""Learning Intelligence router (Phase 0). Deterministic, no model/AWS.

Endpoints (owner-authorized; does NOT register /next — that stays on `app`, spec §7.3):
  GET /students/{id}/skills
  GET /students/{id}/recommendations
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from agent import db
from agent.skills import recommend

from ..deps import require_owner

router = APIRouter(tags=["learning"])

_LABEL_ORDINAL = {"Not enough evidence": 0, "Emerging": 1, "Developing": 2, "Proficient": 3, "Strong": 4}


@router.get("/students/{student_id}/skills")
def skills(student_id: str, authed: str = Depends(require_owner)) -> dict:
    concepts = db.learner_concepts_for_student(authed)
    # NOTE: no `confidence` field is serialized (spec §6.4/§8).
    out_concepts = [
        {
            "concept_id": c["concept_id"],
            "label": c["label"],
            "evidence_count": c["evidence_count"],
            "independent_success_count": c["independent_success_count"],
            "open_misconception": c["open_misconception"],
            "last_seen": c["last_seen"],
        }
        for c in concepts
    ]
    summary = {
        "tracked": len(out_concepts),
        "proficient_or_above": sum(1 for c in out_concepts if _LABEL_ORDINAL.get(c["label"], 0) >= 3),
        "developing": sum(1 for c in out_concepts if c["label"] == "Developing"),
        "open_misconceptions": sum(1 for c in out_concepts if c["open_misconception"]),
    }
    return {"concepts": out_concepts, "summary": summary}


@router.get("/students/{student_id}/recommendations")
def recommendations(student_id: str, authed: str = Depends(require_owner)) -> dict:
    return {"recommendations": recommend.rank(authed)}
