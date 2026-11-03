"""Phase 4 — System Design Academy scenario bank (server-owned, read-only).

Loads agent/data/sysdesign_scenarios.json. The `rubric` block and per-item explanations/feedback live here
and are NEVER returned by a pre-submission public view. Component ids come from a shared catalog; a
scenario's `palette` restricts which components a student may use. Decision prompts expose their options
(text only) but NOT which are acceptable.

No model / AWS. Pure data access.
"""
from __future__ import annotations

import functools
import json
import pathlib

_SDATA = pathlib.Path(__file__).with_name("data") / "sysdesign_scenarios.json"
_CDATA = pathlib.Path(__file__).with_name("data") / "sysdesign_concepts.json"

DIFFICULTIES = ("beginner", "intermediate", "advanced")
DIMENSIONS = ("components", "connections", "data", "api", "scalability", "reliability", "tradeoffs")


@functools.lru_cache(maxsize=1)
def _bank() -> dict:
    data = json.loads(_SDATA.read_text(encoding="utf-8"))
    catalog = {c["id"]: c for c in data.get("component_catalog", [])}
    by_id = {}
    for s in data["scenarios"]:
        if s["difficulty"] not in DIFFICULTIES:
            raise ValueError(f"scenario {s['id']} has unknown difficulty {s['difficulty']!r}")
        by_id[s["id"]] = s
    return {"scenarios": data["scenarios"], "by_id": by_id, "catalog": catalog}


@functools.lru_cache(maxsize=1)
def sysdesign_concept_ids() -> frozenset[str]:
    data = json.loads(_CDATA.read_text(encoding="utf-8"))
    return frozenset(c["id"] for c in data["concepts"])


def component_catalog() -> dict:
    return dict(_bank()["catalog"])


def all_scenarios() -> list[dict]:
    """Full internal scenario dicts (include rubric). Server-side only."""
    return list(_bank()["scenarios"])


def get_scenario(scenario_id: str) -> dict | None:
    """Full internal scenario dict (includes rubric/answer keys). Server-side only."""
    return _bank()["by_id"].get(scenario_id)


def palette_components(scenario: dict) -> list[dict]:
    """The allowed component {id,label} list for a scenario's palette."""
    catalog = _bank()["catalog"]
    return [{"id": cid, "label": catalog.get(cid, {}).get("label", cid)} for cid in scenario.get("palette", [])]


# ---- client-safe projections (NO rubric / acceptable sets / feedback) ------

def public_decision_prompt(dp: dict) -> dict:
    """A decision prompt WITHOUT any indication of which option(s) are acceptable."""
    return {
        "id": dp["id"],
        "type": dp["type"],
        "prompt": dp["prompt"],
        "options": [{"id": o["id"], "text": o["text"]} for o in dp.get("options", [])],
    }


def public_scenario_summary(scenario: dict) -> dict:
    """List-item projection (no requirements/palette/rubric)."""
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "difficulty": scenario["difficulty"],
        "prompt": scenario["prompt"],
    }


def public_scenario(scenario: dict) -> dict:
    """Full client-safe brief: prompt, requirements, palette and decision prompts — but NO rubric,
    acceptable sets, explanations or feedback."""
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "difficulty": scenario["difficulty"],
        "prompt": scenario["prompt"],
        "functional_requirements": list(scenario.get("functional_requirements", [])),
        "nonfunctional_requirements": list(scenario.get("nonfunctional_requirements", [])),
        "palette": palette_components(scenario),
        "decision_prompts": [public_decision_prompt(dp) for dp in scenario.get("decision_prompts", [])],
    }


def public_list() -> list[dict]:
    order = {d: i for i, d in enumerate(DIFFICULTIES)}
    return [public_scenario_summary(s) for s in sorted(all_scenarios(), key=lambda s: (order.get(s["difficulty"], 9), s["id"]))]


def difficulty_label(d: str) -> str:
    return {"beginner": "Beginner", "intermediate": "Intermediate", "advanced": "Advanced"}.get(d, d)


def bank_stats() -> dict:
    scs = all_scenarios()
    by_diff: dict[str, int] = {}
    for s in scs:
        by_diff[s["difficulty"]] = by_diff.get(s["difficulty"], 0) + 1
    return {"total": len(scs), "by_difficulty": by_diff, "catalog_size": len(_bank()["catalog"])}
