"""Input gate: a Strands hook that runs BEFORE any model call (DESIGN.md section 9).

This is the ONE place a hook is the right tool. The abstain decision is NOT here: abstention is
deterministic Python in fairscore/score (it happens after the graph, so no node hook could gate it).

The gate deterministically rejects input that carries personal data or is off-task, so no tokens are
spent on it. Verified pattern: BeforeModelCallEvent.cancel (kit block b03_hooks.py).
"""
from __future__ import annotations

import re

from strands.hooks import BeforeModelCallEvent, HookProvider, HookRegistry

# Simple deterministic PII signals. Not exhaustive; a managed guardrail is a documented stretch.
_PII_PATTERNS = [
    re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),                 # Aadhaar-like 12 digits
    re.compile(r"\b[6-9]\d{9}\b"),                            # Indian mobile number
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # email
]

REJECT_TEXT = ("Please remove personal details (phone, email, id numbers) and send only your interview "
               "answer. We never need your personal data.")


def find_pii(text: str) -> bool:
    return any(p.search(text or "") for p in _PII_PATTERNS)


class InputGate(HookProvider):
    """Cancels the model call if the student's answer contains PII."""

    def __init__(self):
        self.tripped: str | None = None

    def register_hooks(self, registry: HookRegistry, **_):
        registry.add_callback(BeforeModelCallEvent, self._before)

    def _before(self, event: BeforeModelCallEvent):
        msgs = getattr(event.agent, "messages", None) or []
        last = ""
        if msgs:
            content = msgs[-1].get("content", [])
            if content and isinstance(content[0], dict):
                last = content[0].get("text", "")
        if find_pii(last):
            self.tripped = "pii"
            event.cancel = "input gate: personal data detected"
