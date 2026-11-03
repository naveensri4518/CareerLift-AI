"""CareerLift AI — FastAPI backend (local-first).

Run locally (no AWS resources; scoring calls Amazon Bedrock only when /score is hit with real creds):
    uvicorn api.main:app --reload

Endpoints:
    GET  /health
    POST /interviews            start an interview, returns the first question
    GET  /interviews/{id}/question?topic=...   (not used by default; question comes with start)
    POST /score                 score one answer (invokes the agent -> Bedrock; guarded)
    GET  /students/{id}/next     planner's next exercise (deterministic, no model)
    GET  /students/{id}/history  interview history (no model)
    GET  /students/{id}/misconceptions  misconception tally (no model)

Scoring is the ONLY endpoint that would call Bedrock. It is implemented but not exercised by the test
suite (tests monkeypatch the scorer). Nothing here creates AWS resources.
"""
from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agent import activity, db, interview, planner
from agent.app import run as score_answer   # the FairScore agent entrypoint (Bedrock at call time only)
from agent.config import ModelUnavailableError
from agent.gates import find_pii
from agent.skills import signals as skill_signals

from .auth import current_student, register_new_student
from .routers import dashboard as dashboard_router
from .routers import assessment as assessment_router
from .routers import coding as coding_router
from .routers import learning as learning_router
from .routers import studio as studio_router
from .routers import sysdesign as sysdesign_router
from .schemas import (
    HistoryItem,
    MisconceptionItem,
    NextExerciseResponse,
    QuestionResponse,
    RegisterRequest,
    RegisterResponse,
    ScoreAnswerRequest,
    ScoreResponse,
    StartInterviewRequest,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="CareerLift AI", version="0.1.0", lifespan=lifespan)

