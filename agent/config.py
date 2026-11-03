"""Model-mode configuration for CareerLift AI.

CAREERLIFT_MODEL_MODE selects how the MODEL role (claim/observation extraction) is fulfilled:
  - "bedrock" (default): the real Amazon Bedrock path (unchanged). Needs AWS credentials.
  - "mock": a deterministic LOCAL extractor (agent/mockmodel.py). No AWS, no network, no cost.

The mode is NEVER switched silently. If bedrock is selected and credentials are missing, the agent raises
ModelUnavailableError, which the API turns into a clear, actionable 503 (not an opaque 500).
"""
from __future__ import annotations

import os

VALID_MODES = ("bedrock", "mock")


def model_mode() -> str:
    mode = os.environ.get("CAREERLIFT_MODEL_MODE", "bedrock").strip().lower()
    if mode not in VALID_MODES:
        raise ModelUnavailableError(
            f"CAREERLIFT_MODEL_MODE={mode!r} is not valid. Set it to one of {VALID_MODES}."
        )
    return mode


def is_mock() -> bool:
    return model_mode() == "mock"


class ModelUnavailableError(RuntimeError):
    """Raised when the configured model mode cannot run (e.g. bedrock mode without credentials).

    Carries a user-facing, actionable message. Never contains secrets or stack internals.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = message
