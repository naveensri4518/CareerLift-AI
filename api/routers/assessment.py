"""Technical Assessment router (Phase 3). Owner-authorized, deterministic, NO model/AWS.

Lifecycle (server-authoritative timing; the client timer is cosmetic):
  GET  /assessment/catalog                categories, difficulties, counts, durations, bank stats
  POST /assessment/attempts               start an attempt (freezes question set + option order + deadline)
  GET  /assessment/attempts               my attempt history
  GET  /assessment/attempts/{id}          resume: questions WITHOUT answer keys + saved answers + remaining time
  POST /assessment/attempts/{id}/answers  save draft answers (rejected after submit / past deadline)
  POST /assessment/attempts/{id}/submit   grade, persist, emit Phase 0 signals; idempotent
  GET  /assessment/attempts/{id}/result   full result + question-by-question review (answer keys only AFTER submit)

Security: answer keys/explanations are NEVER in a pre-submission payload. Grading is 100% server-side.
Timestamps and scores are never trusted from the client. Ownership is enforced on every attempt route.
"""
from __future__ import annotations

import datetime as dt
import logging
import secrets
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agent import activity, assessment_bank, assessment_eval, assessment_signals, db

from ..auth import current_student

router = APIRouter(prefix="/assessment", tags=["assessment"])
_log = logging.getLogger("careerlift")

Category = Literal[
    "dsa", "java", "python", "c", "cpp", "dbms", "sql", "os",
    "networks", "oop", "architecture", "software_engineering", "mixed",
]
Difficulty = Literal["beginner", "intermediate", "advanced", "mixed"]


class StartAttemptRequest(BaseModel):
    category: Category
    difficulty: Difficulty = "mixed"
    num_questions: int = Field(default=10)
    duration_min: int = Field(default=20)


class AnswerItem(BaseModel):
    # One of these is used depending on the question type; both optional so the client can send drafts.
    # The tf field is exposed to clients as "bool" (via alias) but named tf_value internally to avoid
    # shadowing the builtin `bool` type in the annotation.
    model_config = {"populate_by_name": True}
    selected: Optional[list[str]] = None                     # single/multi: option ids
    tf_value: Optional[bool] = Field(default=None, alias="bool")  # tf


