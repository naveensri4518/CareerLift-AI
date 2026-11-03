"""Request/response Pydantic schemas for the REST API.

User-facing: no internal model ids, framework names or infra details are exposed here (DESIGN.md section 11 /
IDEA.md section 7). Bands and messages only.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Band = Literal["Weak", "Partial", "Solid", "Strong"]


class RegisterRequest(BaseModel):
    # No identity field: the SERVER generates the student id. An optional display_name is cosmetic only
    # and is NOT an identity (not used for auth, not unique). Clients cannot choose their student id.
    display_name: Optional[str] = Field(default=None, max_length=128)


class RegisterResponse(BaseModel):
    student_id: str     # SERVER-generated; the client did not and cannot choose this
    token: str          # shown ONCE; only its hash is stored server-side
    note: str


class StartInterviewRequest(BaseModel):
    # Identity comes from the auth token, not this body. student_id removed on purpose.
    role: str = Field(default="software engineer", max_length=128)
    level: str = Field(default="beginner", max_length=64)
    topic: Optional[str] = Field(default=None, max_length=64)


class QuestionResponse(BaseModel):
    interview_id: int
    question: str
    topic: str
    difficulty: str
    # expected_concepts are internal; echoed as an opaque token list the client returns with the answer
    concept_token: list[str]


class ScoreAnswerRequest(BaseModel):
    interview_id: int
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=8000)
    # IGNORED. Identity comes from the auth token; concepts come from the stored interview. Kept only
    # for backward compatibility with existing clients; the server trusts neither field.
    concept_token: list[str] = Field(default_factory=list)


class ScoreResponse(BaseModel):
    technical_band: Optional[Band] = None
    communication_band: Optional[Band] = None
    abstained_technical: bool = False
    abstained_communication: bool = False
    message: str = ""
    # evidence and gaps are shown to the student; no internal ids
    technical_evidence: list[str] = Field(default_factory=list)
    communication_evidence: list[str] = Field(default_factory=list)
    # True when produced by the LOCAL DEMO / MOCK evaluator (no AI model), so the UI can label it.
    mock: bool = False


class NextExerciseResponse(BaseModel):
    topic: str
    question: str
    reason: str
    concept_token: list[str]


class MisconceptionItem(BaseModel):
    tag: str
    count: int
    last_seen: Optional[str] = None


class HistoryItem(BaseModel):
    interview_id: int
    question: Optional[str]
    technical_band: Optional[str]
    communication_band: Optional[str]
    abstained_technical: bool
    abstained_communication: bool
    created_at: str
