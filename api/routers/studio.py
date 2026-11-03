"""Advanced Interview Studio router (Phase 1). Owner-authorized. Mock-mode evaluation via the FairScore
provider abstraction — NO Bedrock/Translate here (mock mode). Emits Phase 0 signals for technical answers.

Endpoints:
  POST /studio/sessions                     create + return the question set
  GET  /studio/sessions                     list my sessions
  GET  /studio/sessions/{id}                full session (questions + saved answers + evaluation)
  POST /studio/sessions/{id}/answer         save/resume a draft answer (no scoring)
  POST /studio/sessions/{id}/submit         evaluate all answers, persist, return detailed evaluation
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional

from agent import activity, db, interview_studio
from agent.skills import signals as skill_signals

from ..auth import current_student

router = APIRouter(prefix="/studio", tags=["studio"])
_log = logging.getLogger("careerlift")

Category = Literal["technical", "hr", "behavioral", "project", "mixed"]
Difficulty = Literal["beginner", "intermediate", "advanced"]


class CreateSessionRequest(BaseModel):
    category: Category
    difficulty: Difficulty = "beginner"
    experience: Optional[str] = Field(default=None, max_length=64)
    duration_min: Optional[int] = Field(default=None, ge=1, le=240)
    num_questions: int = Field(default=5, ge=1, le=20)
    topics: list[str] = Field(default_factory=list)


class SaveAnswerRequest(BaseModel):
    question_id: int
    answer: str = Field(default="", max_length=8000)


def _owned_session_or_404(session_id: int, student_id: str) -> dict:
    sess = db.get_studio_session(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="interview session not found")
    if sess["student_id"] != student_id:
        raise HTTPException(status_code=403, detail="this interview session does not belong to you")
    return sess


def _public_question(q: dict) -> dict:
    # expected_concepts are SERVER-owned; never exposed to the client.
    return {"question_id": q["id"], "ordinal": q["ordinal"], "category": q["category"],
            "topic": q.get("topic"), "text": q["text"]}


@router.post("/sessions")
def create_session(req: CreateSessionRequest, student_id: str = Depends(current_student)) -> dict:
    try:
        qset = interview_studio.build_question_set(req.category, req.num_questions, req.topics or None,
                                                   seed=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    session_id = db.create_studio_session(
        student_id, req.category, req.difficulty, req.experience, req.duration_min,
        len(qset), req.topics, qset,
    )
    questions = db.studio_questions(session_id)
    return {
        "session_id": session_id,
        "category": req.category,
        "difficulty": req.difficulty,
        "num_questions": len(qset),
        "status": "in_progress",
        "questions": [_public_question(q) for q in questions],
    }


@router.get("/sessions")
def list_sessions(student_id: str = Depends(current_student)) -> dict:
    return {"sessions": db.list_studio_sessions(student_id)}


@router.get("/sessions/{session_id}")
def get_session(session_id: int, student_id: str = Depends(current_student)) -> dict:
    sess = _owned_session_or_404(session_id, student_id)
    questions = db.studio_questions(session_id)
    answers = db.studio_answers(session_id)
    return {
        "session_id": session_id,
        "category": sess["category"],
        "difficulty": sess["difficulty"],
        "status": sess["status"],
        "num_questions": sess["num_questions"],
        "evaluation": sess["evaluation"],
        "questions": [
            {**_public_question(q),
             "answer": (answers.get(q["id"]) or {}).get("answer_text", ""),
             "evaluation": (answers.get(q["id"]) or {}).get("evaluation")}
            for q in questions
        ],
    }


@router.post("/sessions/{session_id}/answer")
def save_answer(session_id: int, req: SaveAnswerRequest, student_id: str = Depends(current_student)) -> dict:
    sess = _owned_session_or_404(session_id, student_id)
    if sess["status"] != "in_progress":
        raise HTTPException(status_code=409, detail="this session is already submitted")
    q = db.get_studio_question(req.question_id)
    if q is None or q["session_id"] != session_id:
        raise HTTPException(status_code=404, detail="question not part of this session")
    db.save_studio_answer(session_id, req.question_id, req.answer)
    return {"saved": True, "question_id": req.question_id}


@router.post("/sessions/{session_id}/submit")
def submit_session(session_id: int, student_id: str = Depends(current_student)) -> dict:
    sess = _owned_session_or_404(session_id, student_id)
    if sess["status"] == "completed":
        # idempotent: return the stored evaluation rather than re-grading
        return {"session_id": session_id, "status": "completed", "evaluation": sess["evaluation"],
                "already_submitted": True}

    questions = db.studio_questions(session_id)
    saved = db.studio_answers(session_id)
    provider = interview_studio.get_provider()

    graded = []
    for q in questions:
        answer_text = (saved.get(q["id"]) or {}).get("answer_text", "") or ""
        ev = provider.evaluate_answer(answer_text, q["expected_concepts"])
        # persist per-answer evaluation (also persists the answer row if none existed)
        db.save_studio_answer(session_id, q["id"], answer_text)
        db.set_studio_answer_evaluation(q["id"], ev)
        graded.append({"ordinal": q["ordinal"], "category": q["category"], "topic": q.get("topic"),
                       "expected_concepts": q["expected_concepts"], "answer_text": answer_text, "eval": ev})

        # Phase 0 integration: feed technical answers into the shared knowledge model (best-effort).
        if q["expected_concepts"] and answer_text.strip():
            try:
                answer_row = {
                    "id": f"studio:{q['id']}",             # distinct evidence ref per studio question
                    "misconception_tags": ev.get("misconception_tags", []),
                    "expected_concepts": q["expected_concepts"],
                    "topic": q.get("topic"),
                    "created_at": None,
                    "concept_status": _concept_status_from_eval(ev, q["expected_concepts"]),
                }
                skill_signals.emit_from_answer(student_id, answer_row)
            except Exception:  # noqa: BLE001 — never break submit on signal emission
                _log.debug("studio signal emission failed for question %s", q["id"])

    summary = interview_studio.summarize_session(sess["category"], graded)
    # attach a curated better-sample-answer for the first weak technical topic, if any
    weak_topic = next((g["topic"] for g in graded
                       if g["eval"].get("technical_band") == "Weak" and g["expected_concepts"]), None)
    if weak_topic:
        summary["sample_better_answer"] = {"topic": weak_topic,
                                           "text": interview_studio.sample_answer_for(weak_topic)}

    db.complete_studio_session(session_id, summary)
    try:
        activity.record(student_id, "interview_scored", f"studio:{session_id}")
    except Exception:  # noqa: BLE001
        _log.debug("studio activity emission failed for session %s", session_id)

    return {"session_id": session_id, "status": "completed", "evaluation": summary,
            "mock": bool(graded and graded[0]["eval"].get("mock")),
            "mock_label": graded[0]["eval"].get("mock_label") if graded else None}


def _concept_status_from_eval(ev: dict, expected: list[str]) -> dict:
    """Derive per-concept status for Phase 0 signals from the FairScore result, using ONLY what the
    pipeline produced (no fabrication). A concept flagged as a misconception is handled by signals.py's
    precedence; others inherit the technical band as a coarse per-concept status when assessed."""
    if ev.get("abstained_technical") or not ev.get("technical_band"):
        return {}
    band = ev["technical_band"]
    status = {"Strong": "supported", "Solid": "supported", "Partial": "partial"}.get(band)
    if not status:
        return {}
    return {cid: status for cid in expected}
