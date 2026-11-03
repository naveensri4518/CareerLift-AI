"""Minimal, clearly-scoped LOCAL authentication for CareerLift AI.

SCOPE AND LIMITATIONS (read this before relying on it):
- This is a minimal bearer-token scheme for LOCAL / single-deployment use, NOT a production identity
  provider. There is no password login, no token expiry/rotation, no refresh, no rate limiting, no
  account recovery, and no transport security of its own (run behind HTTPS in any real deployment).
- What it DOES provide: identity is derived from a server-issued token, never from a client-supplied
  student_id. One student cannot read another student's data without that student's token.
- Credentials: only the SHA-256 hash of a token (salted with a server pepper) is stored. The plaintext
  token is shown exactly once at registration and never persisted, logged, or returned again.
- The server pepper comes from the CAREERLIFT_AUTH_PEPPER environment variable (kept out of source).
  If unset, a process-local random pepper is generated so tokens still cannot be forged, but they will
  not validate across restarts — acceptable for local dev; set the env var for persistence.

This does NOT claim production-ready security. It enforces "no unauthenticated access" locally.
"""
from __future__ import annotations

import hashlib
import os
import secrets

from fastapi import Depends, Header, HTTPException

from agent import db

# Server-side pepper from the environment (never hard-coded). Fallback is a per-process random value.
_PEPPER = os.environ.get("CAREERLIFT_AUTH_PEPPER") or secrets.token_hex(32)


def hash_token(token: str) -> str:
    """SHA-256 of the token combined with the server pepper. One-way; the token cannot be recovered."""
    return hashlib.sha256((_PEPPER + ":" + token).encode("utf-8")).hexdigest()


def new_student_id() -> str:
    """A server-generated, unguessable student identity. Clients NEVER supply this."""
    return "stu_" + secrets.token_urlsafe(16)


def register_new_student(db_path: str | None = None) -> tuple[str, str]:
    """Create a BRAND-NEW student with a server-generated id and issue a token.

    Returns (student_id, plaintext_token). The id is generated here — a client can never register
    'as' an existing student, because we only ever create a fresh, random, previously-unused id. Only
    the token HASH is stored; the plaintext token is returned once and never persisted again.

    LIMITATION (documented): open registration creates an anonymous local account. It is NOT verified
    human identity — anyone who can reach the endpoint can mint a new anonymous account. Keep the API
    local-only until a real account-verification mechanism exists.
    """
    for _ in range(5):  # retry on the astronomically unlikely id collision
        student_id = new_student_id()
        if db.create_new_student(student_id, db_path):
            token = secrets.token_urlsafe(32)
            db.register_token(student_id, hash_token(token), db_path)
            return student_id, token
    raise RuntimeError("could not allocate a unique student id")


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return None


def current_student(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: resolve the bearer token to the owning student_id.

    401 if the header is missing/malformed or the token is unknown. Identity is the token's owner;
    any client-supplied student_id is irrelevant to WHO the caller is.
    """
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    student_id = db.student_for_token_hash(hash_token(token))
    if student_id is None:
        raise HTTPException(status_code=401, detail="invalid token")
    return student_id


# Re-exported so endpoints can write Depends(current_student) cleanly.
require_student = Depends(current_student)