# Allow the LOCAL Vite dev frontend to call the API from the browser. Restricted to localhost dev
# origins only — this does not change auth, scoring, or the schema. Override via CAREERLIFT_CORS_ORIGINS
# (comma-separated) if you run the frontend on a different local port.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
_cors_origins = [o.strip() for o in os.environ.get("CAREERLIFT_CORS_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# Phase 0 Learning Intelligence + Dashboard routers (additive; spec §4). They do NOT register /next.
app.include_router(learning_router.router)
app.include_router(dashboard_router.router)
app.include_router(studio_router.router)      # Phase 1 — Advanced Interview Studio
app.include_router(coding_router.router)      # Phase 2 — Secure Coding Arena
app.include_router(assessment_router.router)  # Phase 3 — Technical Assessment Engine
app.include_router(sysdesign_router.router)   # Phase 4 — System Design Academy


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "careerlift"}


@app.post("/register", response_model=RegisterResponse)
def register(req: RegisterRequest) -> RegisterResponse:
    """Create a NEW anonymous student with a SERVER-generated id and issue a bearer token.

    The client cannot choose or supply a student id, so registration can never impersonate an existing
    student. The token is shown ONCE; only its hash is stored. Open registration is NOT verified human
    identity — keep the API local-only until account verification exists.
    """
    student_id, token = register_new_student()
    return RegisterResponse(
        student_id=student_id, token=token,
        note=("Store this token now; it is shown only once and cannot be retrieved later. Your student id "
              "was assigned by the server. Open registration is anonymous and not identity-verified; "
              "run locally only."))


@app.post("/interviews", response_model=QuestionResponse)
def start_interview(req: StartInterviewRequest, student_id: str = Depends(current_student)) -> QuestionResponse:
    # Identity is the authenticated token owner, NOT any client-supplied id.
    try:
        q = interview.generate_question(topic=req.topic, level=req.level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Persist the question AND its expected concepts server-side: these become the source of truth for
    # scoring. The client never dictates which concepts an answer is graded against.
    interview_id = db.start_interview(student_id, req.role, req.level, q["topic"],
                                      question=q["text"], expected_concepts=q["expected_concepts"])
    return QuestionResponse(interview_id=interview_id, question=q["text"], topic=q["topic"],
                            difficulty=q["difficulty"], concept_token=q["expected_concepts"])


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreAnswerRequest, student_id: str = Depends(current_student)) -> ScoreResponse:
    # --- authorise and validate against the STORED interview before doing anything else ---
    iv = db.get_interview(req.interview_id)
    if iv is None:
        raise HTTPException(status_code=404, detail="interview not found")
    if iv["student_id"] != student_id:
        # Ownership is checked against the AUTHENTICATED identity, not a payload field.
        raise HTTPException(status_code=403, detail="this interview does not belong to you")
    if req.question.strip() != (iv.get("question") or "").strip():
        raise HTTPException(status_code=409, detail="submitted question does not match the interview")

    # Expected concepts come from the SERVER's stored interview, never from the client payload.
    expected_concepts = iv["expected_concepts"]

    # Deterministic input validation BEFORE any model work (defence in depth; the agent also gates).
    if find_pii(req.answer):
        return ScoreResponse(abstained_technical=True, abstained_communication=True,
                             message=("Please remove personal details (phone, email, id numbers) and send only "
                                      "your interview answer."))
    try:
        out = score_answer({"text": req.answer, "expected_concepts": expected_concepts})
    except ModelUnavailableError as e:
        # Clear, actionable 503 instead of an opaque 500 (e.g. Bedrock mode without credentials).
        raise HTTPException(status_code=503, detail=e.user_message)
    plan = out["plan"]
    mode = out.get("meta", {}).get("model_mode")
    # persist
    answer_id = db.record_answer(req.interview_id, iv.get("question", ""), expected_concepts, req.answer, plan)
    tags_with_concept = _tags_with_concepts(expected_concepts, plan.get("misconception_tags", []))
    if tags_with_concept:
        db.bump_misconceptions(student_id, tags_with_concept)

    # Phase 0: emit Learning-Intelligence signals + activity ONLY AFTER successful persistence, wrapped so
    # a failure can NEVER alter this response (spec §8.1). Deterministic/local — no model or AWS call.
    _emit_learning_signals(student_id, answer_id, iv.get("topic"), expected_concepts, plan)
    return ScoreResponse(
        technical_band=plan.get("technical_band"),
        communication_band=plan.get("communication_band"),
        abstained_technical=bool(plan.get("abstained_technical")),
        abstained_communication=bool(plan.get("abstained_communication")),
        message=plan.get("message", ""),
        technical_evidence=plan.get("technical_evidence", []),
        communication_evidence=plan.get("communication_evidence", []),
        mock=(mode == "mock"),
    )


def _authorize_path_student(path_student_id: str, authed_student_id: str) -> None:
    """A caller may only access their OWN student resources. 403 on any mismatch."""
    if path_student_id != authed_student_id:
        raise HTTPException(status_code=403, detail="you may only access your own data")


@app.get("/students/{student_id}/next", response_model=NextExerciseResponse)
def next_exercise(student_id: str, authed: str = Depends(current_student)) -> NextExerciseResponse:
    _authorize_path_student(student_id, authed)
    nx = planner.next_exercise(authed)
    q = nx["question"]
    return NextExerciseResponse(topic=nx["topic"], question=q["text"], reason=nx["reason"],
                                concept_token=q["expected_concepts"])


@app.get("/students/{student_id}/history", response_model=list[HistoryItem])
def history(student_id: str, authed: str = Depends(current_student)) -> list[HistoryItem]:
    _authorize_path_student(student_id, authed)
    rows = db.interview_history(authed)
    return [HistoryItem(interview_id=r["interview_id"], question=r.get("question"),
                        technical_band=r.get("technical_band"), communication_band=r.get("communication_band"),
                        abstained_technical=bool(r.get("abstained_technical")),
                        abstained_communication=bool(r.get("abstained_communication")),
                        created_at=r["created_at"]) for r in rows]


@app.get("/students/{student_id}/misconceptions", response_model=list[MisconceptionItem])
def misconceptions(student_id: str, authed: str = Depends(current_student)) -> list[MisconceptionItem]:
    _authorize_path_student(student_id, authed)
    rows = db.misconception_tally(authed)
    return [MisconceptionItem(tag=r["tag"], count=r["count"], last_seen=r.get("last_seen")) for r in rows]


def _tags_with_concepts(concept_ids: list[str], tags: list[str]) -> list[tuple[str, str]]:
    """Pair each misconception tag with the concept it is 'about' (from the reference)."""
    from agent import fairscore
    about = {m["id"]: m.get("about") for m in fairscore.concepts().get("misconceptions", [])}
    out = []
    for tag in tags:
        concept = about.get(tag) or (concept_ids[0] if concept_ids else "")
        out.append((tag, concept))
    return out


def _emit_learning_signals(student_id: str, answer_id: int, topic, expected_concepts: list[str], plan: dict) -> None:
    """Phase 0 emission (spec §8.1): SkillSignals + interview_scored activity, AFTER persistence.
    Wrapped so ANY failure is swallowed and can never alter the /score response. No model/AWS."""
    try:
        answer_row = {
            "id": answer_id,
            "misconception_tags": plan.get("misconception_tags", []),
            "expected_concepts": expected_concepts,
            "topic": topic,
            "created_at": None,  # db uses its own timestamp; signals inherit it on re-read if needed
        }
        skill_signals.emit_from_answer(student_id, answer_row)
        activity.record_interview_scored(student_id, answer_id)
    except Exception:  # noqa: BLE001 — best-effort projection; never break a successful /score
        logging.getLogger("careerlift").debug("learning-signal emission failed for answer %s", answer_id)