class SaveAnswersRequest(BaseModel):
    # {question_id: {selected:[...]} | {bool: true}} — partial drafts allowed.
    answers: dict[str, AnswerItem] = Field(default_factory=dict)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse(ts: str) -> dt.datetime:
    d = dt.datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _owned_attempt_or_error(attempt_id: int, student_id: str) -> dict:
    att = db.get_assessment_attempt(attempt_id)
    if att is None:
        raise HTTPException(status_code=404, detail="assessment attempt not found")
    if att["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="this attempt does not belong to you")
    return att


def _answers_to_plain(answers: dict) -> dict:
    """Normalize stored/submitted answers to the shape the evaluator expects."""
    out = {}
    for qid, a in (answers or {}).items():
        if isinstance(a, dict):
            out[qid] = {"selected": a.get("selected"), "bool": a.get("bool")}
    return out


def _auto_submit_if_expired(att: dict) -> dict:
    """If an in_progress attempt is past its server deadline, finalize it as timed_out NOW (server-side),
    grade it, emit Phase 0 signals, and return the refreshed attempt. Server-authoritative — independent
    of any client clock."""
    if att["status"] != "in_progress":
        return att
    if _now() <= _parse(att["expires_at"]):
        return att
    _finalize(att, status="timed_out", answers=att["answers"])
    return db.get_assessment_attempt(att["id"])


def _finalize(att: dict, *, status: str, answers: dict) -> dict | None:
    """Grade + persist a finalization exactly once (idempotent via the guarded UPDATE). Emits Phase 0
    signals + an activity event only if THIS call performed the transition. Returns the result payload if
    it graded here, else None (already finalized by a prior/racing call)."""
    plain = _answers_to_plain(answers)
    result = assessment_eval.grade_attempt(att["question_ids"], plain)
    result.update(assessment_eval.strengths_and_weaknesses(result["by_category"]))
    submitted_at = _now().isoformat()
    did = db.submit_assessment_attempt(att["id"], status, answers, result, submitted_at)
    if not did:
        return None  # another call already finalized it; do not double-emit signals
    try:
        assessment_signals.emit_from_attempt(att["student_id"], att["id"], att["question_ids"],
                                             result["per_question"])
        activity.record(att["student_id"], "assessment_scored", f"assessment:{att['id']}")
    except Exception:  # noqa: BLE001 — best-effort projection; never break submit
        _log.debug("assessment signal/activity emission failed for attempt %s", att["id"])
    return result


# ---- catalog ----

@router.get("/catalog")
def catalog(student_id: str = Depends(current_student)) -> dict:
    cats = [c for c in assessment_bank.CATEGORIES] + ["mixed"]
    return {
        "categories": [{"id": c, "label": assessment_bank.category_label(c)} for c in cats],
        "difficulties": ["beginner", "intermediate", "advanced", "mixed"],
        "question_counts": list(assessment_bank.QUESTION_COUNTS),
        "durations_min": list(assessment_bank.DURATIONS_MIN),
        "bank_stats": assessment_bank.bank_stats(),
    }


# ---- lifecycle ----

@router.post("/attempts")
def start_attempt(req: StartAttemptRequest, student_id: str = Depends(current_student)) -> dict:
    if req.num_questions not in assessment_bank.QUESTION_COUNTS:
        raise HTTPException(status_code=400, detail="invalid question count")
    if req.duration_min not in assessment_bank.DURATIONS_MIN:
        raise HTTPException(status_code=400, detail="invalid duration")

    seed = secrets.randbelow(2**31)
    qids = assessment_bank.select_questions(req.category, req.difficulty, req.num_questions, seed)
    if not qids:
        raise HTTPException(status_code=400, detail="no questions available for that selection")

    option_orders: dict[str, list[str]] = {}
    for i, qid in enumerate(qids):
        q = assessment_bank.get_question(qid)
        if q and q["type"] in ("single", "multi"):
            option_orders[qid] = assessment_bank.option_order(q, seed + i + 1)

    started = _now()
    expires = started + dt.timedelta(minutes=req.duration_min)
    attempt_id = db.create_assessment_attempt(
        student_id, req.category, req.difficulty, len(qids), req.duration_min * 60,
        qids, option_orders, seed, started.isoformat(), expires.isoformat(),
    )
    return _public_attempt(db.get_assessment_attempt(attempt_id))


@router.get("/attempts")
def list_attempts(student_id: str = Depends(current_student)) -> dict:
    return {"attempts": db.list_assessment_attempts(student_id)}


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: int, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    att = _auto_submit_if_expired(att)
    return _public_attempt(att)


@router.post("/attempts/{attempt_id}/answers")
def save_answers(attempt_id: int, req: SaveAnswersRequest, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    att = _auto_submit_if_expired(att)
    if att["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="this attempt is already finished")
    # merge drafts into stored answers, keeping only ids that belong to this attempt
    valid_ids = set(att["question_ids"])
    merged = dict(att["answers"])
    for qid, item in req.answers.items():
        if qid not in valid_ids:
            continue
        merged[qid] = {"selected": item.selected, "bool": item.tf_value}
    db.save_assessment_answers(attempt_id, merged)
    return {"saved": True, "answered": _answered_count(att["question_ids"], merged)}


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: int, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    if att["status"] != "in_progress":
        # idempotent: already finished -> return the stored result
        return {"attempt_id": attempt_id, "status": att["status"], "already_submitted": True,
                "result": att["result"]}
    # choose status by the server clock, then grade (expired -> timed_out, else submitted)
    status = "timed_out" if _now() > _parse(att["expires_at"]) else "submitted"
    result = _finalize(att, status=status, answers=att["answers"])
    fresh = db.get_assessment_attempt(attempt_id)
    return {"attempt_id": attempt_id, "status": fresh["status"], "already_submitted": result is None,
            "result": fresh["result"]}


@router.get("/attempts/{attempt_id}/result")
def get_result(attempt_id: int, student_id: str = Depends(current_student)) -> dict:
    att = _owned_attempt_or_error(attempt_id, student_id)
    att = _auto_submit_if_expired(att)
    if att["status"] == "in_progress":
        raise HTTPException(status_code=409, detail="attempt not submitted yet")
    # question-by-question review (answer keys + explanations) is allowed ONLY now, post-submission.
    review = []
    plain = _answers_to_plain(att["answers"])
    for qid in att["question_ids"]:
        q = assessment_bank.get_question(qid)
        if not q:
            continue
        rq = assessment_bank.review_question(q)
        rq["your_answer"] = plain.get(qid)
        rq["status"] = att["result"]["per_question"].get(qid, {}).get("status", "unanswered")
        review.append(rq)
    return {
        "attempt_id": attempt_id,
        "category": att["category"],
        "difficulty": att["difficulty"],
        "status": att["status"],
        "started_at": att["started_at"],
        "submitted_at": att["submitted_at"],
        "time_taken_sec": _time_taken_sec(att),
        "duration_sec": att["duration_sec"],
        "result": att["result"],
        "review": review,
    }


# ---- projections / helpers ----

def _public_attempt(att: dict) -> dict:
    """Pre-submission attempt view: questions with randomized options and NO answer keys, saved drafts,
    and server-computed remaining time."""
    questions = []
    for qid in att["question_ids"]:
        q = assessment_bank.get_question(qid)
        if not q:
            continue
        order = att["option_orders"].get(qid)
        questions.append(assessment_bank.public_question(q, order))
    remaining = max(0, int((_parse(att["expires_at"]) - _now()).total_seconds()))
    return {
        "attempt_id": att["id"],
        "category": att["category"],
        "difficulty": att["difficulty"],
        "num_questions": att["num_questions"],
        "duration_sec": att["duration_sec"],
        "status": att["status"],
        "started_at": att["started_at"],
        "expires_at": att["expires_at"],
        "remaining_sec": remaining if att["status"] == "in_progress" else 0,
        "questions": questions,
        "answers": att["answers"],   # the student's OWN drafts only (not answer keys)
    }


def _answered_count(question_ids: list[str], answers: dict) -> int:
    n = 0
    for qid in question_ids:
        a = answers.get(qid)
        if not a:
            continue
        if a.get("bool") is not None or (a.get("selected")):
            n += 1
    return n


def _time_taken_sec(att: dict) -> int | None:
    if not att.get("submitted_at"):
        return None
    return max(0, int((_parse(att["submitted_at"]) - _parse(att["started_at"])).total_seconds()))
