"""Phase 3 — Technical Assessment question bank (server-owned, read-only).

Loads agent/data/assessment_questions.json. Correct answers (correct_options / correct_bool) and
explanations live here and are NEVER returned by a pre-submission public view. Deterministic selection +
option randomization are seeded per-attempt so a refresh restores the identical question set and order.

No model / AWS. Pure data + stdlib random (seeded).
"""
from __future__ import annotations

import functools
import json
import pathlib
import random

_QDATA = pathlib.Path(__file__).with_name("data") / "assessment_questions.json"
_CDATA = pathlib.Path(__file__).with_name("data") / "assessment_concepts.json"

CATEGORIES = (
    "dsa", "java", "python", "c", "cpp", "dbms", "sql", "os",
    "networks", "oop", "architecture", "software_engineering",
)
DIFFICULTIES = ("beginner", "intermediate", "advanced")
QUESTION_COUNTS = (10, 20, 30, 50)
DURATIONS_MIN = (10, 20, 30, 45, 60)
TYPES = ("single", "multi", "tf")


@functools.lru_cache(maxsize=1)
def _bank() -> dict:
    data = json.loads(_QDATA.read_text(encoding="utf-8"))
    by_id = {}
    for q in data["questions"]:
        if q["category"] not in CATEGORIES:
            raise ValueError(f"question {q['id']} has unknown category {q['category']!r}")
        if q["difficulty"] not in DIFFICULTIES:
            raise ValueError(f"question {q['id']} has unknown difficulty {q['difficulty']!r}")
        if q["type"] not in TYPES:
            raise ValueError(f"question {q['id']} has unknown type {q['type']!r}")
        by_id[q["id"]] = q
    return {"questions": data["questions"], "by_id": by_id}


@functools.lru_cache(maxsize=1)
def assessment_concept_ids() -> frozenset[str]:
    data = json.loads(_CDATA.read_text(encoding="utf-8"))
    return frozenset(c["id"] for c in data["concepts"])


def all_questions() -> list[dict]:
    """Full internal question dicts (include answer keys). Server-side only."""
    return list(_bank()["questions"])


def get_question(question_id: str) -> dict | None:
    """Full internal question dict (includes answer key). Server-side only."""
    return _bank()["by_id"].get(question_id)


def marks_for(question: dict) -> int:
    return int(question.get("marks", 1))


# ---- selection -------------------------------------------------------------

def select_questions(category: str, difficulty: str, count: int, seed: int) -> list[str]:
    """Deterministically pick `count` question ids for the given filters using `seed`.

    category: a valid category OR 'mixed' (draw from all). difficulty: a valid level OR 'mixed'.
    Randomized but reproducible for a seed, so an attempt's question set survives a refresh.
    Returns fewer ids only if the bank cannot supply `count` matching questions.
    """
    pool = all_questions()
    if category != "mixed":
        pool = [q for q in pool if q["category"] == category]
    if difficulty != "mixed":
        pool = [q for q in pool if q["difficulty"] == difficulty]

    rng = random.Random(seed)
    ids = [q["id"] for q in pool]
    rng.shuffle(ids)
    return ids[:count]


def option_order(question: dict, seed: int) -> list[str]:
    """Deterministic display order of option ids for a choice question (randomized answer options).
    True/False questions have no options list."""
    opts = [o["id"] for o in question.get("options", [])]
    rng = random.Random(seed)
    rng.shuffle(opts)
    return opts


# ---- client-safe projections (NO answer keys / explanations) ---------------

def public_question(question: dict, option_ids_in_order: list[str] | None = None) -> dict:
    """Projection safe to send BEFORE submission. Strips correct_options, correct_bool and explanation.
    `option_ids_in_order` supplies the (already randomized) display order if provided."""
    out = {
        "id": question["id"],
        "category": question["category"],
        "difficulty": question["difficulty"],
        "type": question["type"],
        "marks": marks_for(question),
        "prompt": question["prompt"],
    }
    if question["type"] in ("single", "multi"):
        by_id = {o["id"]: o for o in question["options"]}
        order = option_ids_in_order or [o["id"] for o in question["options"]]
        out["options"] = [{"id": oid, "text": by_id[oid]["text"]} for oid in order if oid in by_id]
    return out


def review_question(question: dict) -> dict:
    """Projection safe to send AFTER submission — includes the correct answer and explanation for
    question-by-question review."""
    out = public_question(question)
    out["explanation"] = question.get("explanation", "")
    if question["type"] == "tf":
        out["correct_bool"] = bool(question["correct_bool"])
    else:
        out["correct_options"] = list(question["correct_options"])
    out["concept_ids"] = list(question.get("concept_ids", []))
    return out


def category_label(cat: str) -> str:
    return {
        "dsa": "Data Structures & Algorithms", "java": "Java", "python": "Python", "c": "C",
        "cpp": "C++", "dbms": "DBMS", "sql": "SQL", "os": "Operating Systems",
        "networks": "Computer Networks", "oop": "Object-Oriented Programming",
        "architecture": "Computer Architecture", "software_engineering": "Software Engineering",
        "mixed": "Mixed Technical",
    }.get(cat, cat)


def bank_stats() -> dict:
    """Counts for validation / reporting (no answer keys)."""
    qs = all_questions()
    by_cat: dict[str, int] = {}
    by_diff: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for q in qs:
        by_cat[q["category"]] = by_cat.get(q["category"], 0) + 1
        by_diff[q["difficulty"]] = by_diff.get(q["difficulty"], 0) + 1
        by_type[q["type"]] = by_type.get(q["type"], 0) + 1
    return {"total": len(qs), "by_category": by_cat, "by_difficulty": by_diff, "by_type": by_type}
