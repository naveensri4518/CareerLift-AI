"""CareerLift AI — structured outputs and shared types.

The MODEL only ever produces TechnicalClaims and CommObservations (extraction, no scores).
Every band is computed by deterministic Python in fairscore.py. See DESIGN.md sections 3, 6, 7, 10.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Four-band scales (ordinal). Index is the ordinal value used for the fairness gap.
BANDS: list[str] = ["Weak", "Partial", "Solid", "Strong"]
Band = Literal["Weak", "Partial", "Solid", "Strong"]

# Per-claim status the Technical Evaluator assigns each expected concept.
#   supported  = clearly and correctly addressed
#   partial    = touched but incomplete/vague (incomplete explanation)
#   absent     = not addressed (missing knowledge)
#   incorrect  = the student made an explicit WRONG assertion about this concept (needs a grounded quote)
ClaimStatus = Literal["supported", "partial", "absent", "incorrect"]
# Per-dimension observation the Communication Coach assigns.
ObsStatus = Literal["present", "partial", "absent"]


class Claim(BaseModel):
    """One technical claim the answer makes about one concept. Extraction only, no score."""
    concept_id: str = Field(description="An id from the concept reference (expected_concepts).")
    status: ClaimStatus = Field(description=("supported = clearly and correctly addressed; "
                                             "partial = touched but incomplete/vague; absent = not addressed; "
                                             "incorrect = the student explicitly stated something WRONG about this concept"))
    evidence_span: str = Field(default="", description=("A short quote copied VERBATIM from the student's answer. REQUIRED for "
                                                        "supported, partial and incorrect (quote the exact wrong words for incorrect). Empty only for absent."))


class TechnicalClaims(BaseModel):
    """What the Technical Evaluator returns. No band, no number."""
    claims: list[Claim] = Field(default_factory=list)


class CommObservations(BaseModel):
    """What the Communication Coach returns. No band, no number.

    Judge ONLY clarity / structure / relevance / organisation. NEVER judge grammar,
    accent, vocabulary richness, spelling, or length. Plain English is fine.
    """
    clarity: ObsStatus = Field(description="Can the point be understood? Plain simple English counts as clear.")
    structure: ObsStatus = Field(description="Is there a logical order to the explanation?")
    relevance: ObsStatus = Field(description="Does it address the question that was asked?")
    organisation: ObsStatus = Field(description="Are the ideas grouped sensibly rather than rambling?")
    evidence: list[str] = Field(default_factory=list,
                                description="Up to 4 SHORT quotes copied verbatim from the answer that justify the observations above.")
    notes: str = Field(default="", description="One short neutral note. Never mention grammar/vocabulary/accent/length.")


class ScoreResult(BaseModel):
    """Produced by Python (fairscore.py), never by the model. This is the agent's answer object."""
    technical_band: Band | None = None
    communication_band: Band | None = None
    technical_evidence: list[str] = Field(default_factory=list)
    communication_evidence: list[str] = Field(default_factory=list)
    misconception_tags: list[str] = Field(default_factory=list)
    abstained_technical: bool = False
    abstained_communication: bool = False
    message: str = Field(default="", description="User-facing summary; fixed text on abstain, never a guessed band.")
