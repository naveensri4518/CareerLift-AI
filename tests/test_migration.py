"""Task 1: SQLite schema migration. No model, no AWS. Builds an OLD-schema DB by hand, then migrates."""
import os
import sqlite3
import tempfile

import pytest

from agent import db


@pytest.fixture()
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


def _old_schema(path):
    """Create the pre-migration interview table (no question / expected_concepts columns) with a record."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE student (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
        CREATE TABLE interview (
            id INTEGER PRIMARY KEY AUTOINCREMENT, student_id TEXT NOT NULL,
            role TEXT, level TEXT, topic TEXT, created_at TEXT NOT NULL);
        CREATE TABLE answer (
            id INTEGER PRIMARY KEY AUTOINCREMENT, interview_id INTEGER NOT NULL,
            question TEXT, answer_text TEXT, technical_band TEXT, communication_band TEXT,
            created_at TEXT NOT NULL);
        CREATE TABLE misconception (
            student_id TEXT NOT NULL, concept_id TEXT NOT NULL, tag TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0, last_seen TEXT, PRIMARY KEY (student_id, tag));
    """)
    conn.execute("INSERT INTO student(id, created_at) VALUES ('legacy-stu', '2020-01-01T00:00:00')")
    conn.execute("INSERT INTO interview(student_id, role, level, topic, created_at) "
                 "VALUES ('legacy-stu', 'sde', 'beginner', 'hashing', '2020-01-01T00:00:00')")
    conn.execute("INSERT INTO misconception(student_id, concept_id, tag, count, last_seen) "
                 "VALUES ('legacy-stu', 'C-HASH-AVG', 'M-HASH-ALWAYS-O1', 3, '2020-01-02T00:00:00')")
    conn.commit()
    conn.close()


def test_fresh_db_has_all_columns(db_path):
    applied = db.init_db(db_path)
    assert applied == []        # fresh DB needs no migration; SCHEMA already current
    cols = db.schema_version(db_path)
    assert "question" in cols["interview"]
    assert "expected_concepts" in cols["interview"]


def test_migration_adds_missing_columns(db_path):
    _old_schema(db_path)
    # sanity: old DB lacks the new columns
    before = db.schema_version(db_path)
    assert "question" not in before["interview"]
    assert "expected_concepts" not in before["interview"]
    applied = db.init_db(db_path)
    assert "interview.question" in applied
    assert "interview.expected_concepts" in applied
    after = db.schema_version(db_path)
    assert "question" in after["interview"]
    assert "expected_concepts" in after["interview"]


def test_migration_preserves_existing_records(db_path):
    _old_schema(db_path)
    db.init_db(db_path)
    # the legacy student, interview and misconception survived
    with db.connect(db_path) as c:
        students = [dict(r) for r in c.execute("SELECT * FROM student").fetchall()]
        interviews = [dict(r) for r in c.execute("SELECT * FROM interview").fetchall()]
    assert any(s["id"] == "legacy-stu" for s in students)
    assert interviews and interviews[0]["topic"] == "hashing"
    tally = db.misconception_tally("legacy-stu", db_path)
    assert tally and tally[0]["count"] == 3        # preserved, not reset


def test_migration_is_idempotent(db_path):
    _old_schema(db_path)
    first = db.init_db(db_path)
    second = db.init_db(db_path)
    third = db.init_db(db_path)
    assert "interview.question" in first
    assert second == [] and third == []            # nothing left to add on repeat runs


def test_interview_create_and_retrieve_after_migration(db_path):
    _old_schema(db_path)
    db.init_db(db_path)
    iid = db.start_interview("legacy-stu", "sde", "beginner", "hashing",
                             question="What is a hash map?", expected_concepts=["C-HASH-AVG"],
                             db_path=db_path)
    iv = db.get_interview(iid, db_path)
    assert iv["question"] == "What is a hash map?"
    assert iv["expected_concepts"] == ["C-HASH-AVG"]
    assert iv["student_id"] == "legacy-stu"
