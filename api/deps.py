"""Shared API dependencies (Phase 0). One place for student ownership authorization, matching the
existing pattern in api/main.py (_authorize_path_student)."""
from __future__ import annotations

from fastapi import Depends, HTTPException

from .auth import current_student


def require_owner(student_id: str, authed: str = Depends(current_student)) -> str:
    """A caller may only access their OWN student resources. 401 handled by current_student; 403 on mismatch.
    Returns the authenticated student id for convenience."""
    if student_id != authed:
        raise HTTPException(status_code=403, detail="you may only access your own data")
    return authed
