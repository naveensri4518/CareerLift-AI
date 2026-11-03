"""CareerLift AI — SQLite application persistence (DESIGN.md section 8).

This is CareerLift's source of truth, DISTINCT from Strands conversation sessions (files on disk).
Stdlib sqlite3 only (no extra dependency). Stores students, interviews, scored answers and the
per-student misconception tally that the Learning Planner reads.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB = os.environ.get("CAREERLIFT_DB", str(Path.cwd() / "careerlift.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS student (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS interview (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  TEXT NOT NULL,
    role        TEXT,
    level       TEXT,
    topic       TEXT,
    question    TEXT,
    expected_concepts TEXT,          -- json list; the SERVER's source of truth for scoring
    created_at  TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE TABLE IF NOT EXISTS answer (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id    INTEGER NOT NULL,
    question        TEXT,
    expected_concepts TEXT,           -- json list
    answer_text     TEXT,
    technical_band  TEXT,
    communication_band TEXT,
    abstained_technical INTEGER DEFAULT 0,
    abstained_communication INTEGER DEFAULT 0,
    misconception_tags TEXT,          -- json list
    created_at      TEXT NOT NULL,
    FOREIGN KEY (interview_id) REFERENCES interview(id)
);
CREATE TABLE IF NOT EXISTS misconception (
    student_id  TEXT NOT NULL,
    concept_id  TEXT NOT NULL,
    tag         TEXT NOT NULL,
    count       INTEGER NOT NULL DEFAULT 0,
    last_seen   TEXT,
    PRIMARY KEY (student_id, tag)
);
CREATE TABLE IF NOT EXISTS auth_token (
    token_hash  TEXT PRIMARY KEY,     -- SHA-256(token + server pepper); plaintext token is NEVER stored
    student_id  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);

-- ===== Phase 0: Learning Intelligence (additive; PHASE_0_IMPLEMENTATION_SPEC.md section 5) =====
CREATE TABLE IF NOT EXISTS skill_signal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    concept_id      TEXT NOT NULL,              -- MUST exist in the shared taxonomy
    source_module   TEXT NOT NULL,              -- 'interview' (Phase 0); later: coding|assessment|sysdesign|behavioral
    outcome         TEXT NOT NULL,              -- mastered | partial | struggled | misconception
    strength        TEXT NOT NULL,              -- weak | medium | strong
    confidence      REAL NOT NULL DEFAULT 0,    -- forward-compat only; unused in Phase 0 (written 0)
    evidence_ref    TEXT,                       -- e.g. 'answer:42'
    independent_key TEXT NOT NULL,              -- distinct-item key per concept (e.g. 'iv:answer:42:C-HASH-AVG')
    dedup_key       TEXT NOT NULL UNIQUE,       -- sha256(student|source_module|evidence_ref|concept_id|outcome)
    created_at      TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_signal_student_time ON skill_signal(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_signal_student_concept ON skill_signal(student_id, concept_id);

CREATE TABLE IF NOT EXISTS learner_concept (
    student_id                TEXT NOT NULL,
    concept_id                TEXT NOT NULL,
    label                     TEXT NOT NULL,    -- Not enough evidence|Emerging|Developing|Proficient|Strong
    confidence                REAL NOT NULL DEFAULT 0,   -- forward-compat only; unused in Phase 0
    evidence_count            INTEGER NOT NULL DEFAULT 0,
    independent_success_count INTEGER NOT NULL DEFAULT 0,
    open_misconception        INTEGER NOT NULL DEFAULT 0,
    last_seen                 TEXT,
    updated_at                TEXT NOT NULL,
    PRIMARY KEY (student_id, concept_id),
    FOREIGN KEY (student_id) REFERENCES student(id)
);

CREATE TABLE IF NOT EXISTS activity_event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,                -- 'interview_scored' | 'misconception_opened' | 'misconception_resolved'
    ref_id        TEXT,
    event_key     TEXT NOT NULL UNIQUE,         -- idempotency key; formula depends on kind (spec section 8.1)
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_activity_student_time ON activity_event(student_id, created_at);

-- ===== Phase 1: Advanced Interview Studio (additive) =====
CREATE TABLE IF NOT EXISTS studio_session (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    category      TEXT NOT NULL,                -- technical|hr|behavioral|project|mixed
    difficulty    TEXT NOT NULL,
    experience    TEXT,
    duration_min  INTEGER,
    num_questions INTEGER NOT NULL,
    topics        TEXT,                          -- json list (technical topic filter), may be []
    status        TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | completed
    evaluation    TEXT,                          -- json session summary (set on submit)
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_studio_session_student ON studio_session(student_id, created_at);

CREATE TABLE IF NOT EXISTS studio_question (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        INTEGER NOT NULL,
    ordinal           INTEGER NOT NULL,
    category          TEXT NOT NULL,
    topic             TEXT,
    text              TEXT NOT NULL,
    expected_concepts TEXT,                      -- json list (SERVER-owned; never trusted from client)
    FOREIGN KEY (session_id) REFERENCES studio_session(id)
);
CREATE INDEX IF NOT EXISTS idx_studio_question_session ON studio_question(session_id, ordinal);

CREATE TABLE IF NOT EXISTS studio_answer (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id   INTEGER NOT NULL UNIQUE,       -- one answer row per question (upserted)
    session_id    INTEGER NOT NULL,
    answer_text   TEXT,
    evaluation    TEXT,                          -- json per-answer eval (set on submit)
    updated_at    TEXT NOT NULL,
    FOREIGN KEY (question_id) REFERENCES studio_question(id),
    FOREIGN KEY (session_id) REFERENCES studio_session(id)
);

-- ===== Phase 2: Secure Coding Arena (additive) =====
-- Problems themselves live in agent/data/coding_problems.json (server-owned, incl. hidden tests); only
-- submissions are persisted. problem_id is the curated problem's string id. verdict + result are the
-- deterministic sandbox evaluation; result JSON NEVER contains hidden-test I/O.
CREATE TABLE IF NOT EXISTS coding_submission (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    problem_id    TEXT NOT NULL,                 -- curated problem id (e.g. 'P-BINARY-SEARCH')
    language      TEXT NOT NULL,                 -- python | cpp | java
    source        TEXT NOT NULL,                 -- the student's submitted code
    verdict       TEXT NOT NULL,                 -- ACCEPTED | WRONG ANSWER | COMPILATION ERROR | TIME LIMIT EXCEEDED | RUNTIME ERROR
    tests_passed  INTEGER NOT NULL DEFAULT 0,
    tests_total   INTEGER NOT NULL DEFAULT 0,
    max_time_ms   INTEGER,
    result        TEXT,                          -- json evaluation payload (public results only; no hidden I/O)
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_coding_submission_student ON coding_submission(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_coding_submission_problem ON coding_submission(student_id, problem_id, created_at);

-- ===== Phase 3: Technical Assessment Engine (additive) =====
-- An attempt freezes its question set + per-question option display order at start (server-owned) so a
-- refresh restores identically. Timing is SERVER-authoritative: started_at + duration_sec => expires_at;
-- the client timer is cosmetic. status: in_progress | submitted | timed_out. result JSON (set on submit)
-- holds the deterministic grade/analytics and NEVER contains answer keys for unanswered review before
-- submission (it only exists after submission). Answers are stored as JSON per question id.
CREATE TABLE IF NOT EXISTS assessment_attempt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    category      TEXT NOT NULL,                -- one of 12 categories | 'mixed'
    difficulty    TEXT NOT NULL,                -- beginner|intermediate|advanced|mixed
    num_questions INTEGER NOT NULL,
    duration_sec  INTEGER NOT NULL,             -- configured time budget in seconds
    question_ids  TEXT NOT NULL,                -- json ordered list of question ids (server-owned)
    option_orders TEXT NOT NULL,                -- json {question_id: [option_id,...]} randomized order
    seed          INTEGER NOT NULL,             -- reproducible selection/order seed
    status        TEXT NOT NULL DEFAULT 'in_progress',   -- in_progress | submitted | timed_out
    started_at    TEXT NOT NULL,                -- server timestamp at start (authoritative)
    expires_at    TEXT NOT NULL,                -- started_at + duration_sec (authoritative deadline)
    submitted_at  TEXT,
    answers       TEXT NOT NULL DEFAULT '{}',   -- json {question_id: answer} (draft, upserted)
    result        TEXT,                          -- json grade+analytics (set once on submit)
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_assessment_attempt_student ON assessment_attempt(student_id, created_at);

-- ===== Phase 4: System Design Academy (additive) =====
-- One attempt at one scenario. The submitted design (components/connections/decisions) and the graded
-- result are stored as JSON. status: in_progress | submitted. result is set once on submit (guarded
-- UPDATE => idempotent, no duplicate submission). Scenarios + rubrics live in
-- agent/data/sysdesign_scenarios.json (server-owned); only attempts are persisted.
CREATE TABLE IF NOT EXISTS sysdesign_attempt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    scenario_id   TEXT NOT NULL,                 -- curated scenario id (e.g. 'SD-URL-SHORTENER')
    difficulty    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | submitted
    design        TEXT NOT NULL DEFAULT '{}',    -- json {components, connections, decisions}
    result        TEXT,                          -- json score+dimensions+feedback (set once on submit)
    started_at    TEXT NOT NULL,
    submitted_at  TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_sysdesign_attempt_student ON sysdesign_attempt(student_id, created_at);
"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@contextmanager
def connect(db_path: str | None = None):
    conn = sqlite3.connect(db_path or DEFAULT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Columns that were introduced after the first release. Migration adds any that a pre-existing
# (older-schema) database is missing, WITHOUT dropping or recreating tables, so existing records are
# preserved. (table, column, column definition). ALTER TABLE ADD COLUMN is idempotent here because we
# only add a column after confirming it is absent.
_EXPECTED_COLUMNS: list[tuple[str, str, str]] = [
    ("interview", "question", "TEXT"),
    ("interview", "expected_concepts", "TEXT"),
    # answer table columns below already shipped in the first release, but listing them makes migration
    # robust even if a very old database predates them.
    ("answer", "expected_concepts", "TEXT"),
    ("answer", "misconception_tags", "TEXT"),
    ("answer", "abstained_technical", "INTEGER DEFAULT 0"),
    ("answer", "abstained_communication", "INTEGER DEFAULT 0"),
]


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate(conn) -> list[str]:
    """Add any missing columns to existing tables. Returns the list of applied changes (for tests/logs).

    Never drops or recreates a table. Safe to run repeatedly: a column that already exists is skipped.
    """
    applied: list[str] = []
    for table, column, decl in _EXPECTED_COLUMNS:
        if not _table_exists(conn, table):
            continue  # fresh DBs already got the full table from SCHEMA; nothing to migrate
        if column not in _columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
            applied.append(f"{table}.{column}")
    return applied


def init_db(db_path: str | None = None) -> list[str]:
    """Create tables if absent (fresh DB) then migrate missing columns (older DB). Idempotent.

    Returns the list of migration changes applied this call (empty when already up to date).
    """
    with connect(db_path) as c:
        c.executescript(SCHEMA)       # CREATE TABLE IF NOT EXISTS: full schema on a fresh database
        return _migrate(c)            # ALTER TABLE ADD COLUMN for any pre-existing older-schema database


def schema_version(db_path: str | None = None) -> dict:
    """Introspection helper for tests/ops: which expected columns are present per table."""
    with connect(db_path) as c:
        return {t: sorted(_columns(c, t)) for t in ("student", "interview", "answer", "misconception")
                if _table_exists(c, t)}


def ensure_student(student_id: str, db_path: str | None = None) -> str:
    with connect(db_path) as c:
        c.execute("INSERT OR IGNORE INTO student(id, created_at) VALUES (?,?)", (student_id, _now()))
    return student_id


def student_exists(student_id: str, db_path: str | None = None) -> bool:
    with connect(db_path) as c:
        return c.execute("SELECT 1 FROM student WHERE id=?", (student_id,)).fetchone() is not None


def create_new_student(student_id: str, db_path: str | None = None) -> bool:
    """Insert a brand-new student row. Returns True if created, False if the id already existed.

    Uses INSERT (not INSERT OR IGNORE) inside a uniqueness check so registration can NEVER attach to an
    existing student. The id is expected to be a server-generated random value.
    """
    with connect(db_path) as c:
        if c.execute("SELECT 1 FROM student WHERE id=?", (student_id,)).fetchone() is not None:
            return False
        c.execute("INSERT INTO student(id, created_at) VALUES (?,?)", (student_id, _now()))
        return True


def start_interview(student_id: str, role: str, level: str, topic: str,
                    question: str = "", expected_concepts: list[str] | None = None,
                    db_path: str | None = None) -> int:
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        cur = c.execute(
            "INSERT INTO interview(student_id, role, level, topic, question, expected_concepts, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (student_id, role, level, topic, question, json.dumps(expected_concepts or []), _now()),
        )
        return int(cur.lastrowid)


def get_interview(interview_id: int, db_path: str | None = None) -> dict | None:
    """Return the stored interview row (incl. the server's question + expected_concepts), or None."""
    with connect(db_path) as c:
        r = c.execute(
            "SELECT id, student_id, role, level, topic, question, expected_concepts, created_at "
            "FROM interview WHERE id=?",
            (interview_id,),
        ).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["expected_concepts"] = json.loads(d.get("expected_concepts") or "[]")
        return d


def record_answer(interview_id: int, question: str, expected_concepts: list[str], answer_text: str,
                  score: dict, db_path: str | None = None) -> int:
    with connect(db_path) as c:
        cur = c.execute(
            """INSERT INTO answer(interview_id, question, expected_concepts, answer_text,
                                  technical_band, communication_band, abstained_technical,
                                  abstained_communication, misconception_tags, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (interview_id, question, json.dumps(expected_concepts), answer_text,
             score.get("technical_band"), score.get("communication_band"),
             int(bool(score.get("abstained_technical"))), int(bool(score.get("abstained_communication"))),
             json.dumps(score.get("misconception_tags", [])), _now()),
        )
        return int(cur.lastrowid)


def bump_misconceptions(student_id: str, tags_with_concept: list[tuple[str, str]], db_path: str | None = None) -> None:
    """tags_with_concept: list of (tag, concept_id)."""
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        for tag, concept_id in tags_with_concept:
            c.execute(
                """INSERT INTO misconception(student_id, concept_id, tag, count, last_seen)
                   VALUES (?,?,?,1,?)
                   ON CONFLICT(student_id, tag)
                   DO UPDATE SET count = count + 1, last_seen = excluded.last_seen""",
                (student_id, concept_id, tag, _now()),
            )


def misconception_tally(student_id: str, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT concept_id, tag, count, last_seen FROM misconception WHERE student_id=? ORDER BY count DESC, last_seen DESC",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def register_token(student_id: str, token_hash: str, db_path: str | None = None) -> None:
    """Store only the HASH of a token. The plaintext token is never persisted."""
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        c.execute("INSERT OR REPLACE INTO auth_token(token_hash, student_id, created_at) VALUES (?,?,?)",
                  (token_hash, student_id, _now()))


def student_for_token_hash(token_hash: str, db_path: str | None = None) -> str | None:
    """Resolve a token hash to its owning student_id, or None if unknown."""
    with connect(db_path) as c:
        r = c.execute("SELECT student_id FROM auth_token WHERE token_hash=?", (token_hash,)).fetchone()
        return r["student_id"] if r else None


def interview_history(student_id: str, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT a.id, a.interview_id, a.question, a.technical_band, a.communication_band,
                      a.abstained_technical, a.abstained_communication, a.misconception_tags, a.created_at
               FROM answer a JOIN interview i ON a.interview_id = i.id
               WHERE i.student_id=? ORDER BY a.created_at""",
            (student_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["misconception_tags"] = json.loads(d.get("misconception_tags") or "[]")
            out.append(d)
        return out


# ===== Phase 0 data access (PHASE_0_IMPLEMENTATION_SPEC.md sections 5, 8, 9) =====

def answers_for_student(student_id: str, db_path: str | None = None) -> list[dict]:
    """All scored answers for a student, joined with their interview's topic + expected_concepts.
    Used by signal emission and backfill. Reads persisted data only (no model)."""
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT a.id, a.interview_id, a.question, a.answer_text,
                      a.technical_band, a.communication_band,
                      a.abstained_technical, a.abstained_communication,
                      a.misconception_tags, a.expected_concepts, a.created_at,
                      i.topic AS topic
               FROM answer a JOIN interview i ON a.interview_id = i.id
               WHERE i.student_id=? ORDER BY a.created_at, a.id""",
            (student_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["misconception_tags"] = json.loads(d.get("misconception_tags") or "[]")
            d["expected_concepts"] = json.loads(d.get("expected_concepts") or "[]")
            out.append(d)
        return out


def all_student_ids(db_path: str | None = None) -> list[str]:
    with connect(db_path) as c:
        return [r["id"] for r in c.execute("SELECT id FROM student").fetchall()]


# ---- skill_signal ----

def insert_skill_signal(sig: dict, db_path: str | None = None) -> int | None:
    """INSERT OR IGNORE a signal on the UNIQUE dedup_key. Returns the row id, or None if it already
    existed (idempotent). Never double-counts."""
    with connect(db_path) as c:
        cur = c.execute(
            """INSERT OR IGNORE INTO skill_signal
               (student_id, concept_id, source_module, outcome, strength, confidence,
                evidence_ref, independent_key, dedup_key, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (sig["student_id"], sig["concept_id"], sig["source_module"], sig["outcome"],
             sig["strength"], float(sig.get("confidence", 0.0)), sig.get("evidence_ref"),
             sig["independent_key"], sig["dedup_key"], sig.get("created_at") or _now()),
        )
        return int(cur.lastrowid) if cur.rowcount else None


def signals_for_concept(student_id: str, concept_id: str, db_path: str | None = None) -> list[dict]:
    """All of a student's signals for one concept, in (created_at, id) order for deterministic replay."""
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT id, concept_id, source_module, outcome, strength, evidence_ref,
                      independent_key, created_at
               FROM skill_signal WHERE student_id=? AND concept_id=?
               ORDER BY created_at, id""",
            (student_id, concept_id),
        ).fetchall()
        return [dict(r) for r in rows]


def signal_concepts_for_student(student_id: str, db_path: str | None = None) -> list[str]:
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT DISTINCT concept_id FROM skill_signal WHERE student_id=? ORDER BY concept_id",
            (student_id,),
        ).fetchall()
        return [r["concept_id"] for r in rows]


# ---- learner_concept (derived cache) ----

def upsert_learner_concept(student_id: str, concept_id: str, lc: dict, db_path: str | None = None) -> None:
    with connect(db_path) as c:
        c.execute(
            """INSERT INTO learner_concept
               (student_id, concept_id, label, confidence, evidence_count,
                independent_success_count, open_misconception, last_seen, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(student_id, concept_id) DO UPDATE SET
                 label=excluded.label, confidence=excluded.confidence,
                 evidence_count=excluded.evidence_count,
                 independent_success_count=excluded.independent_success_count,
                 open_misconception=excluded.open_misconception,
                 last_seen=excluded.last_seen, updated_at=excluded.updated_at""",
            (student_id, concept_id, lc["label"], float(lc.get("confidence", 0.0)),
             int(lc["evidence_count"]), int(lc["independent_success_count"]),
             int(bool(lc["open_misconception"])), lc.get("last_seen"), _now()),
        )


def learner_concepts_for_student(student_id: str, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT concept_id, label, evidence_count, independent_success_count,
                      open_misconception, last_seen
               FROM learner_concept WHERE student_id=? ORDER BY concept_id""",
            (student_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["open_misconception"] = bool(d["open_misconception"])
            out.append(d)
        return out


# ---- activity_event ----

def insert_activity_event(student_id: str, kind: str, ref_id: str, event_key: str,
                          created_at: str | None = None, db_path: str | None = None) -> bool:
    """INSERT OR IGNORE on UNIQUE event_key. Returns True if a new row was inserted, False if a no-op
    (duplicate). Makes activity emission idempotent."""
    with connect(db_path) as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO activity_event(student_id, kind, ref_id, event_key, created_at) "
            "VALUES (?,?,?,?,?)",
            (student_id, kind, ref_id, event_key, created_at or _now()),
        )
        return bool(cur.rowcount)


def activity_events_for_student(student_id: str, since: str | None = None, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as c:
        if since:
            rows = c.execute(
                "SELECT kind, ref_id, created_at FROM activity_event WHERE student_id=? AND created_at>=? "
                "ORDER BY created_at",
                (student_id, since),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT kind, ref_id, created_at FROM activity_event WHERE student_id=? ORDER BY created_at",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]


# ===== Phase 1: Interview Studio data access =====

def create_studio_session(student_id: str, category: str, difficulty: str, experience: str | None,
                          duration_min: int | None, num_questions: int, topics: list[str],
                          questions: list[dict], db_path: str | None = None) -> int:
    """Create a session and its question rows (server-owned questions + expected_concepts).
    `questions`: list of {ordinal, category, topic, text, expected_concepts}."""
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        cur = c.execute(
            """INSERT INTO studio_session(student_id, category, difficulty, experience, duration_min,
                                          num_questions, topics, status, created_at)
               VALUES (?,?,?,?,?,?,?, 'in_progress', ?)""",
            (student_id, category, difficulty, experience, duration_min, num_questions,
             json.dumps(topics or []), _now()),
        )
        sid = int(cur.lastrowid)
        for q in questions:
            c.execute(
                """INSERT INTO studio_question(session_id, ordinal, category, topic, text, expected_concepts)
                   VALUES (?,?,?,?,?,?)""",
                (sid, q["ordinal"], q["category"], q.get("topic"), q["text"],
                 json.dumps(q.get("expected_concepts") or [])),
            )
        return sid


def get_studio_session(session_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as c:
        r = c.execute("SELECT * FROM studio_session WHERE id=?", (session_id,)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["evaluation"] = json.loads(d["evaluation"]) if d.get("evaluation") else None
        return d


def studio_questions(session_id: int, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT * FROM studio_question WHERE session_id=? ORDER BY ordinal", (session_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["expected_concepts"] = json.loads(d.get("expected_concepts") or "[]")
            out.append(d)
        return out


def get_studio_question(question_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as c:
        r = c.execute("SELECT * FROM studio_question WHERE id=?", (question_id,)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["expected_concepts"] = json.loads(d.get("expected_concepts") or "[]")
        return d


def save_studio_answer(session_id: int, question_id: int, answer_text: str, db_path: str | None = None) -> None:
    """Upsert the draft answer for a question (resume support). Does not evaluate."""
    with connect(db_path) as c:
        c.execute(
            """INSERT INTO studio_answer(question_id, session_id, answer_text, updated_at)
               VALUES (?,?,?,?)
               ON CONFLICT(question_id) DO UPDATE SET answer_text=excluded.answer_text,
                                                      updated_at=excluded.updated_at""",
            (question_id, session_id, answer_text, _now()),
        )


def studio_answers(session_id: int, db_path: str | None = None) -> dict:
    """Return {question_id: {answer_text, evaluation}} for a session."""
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT question_id, answer_text, evaluation FROM studio_answer WHERE session_id=?",
            (session_id,),
        ).fetchall()
        out = {}
        for r in rows:
            d = dict(r)
            d["evaluation"] = json.loads(d["evaluation"]) if d.get("evaluation") else None
            out[d["question_id"]] = d
        return out


def set_studio_answer_evaluation(question_id: int, evaluation: dict, db_path: str | None = None) -> None:
    with connect(db_path) as c:
        c.execute("UPDATE studio_answer SET evaluation=?, updated_at=? WHERE question_id=?",
                  (json.dumps(evaluation), _now(), question_id))


def complete_studio_session(session_id: int, evaluation: dict, db_path: str | None = None) -> None:
    with connect(db_path) as c:
        c.execute("UPDATE studio_session SET status='completed', evaluation=?, completed_at=? WHERE id=?",
                  (json.dumps(evaluation), _now(), session_id))


def list_studio_sessions(student_id: str, db_path: str | None = None) -> list[dict]:
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT id, category, difficulty, num_questions, status, created_at, completed_at
               FROM studio_session WHERE student_id=? ORDER BY created_at DESC""",
            (student_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ===== Phase 2: Coding Arena data access =====

def create_coding_submission(student_id: str, problem_id: str, language: str, source: str,
                             verdict: str, tests_passed: int, tests_total: int,
                             max_time_ms: int | None, result: dict,
                             db_path: str | None = None) -> int:
    """Persist a graded coding submission. `result` is the client-safe evaluation payload (NO hidden
    test I/O). Returns the new submission id."""
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        cur = c.execute(
            """INSERT INTO coding_submission(student_id, problem_id, language, source, verdict,
                                             tests_passed, tests_total, max_time_ms, result, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (student_id, problem_id, language, source, verdict, int(tests_passed), int(tests_total),
             (int(max_time_ms) if max_time_ms is not None else None), json.dumps(result), _now()),
        )
        return int(cur.lastrowid)


def get_coding_submission(submission_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as c:
        r = c.execute("SELECT * FROM coding_submission WHERE id=?", (submission_id,)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["result"] = json.loads(d["result"]) if d.get("result") else None
        return d


def list_coding_submissions(student_id: str, problem_id: str | None = None,
                            db_path: str | None = None) -> list[dict]:
    """A student's submissions, newest first. Lightweight rows (no source/result blobs)."""
    with connect(db_path) as c:
        if problem_id:
            rows = c.execute(
                """SELECT id, problem_id, language, verdict, tests_passed, tests_total, max_time_ms, created_at
                   FROM coding_submission WHERE student_id=? AND problem_id=? ORDER BY created_at DESC, id DESC""",
                (student_id, problem_id),
            ).fetchall()
        else:
            rows = c.execute(
                """SELECT id, problem_id, language, verdict, tests_passed, tests_total, max_time_ms, created_at
                   FROM coding_submission WHERE student_id=? ORDER BY created_at DESC, id DESC""",
                (student_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def solved_coding_problem_ids(student_id: str, db_path: str | None = None) -> list[str]:
    """Distinct problem ids the student has ever gotten ACCEPTED. Used for list badges + stats."""
    with connect(db_path) as c:
        rows = c.execute(
            "SELECT DISTINCT problem_id FROM coding_submission WHERE student_id=? AND verdict='ACCEPTED' "
            "ORDER BY problem_id",
            (student_id,),
        ).fetchall()
        return [r["problem_id"] for r in rows]


# ===== Phase 3: Technical Assessment data access =====

def create_assessment_attempt(student_id: str, category: str, difficulty: str, num_questions: int,
                              duration_sec: int, question_ids: list[str], option_orders: dict,
                              seed: int, started_at: str, expires_at: str,
                              db_path: str | None = None) -> int:
    """Create an in_progress attempt with a frozen, server-owned question set + option order and
    server-authoritative start/expiry timestamps. Returns the new attempt id."""
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        cur = c.execute(
            """INSERT INTO assessment_attempt(student_id, category, difficulty, num_questions,
                   duration_sec, question_ids, option_orders, seed, status, started_at, expires_at,
                   answers, created_at)
               VALUES (?,?,?,?,?,?,?,?, 'in_progress', ?, ?, '{}', ?)""",
            (student_id, category, difficulty, int(num_questions), int(duration_sec),
             json.dumps(question_ids), json.dumps(option_orders), int(seed),
             started_at, expires_at, _now()),
        )
        return int(cur.lastrowid)


def get_assessment_attempt(attempt_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as c:
        r = c.execute("SELECT * FROM assessment_attempt WHERE id=?", (attempt_id,)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["question_ids"] = json.loads(d.get("question_ids") or "[]")
        d["option_orders"] = json.loads(d.get("option_orders") or "{}")
        d["answers"] = json.loads(d.get("answers") or "{}")
        d["result"] = json.loads(d["result"]) if d.get("result") else None
        return d


def save_assessment_answers(attempt_id: int, answers: dict, db_path: str | None = None) -> None:
    """Replace the draft answers blob for an in_progress attempt. Caller enforces state/ownership."""
    with connect(db_path) as c:
        c.execute("UPDATE assessment_attempt SET answers=? WHERE id=? AND status='in_progress'",
                  (json.dumps(answers), attempt_id))


def submit_assessment_attempt(attempt_id: int, status: str, answers: dict, result: dict,
                              submitted_at: str, db_path: str | None = None) -> bool:
    """Atomically finalize an attempt: only transitions a row that is STILL 'in_progress' (guards against
    duplicate/racing submits). Returns True if this call performed the submission, False if it was already
    finalized. `status` is 'submitted' (manual) or 'timed_out' (deadline passed)."""
    with connect(db_path) as c:
        cur = c.execute(
            """UPDATE assessment_attempt
               SET status=?, answers=?, result=?, submitted_at=?
               WHERE id=? AND status='in_progress'""",
            (status, json.dumps(answers), json.dumps(result), submitted_at, attempt_id),
        )
        return bool(cur.rowcount)


def list_assessment_attempts(student_id: str, db_path: str | None = None) -> list[dict]:
    """A student's attempts, newest first. Lightweight rows (no question_ids/answers/result blobs,
    but includes the summary scores pulled from result when present)."""
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT id, category, difficulty, num_questions, duration_sec, status,
                      started_at, submitted_at, result, created_at
               FROM assessment_attempt WHERE student_id=? ORDER BY created_at DESC, id DESC""",
            (student_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            res = json.loads(d["result"]) if d.get("result") else None
            d.pop("result", None)
            if res:
                d["total_score"] = res.get("total_score")
                d["max_score"] = res.get("max_score")
                d["percentage"] = res.get("percentage")
                d["grade"] = res.get("grade")
            out.append(d)
        return out


# ===== Phase 4: System Design Academy data access =====

def create_sysdesign_attempt(student_id: str, scenario_id: str, difficulty: str, started_at: str,
                             db_path: str | None = None) -> int:
    """Create an in_progress attempt for a scenario. Returns the new attempt id."""
    ensure_student(student_id, db_path)
    with connect(db_path) as c:
        cur = c.execute(
            """INSERT INTO sysdesign_attempt(student_id, scenario_id, difficulty, status, design,
                   started_at, created_at)
               VALUES (?,?,?, 'in_progress', '{}', ?, ?)""",
            (student_id, scenario_id, difficulty, started_at, _now()),
        )
        return int(cur.lastrowid)


def get_sysdesign_attempt(attempt_id: int, db_path: str | None = None) -> dict | None:
    with connect(db_path) as c:
        r = c.execute("SELECT * FROM sysdesign_attempt WHERE id=?", (attempt_id,)).fetchone()
        if r is None:
            return None
        d = dict(r)
        d["design"] = json.loads(d.get("design") or "{}")
        d["result"] = json.loads(d["result"]) if d.get("result") else None
        return d


def save_sysdesign_design(attempt_id: int, design: dict, db_path: str | None = None) -> None:
    """Replace the draft design for an in_progress attempt. Caller enforces state/ownership."""
    with connect(db_path) as c:
        c.execute("UPDATE sysdesign_attempt SET design=? WHERE id=? AND status='in_progress'",
                  (json.dumps(design), attempt_id))


def submit_sysdesign_attempt(attempt_id: int, design: dict, result: dict, submitted_at: str,
                             db_path: str | None = None) -> bool:
    """Atomically finalize an attempt: only transitions a row STILL 'in_progress' (guards against
    duplicate/racing submits). Returns True if this call performed the submission, False otherwise."""
    with connect(db_path) as c:
        cur = c.execute(
            """UPDATE sysdesign_attempt SET status='submitted', design=?, result=?, submitted_at=?
               WHERE id=? AND status='in_progress'""",
            (json.dumps(design), json.dumps(result), submitted_at, attempt_id),
        )
        return bool(cur.rowcount)


def list_sysdesign_attempts(student_id: str, db_path: str | None = None) -> list[dict]:
    """A student's attempts, newest first, with summary score pulled from result when present."""
    with connect(db_path) as c:
        rows = c.execute(
            """SELECT id, scenario_id, difficulty, status, started_at, submitted_at, result, created_at
               FROM sysdesign_attempt WHERE student_id=? ORDER BY created_at DESC, id DESC""",
            (student_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            res = json.loads(d["result"]) if d.get("result") else None
            d.pop("result", None)
            if res:
                d["percentage"] = res.get("percentage")
                d["grade"] = res.get("grade")
            out.append(d)
        return out
