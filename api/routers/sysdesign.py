"""System Design Academy router (Phase 4). Owner-authorized, deterministic, NO model/AWS.

Lifecycle:
  GET  /sysdesign/scenarios                 list scenarios (id, title, difficulty, prompt; NO rubric)
  GET  /sysdesign/scenarios/{id}            full brief (requirements, palette, decision prompts; NO keys)
  POST /sysdesign/attempts                  start an attempt for a scenario
  GET  /sysdesign/attempts                  my attempt history
  GET  /sysdesign/attempts/{id}             resume: saved design + brief (no keys)
  POST /sysdesign/attempts/{id}/design      save draft design (rejected after submit)
  POST /sysdesign/attempts/{id}/submit      deterministic grade, persist, emit Phase 0 signals; idempotent
  GET  /sysdesign/attempts/{id}/result      full result + rubric review (expected design) — only AFTER submit

Security: rubric internals (acceptable sets, weights, feedback) are NEVER in a pre-submission payload.
Grading is 100% server-side. Ownership enforced on every attempt route. Submitted attempts are immutable.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent import activity, db, sysdesign_bank, sysdesign_eval, sysdesign_signals

from ..auth import current_student

router = APIRouter(prefix="/sysdesign", tags=["sysdesign"])
_log = logging.getLogger("careerlift")


class StartAttemptRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=64)


class DecisionAnswer(BaseModel):
    selected: list[str] = Field(default_factory=list)


class SaveDesignRequest(BaseModel):
    components: list[str] = Field(default_factory=list)
    connections: list[list[str]] = Field(default_factory=list)
    decisions: dict[str, DecisionAnswer] = Field(default_factory=dict)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _parse(ts: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _owned_attempt_or_error(attempt_id: int, student_id: str) -> dict:
    att = db.get_sysdesign_attempt(attempt_id)
    if att is None:
        raise HTTPException(status_code=404, detail="design attempt not found")
    if att["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="this attempt does not belong to you")
    return att


def _design_from_request(req: SaveDesignRequest) -> dict:
    return {
        "components": list(req.components),
        "connections": [list(c) for c in req.connections],
        "decisions": {did: {"selected": list(a.selected)} for did, a in req.decisions.items()},
    }


# ---- catalog ----

@router.get("/scenarios")
def list_scenarios(student_id: str = Depends(current_student)) -> dict:
    solved = {a["scenario_id"] for a in db.list_sysdesign_attempts(student_id)
              if a.get("status") == "submitted"}
    items = [{**s, "attempted": s["id"] in solved} for s in sysdesign_bank.public_list()]
    return {"scenarios": items, "bank_stats": sysdesign_bank.bank_stats()}


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, student_id: str = Depends(current_student)) -> dict:
    s = sysdesign_bank.get_scenario(scenario_id)
    if s is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return sysdesign_bank.public_scenario(s)   # NO rubric / acceptable sets / feedback


# ---- lifecycle ----

@router.post("/attempts")
def start_attempt(req: StartAttemptRequest, student_id: str = Depends(current_student)) -> dict:
    s = sysdesign_bank.get_scenario(req.scenario_id)
    if s is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    attempt_id = db.create_sysdesign_attempt(student_id, s["id"], s["difficulty"], _now())
    return _public_attempt(db.get_sysdesign_attempt(attempt_id))


@router.get("/attempts")
def list_attempts(student_id: str = Depends(current_student)) -> dict:
    return {"attempts": db.list_sysdesign_attempts(student_id)}


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: int, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    return _public_attempt(att)


@router.post("/attempts/{attempt_id}/design")
def save_design(attempt_id: int, req: SaveDesignRequest, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    if att["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="this attempt is already submitted")
    scenario = sysdesign_bank.get_scenario(att["scenario_id"])
    design = _design_from_request(req)
    errors = sysdesign_eval.validate_design(scenario, design)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors[:5]))
    db.save_sysdesign_design(attempt_id, design)
    return {"saved": True,
            "components": len(design["components"]),
            "connections": len(design["connections"]),
            "decisions": len(design["decisions"])}


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: int, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    if att["status"] != "in_progress":
        # idempotent: already submitted -> return the stored result
        return {"attempt_id": attempt_id, "status": att["status"], "already_submitted": True,
                "result": att["result"]}
    scenario = sysdesign_bank.get_scenario(att["scenario_id"])
    design = att["design"] or {}
    errors = sysdesign_eval.validate_design(scenario, design)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors[:5]))

    result = sysdesign_eval.grade(scenario, design)
    did = db.submit_sysdesign_attempt(attempt_id, design, result, _now())
    if not did:
        fresh = db.get_sysdesign_attempt(attempt_id)
        return {"attempt_id": attempt_id, "status": fresh["status"], "already_submitted": True,
                "result": fresh["result"]}

    # Phase 0 integration + activity, AFTER persistence, wrapped so a failure can never alter the response.
    try:
        outcomes = sysdesign_eval.dimension_outcomes(result)
        sysdesign_signals.emit_from_result(student_id, attempt_id, outcomes)
        activity.record(student_id, "sysdesign_scored", f"sysdesign:{attempt_id}")
    except Exception:  # noqa: BLE001 — best-effort projection; never break submit
        _log.debug("sysdesign signal/activity emission failed for attempt %s", attempt_id)

    return {"attempt_id": attempt_id, "status": "submitted", "already_submitted": False, "result": result}


@router.get("/attempts/{attempt_id}/result")
def get_result(attempt_id: int, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    if att["status"] != "submitted":
        raise HTTPException(status_code=409, detail="attempt not submitted yet")
    scenario = sysdesign_bank.get_scenario(att["scenario_id"])
    # Post-submission: the expected design (required components/connections) is allowed in the review.
    rubric = scenario["rubric"]
    return {
        "attempt_id": attempt_id,
        "scenario_id": att["scenario_id"],
        "title": scenario["title"],
        "difficulty": att["difficulty"],
        "status": att["status"],
        "started_at": att["started_at"],
        "submitted_at": att["submitted_at"],
        "design": att["design"],
        "result": att["result"],
        "brief": sysdesign_bank.public_scenario(scenario),
        "expected": {
            "required_components": rubric.get("required_components", []),
            "recommended_components": rubric.get("recommended_components", []),
            "required_connections": rubric.get("required_connections", []),
        },
    }


# ---- projections ----

def _public_attempt(att: dict) -> dict:
    """Pre-submission attempt view: the scenario brief (no keys) + the student's saved draft design."""
    scenario = sysdesign_bank.get_scenario(att["scenario_id"])
    brief = sysdesign_bank.public_scenario(scenario) if scenario else None
    return {
        "attempt_id": att["id"],
        "scenario_id": att["scenario_id"],
        "difficulty": att["difficulty"],
        "status": att["status"],
        "started_at": att["started_at"],
        "brief": brief,
        "design": att["design"] or {"components": [], "connections": [], "decisions": {}},
    }
