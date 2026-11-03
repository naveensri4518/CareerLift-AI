"""Back-compat shim. CareerLift's structured outputs live in agent/models.py.

Kept so `from .plan import ...` never surprises a reader; the real models are in models.py.
"""
from .models import (  # noqa: F401
    BANDS,
    Band,
    Claim,
    CommObservations,
    ScoreResult,
    TechnicalClaims,
)
