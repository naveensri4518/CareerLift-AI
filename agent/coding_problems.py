"""Phase 2 — Coding Arena problem bank (server-owned, read-only).

Loads the curated problem bank from agent/data/coding_problems.json. Hidden test cases live here and are
NEVER returned by any public-facing function — the router only ever exposes `public_view`. Problem
concept_ids map into agent/data/concepts.json so a correct solution can feed the shared Phase 0 mastery
model (see api/routers/coding.py). No model/AWS; pure data access.
"""
from __future__ import annotations

import functools
import json
import pathlib

_DATA = pathlib.Path(__file__).with_name("data") / "coding_problems.json"

DIFFICULTIES = ("beginner", "intermediate", "advanced")

# Hard ceilings the server enforces regardless of a problem's declared limits (defence in depth).
MAX_TIME_MS = 5000
MAX_MEMORY_MB = 512


@functools.lru_cache(maxsize=1)
def _bank() -> dict:
    with _DATA.open(encoding="utf-8") as fh:
        data = json.load(fh)
    by_id = {}
    for p in data.get("problems", []):
        if p["difficulty"] not in DIFFICULTIES:
            raise ValueError(f"problem {p['id']} has unknown difficulty {p['difficulty']!r}")
        by_id[p["id"]] = p
    return {"problems": data.get("problems", []), "by_id": by_id}


def all_problems() -> list[dict]:
    """Full internal problem dicts (includes hidden tests). For server-side use only."""
    return list(_bank()["problems"])


def get_problem(problem_id: str) -> dict | None:
    """Full internal problem dict (includes hidden tests). For server-side use only."""
    return _bank()["by_id"].get(problem_id)


def effective_limits(problem: dict) -> dict:
    """The execution limits to enforce: the problem's declared limits, capped by the hard ceilings."""
    lim = problem.get("limits", {})
    return {
        "time_ms": min(int(lim.get("time_ms", 2000)), MAX_TIME_MS),
        "memory_mb": min(int(lim.get("memory_mb", 256)), MAX_MEMORY_MB),
    }


def public_view(problem: dict) -> dict:
    """Client-safe projection of a problem. Includes the PUBLIC tests and the declared limits, but NEVER
    the hidden tests. This is the only shape the API should send to a browser."""
    return {
        "id": problem["id"],
        "title": problem["title"],
        "difficulty": problem["difficulty"],
        "description": problem["description"],
        "input_format": problem["input_format"],
        "output_format": problem["output_format"],
        "constraints": list(problem.get("constraints", [])),
        "examples": list(problem.get("examples", [])),
        "public_tests": list(problem.get("public_tests", [])),
        "public_test_count": len(problem.get("public_tests", [])),
        "hidden_test_count": len(problem.get("hidden_tests", [])),
        "limits": effective_limits(problem),
        "concept_ids": list(problem.get("concept_ids", [])),
    }


def public_summary(problem: dict) -> dict:
    """Compact list-item projection (no test cases at all)."""
    return {
        "id": problem["id"],
        "title": problem["title"],
        "difficulty": problem["difficulty"],
        "concept_ids": list(problem.get("concept_ids", [])),
    }


def public_list() -> list[dict]:
    order = {d: i for i, d in enumerate(DIFFICULTIES)}
    return [public_summary(p) for p in sorted(all_problems(), key=lambda p: (order.get(p["difficulty"], 9), p["id"]))]
