"""Shared pytest fixtures. All tests run with NO AWS and NO model calls."""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# make the project root importable (agent/, api/)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def temp_db(monkeypatch):
    """A throwaway SQLite database per test."""
    from agent import db
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("CAREERLIFT_DB", path)
    monkeypatch.setattr(db, "DEFAULT_DB", path)
    db.init_db(path)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass
