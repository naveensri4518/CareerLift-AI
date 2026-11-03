"""Strands conversation/session wiring (DESIGN.md section 8).

STATUS — honest note (P1 review): persistent CONVERSATIONAL context is NOT yet wired into the scoring
lifecycle. Scoring one answer (agent/app.py) is a single-shot, stateless operation: the Technical
Evaluator and Communication Coach each run on one answer with NO session_manager and NO
conversation_manager, by design — there is no multi-turn dialogue to carry between independent answers.

What IS persistent today is CareerLift's APPLICATION state in SQLite (agent/db.py): interview history
and the misconception tally across sessions. That is what powers before/after progress, NOT a Strands
conversation window.

This module provides constructors for a FUTURE multi-turn mode (e.g. a conversational interview where
follow-ups depend on earlier turns). They are verified to construct and FileSessionManager is writable
on the /mnt/c mount (probe, no AWS), but they are not yet attached to app.run(). Do not describe the
current build as having persistent conversational memory.
"""
from __future__ import annotations

import os
from pathlib import Path

from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.session import FileSessionManager

SESSION_DIR = os.environ.get("CAREERLIFT_SESSIONS", str(Path.cwd() / "results" / "sessions"))
WINDOW = 20


def session_manager(student_id: str, storage_dir: str | None = None) -> FileSessionManager:
    d = storage_dir or SESSION_DIR
    Path(d).mkdir(parents=True, exist_ok=True)
    return FileSessionManager(session_id=student_id, storage_dir=d)


def conversation_manager() -> SlidingWindowConversationManager:
    return SlidingWindowConversationManager(window_size=WINDOW)
