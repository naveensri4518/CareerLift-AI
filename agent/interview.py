"""Interview question generation (DESIGN.md section 11).

Deterministic-first: questions are selected from the curated concept reference so every question's
expected_concepts are REAL ids (never invented by the model). A model may later rephrase the text, but
selection — the part that must be correct — is pure Python and needs no model call.
"""
from __future__ import annotations

import random

from . import fairscore

# A small bank mapping a topic to its question template and the concepts it targets.
# Every concept_id here must exist in agent/data/concepts.json.
QUESTION_BANK = [
    {"topic": "complexity", "concepts": ["C-BIGO-DEF", "C-BIGO-WORSTCASE"],
     "text": "What does Big-O notation describe, and how do worst-case and average-case differ?"},
    {"topic": "search", "concepts": ["C-BINSEARCH"],
     "text": "How does binary search work, and what must be true of the input for it to be correct?"},
    {"topic": "hashing", "concepts": ["C-HASH-AVG"],
     "text": "What is the time complexity of a hash table lookup, on average and in the worst case?"},
    {"topic": "recursion", "concepts": ["C-RECURSION-BASE"],
     "text": "Why does a recursive function need a base case? What happens without one?"},
    {"topic": "sql-joins", "concepts": ["C-SQL-JOIN"],
     "text": "Explain the difference between an INNER JOIN and a LEFT JOIN."},
    {"topic": "sql-index", "concepts": ["C-SQL-INDEX"],
     "text": "What does a database index do, and what is the trade-off of adding one?"},
    {"topic": "python", "concepts": ["C-PY-MUTABLE-DEFAULT"],
     "text": "What is the mutable default argument pitfall in Python, and why does it happen?"},
]

VALID_TOPICS = [q["topic"] for q in QUESTION_BANK]


def generate_question(topic: str | None = None, level: str = "beginner", seed: int | None = None) -> dict:
    """Return {text, expected_concepts, topic, difficulty}. Deterministic given topic (or seed)."""
    pool = [q for q in QUESTION_BANK if (topic is None or q["topic"] == topic)]
    if not pool:
        raise ValueError(f"unknown topic {topic!r}; choose one of {VALID_TOPICS}")
    rng = random.Random(seed)
    q = pool[0] if topic else rng.choice(pool)
    # validate concept ids exist in the reference (fail fast if the bank drifts)
    ids = fairscore.concept_ids()
    unknown = [c for c in q["concepts"] if c not in ids]
    if unknown:
        raise ValueError(f"question targets unknown concept ids: {unknown}")
    return {"text": q["text"], "expected_concepts": list(q["concepts"]),
            "topic": q["topic"], "difficulty": level}
