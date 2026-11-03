"""Secure Coding Arena router (Phase 2). Owner-authorized. Student code is executed ONLY inside an
isolated Docker sandbox (agent/coding_exec.py); if the sandbox is unavailable the endpoints fail CLOSED
with a 503 — there is no insecure fallback. Hidden test cases are NEVER exposed to the client. Graded
submissions feed the shared Phase 0 SkillSignals / mastery model.

Endpoints:
  GET  /coding/problems                 list problems (difficulty + concept badges; no tests)
  GET  /coding/problems/{id}            full problem (description, PUBLIC tests only, limits)
  GET  /coding/languages                supported languages for the selector
  GET  /coding/status                   sandbox availability (so the UI can warn honestly)
  POST /coding/run                      run PUBLIC sample tests only (no persistence, no hidden tests)
  POST /coding/submit                   grade against ALL tests, persist, emit Phase 0 signals
  GET  /coding/submissions              my submission history (optionally filtered by problem)
  GET  /coding/submissions/{id}         one of my submissions (full result payload)
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent import (
    activity,
    coding_eval,
    coding_exec,
    coding_languages,
    coding_problems,
    coding_signals,
    db,
)

from ..auth import current_student

router = APIRouter(prefix="/coding", tags=["coding"])
_log = logging.getLogger("careerlift")

Language = Literal["python", "cpp", "java"]
MAX_SOURCE_CHARS = 60000


class RunRequest(BaseModel):
    problem_id: str = Field(min_length=1, max_length=64)
    language: Language
    source: str = Field(min_length=1, max_length=MAX_SOURCE_CHARS)


class SubmitRequest(RunRequest):
    pass


def _problem_or_404(problem_id: str) -> dict:
    p = coding_problems.get_problem(problem_id)
    if p is None:
        raise HTTPException(status_code=404, detail="problem not found")
    return p


# ---- catalogue (read-only, no execution) ----

@router.get("/problems")
def list_problems(student_id: str = Depends(current_student)) -> dict:
    solved = set(db.solved_coding_problem_ids(student_id))
    items = []
    for p in coding_problems.public_list():
        items.append({**p, "solved": p["id"] in solved})
    return {"problems": items}


@router.get("/problems/{problem_id}")
def get_problem(problem_id: str, student_id: str = Depends(current_student)) -> dict:
    p = _problem_or_404(problem_id)
    # public_view intentionally excludes hidden tests.
    view = coding_problems.public_view(p)
    view["solved"] = problem_id in set(db.solved_coding_problem_ids(student_id))
    return view


@router.get("/languages")
def languages(student_id: str = Depends(current_student)) -> dict:
    return {"languages": coding_languages.public_languages()}


@router.get("/status")
def status(student_id: str = Depends(current_student)) -> dict:
    """Report whether the secure sandbox is ready. The UI uses this to warn honestly that code cannot be
    run until Docker is available — instead of failing only at submit time."""
    ok, reason = coding_exec.preflight()
    return {"sandbox_available": ok, "reason": reason if not ok else "ok"}


# ---- execution (sandbox-only, fail-closed) ----

@router.post("/run")
def run(req: RunRequest, student_id: str = Depends(current_student)) -> dict:
    """Run PUBLIC sample tests only. Never touches hidden tests; nothing is persisted."""
    problem = _problem_or_404(req.problem_id)
    try:
        result = coding_eval.run_only(problem, req.language, req.source)
    except coding_exec.SandboxUnavailableError as e:
        raise HTTPException(status_code=503, detail=e.user_message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/submit")
def submit(req: SubmitRequest, student_id: str = Depends(current_student)) -> dict:
    """Grade against ALL tests (public + hidden), persist the submission, and feed the verdict into the
    shared Phase 0 mastery model. Hidden test I/O is never returned."""
    problem = _problem_or_404(req.problem_id)
    try:
        result = coding_eval.evaluate_submission(problem, req.language, req.source)
    except coding_exec.SandboxUnavailableError as e:
        raise HTTPException(status_code=503, detail=e.user_message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    submission_id = db.create_coding_submission(
        student_id=student_id,
        problem_id=req.problem_id,
        language=req.language,
        source=req.source,
        verdict=result["verdict"],
        tests_passed=result["tests_passed"],
        tests_total=result["tests_total"],
        max_time_ms=result.get("max_time_ms"),
        result=result,
    )

    # Phase 0 integration + activity, AFTER persistence and wrapped so a failure can never alter the
    # response (same discipline as /score and studio submit). Deterministic/local — no model or AWS.
    try:
        coding_signals.emit_from_verdict(student_id, submission_id, problem.get("concept_ids", []),
                                         result["verdict"])
        if result["verdict"] == "ACCEPTED":
            activity.record(student_id, "coding_solved", f"coding:{submission_id}")
        else:
            activity.record(student_id, "coding_attempted", f"coding:{submission_id}")
    except Exception:  # noqa: BLE001 — best-effort projection; never break a successful submit
        _log.debug("coding signal/activity emission failed for submission %s", submission_id)

    return {"submission_id": submission_id, **result}


# ---- history (owner-scoped) ----

@router.get("/submissions")
def list_submissions(problem_id: str | None = None, student_id: str = Depends(current_student)) -> dict:
    return {"submissions": db.list_coding_submissions(student_id, problem_id)}


@router.get("/submissions/{submission_id}")
def get_submission(submission_id: int, student_id: str = Depends(current_student)) -> dict:
    sub = db.get_coding_submission(submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="submission not found")
    if sub["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="this submission does not belong to you")
    return sub
