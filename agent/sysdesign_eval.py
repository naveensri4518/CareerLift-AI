"""Phase 4 — deterministic System Design rubric grading. NO model / AWS.

A submission (design) has:
  components  : list of component ids (from the scenario palette)
  connections : list of [from_id, to_id] pairs (ids from the palette)
  decisions   : {decision_prompt_id: {"selected": [...]} or {"selected": ["opt"]}}

Grading is per-dimension and transparent:
  components  : fraction of the rubric's required_components present (recommended add a small bonus, capped).
  connections : fraction of required_connections present (direction-insensitive match).
  decisions   : each decision prompt maps to a dimension. single/"acceptable" -> full if the chosen option
                is in the acceptable set. multi/"expected" -> exact-set match of chosen vs expected.
  tradeoffs   : the trade-off decision prompt graded as a multi expected-set match.

Every score is in [0,1]; the overall percentage is the weighted mean across present dimensions. Nothing
is fabricated — matched/missing lists come straight from the rubric vs the submission.
"""
from __future__ import annotations

from . import sysdesign_bank


def _norm_conn(pair) -> tuple[str, str]:
    a, b = pair[0], pair[1]
    return (a, b) if a <= b else (b, a)   # direction-insensitive canonical form


def validate_design(scenario: dict, design: dict) -> list[str]:
    """Return a list of validation errors (unknown component/connection/decision ids). Empty = valid.
    Used by the router to reject malformed submissions (400) before grading."""
    errors: list[str] = []
    palette = set(scenario.get("palette", []))
    for cid in design.get("components", []) or []:
        if cid not in palette:
            errors.append(f"unknown component '{cid}'")
    for conn in design.get("connections", []) or []:
        if not isinstance(conn, (list, tuple)) or len(conn) != 2:
            errors.append(f"malformed connection {conn!r}")
            continue
        for cid in conn:
            if cid not in palette:
                errors.append(f"connection references unknown component '{cid}'")
    prompt_ids = {dp["id"] for dp in scenario.get("decision_prompts", [])}
    opt_ids = {dp["id"]: {o["id"] for o in dp.get("options", [])} for dp in scenario.get("decision_prompts", [])}
    for did, ans in (design.get("decisions") or {}).items():
        if did not in prompt_ids:
            errors.append(f"unknown decision prompt '{did}'")
            continue
        for sel in (ans or {}).get("selected", []) or []:
            if sel not in opt_ids.get(did, set()):
                errors.append(f"decision '{did}' references unknown option '{sel}'")
    return errors


def _dimension_for_decision(scenario: dict, decision_id: str) -> str:
    """Map a decision prompt to a rubric dimension via its concept's dimension, falling back by name."""
    dp = next((d for d in scenario["decision_prompts"] if d["id"] == decision_id), None)
    if not dp:
        return "components"
    # the scenario rubric declares concept_dimension per dimension; invert via the prompt's concept_id
    cid = dp.get("concept_id")
    for dim, dim_cid in scenario["rubric"].get("concept_dimension", {}).items():
        if dim_cid == cid:
            return dim
    return "tradeoffs" if decision_id == "tradeoffs" else "components"


def grade(scenario: dict, design: dict) -> dict:
    """Deterministically grade a design against a scenario rubric. Returns a client-safe result payload
    (includes expected design for post-submission review — the router only returns it after submit)."""
    rubric = scenario["rubric"]
    comps = set(design.get("components", []) or [])
    conns = {_norm_conn(c) for c in (design.get("connections", []) or []) if isinstance(c, (list, tuple)) and len(c) == 2}
    decisions = design.get("decisions") or {}

    dims: dict[str, dict] = {}

    # --- components dimension ---
    required_c = rubric.get("required_components", [])
    recommended_c = rubric.get("recommended_components", [])
    matched_req = [c for c in required_c if c in comps]
    missing_req = [c for c in required_c if c not in comps]
    base = (len(matched_req) / len(required_c)) if required_c else 1.0
    bonus = (sum(1 for c in recommended_c if c in comps) / len(recommended_c) * 0.15) if recommended_c else 0.0
    dims["components"] = {
        "score": round(min(1.0, base + bonus), 3),
        "matched": matched_req, "missing": missing_req,
        "concept_id": rubric["concept_dimension"].get("components"),
    }

    # --- connections dimension ---
    required_conn = [_norm_conn(c) for c in rubric.get("required_connections", [])]
    matched_conn = [list(c) for c in required_conn if c in conns]
    missing_conn = [list(c) for c in required_conn if c not in conns]
    dims["connections"] = {
        "score": round((len(matched_conn) / len(required_conn)) if required_conn else 1.0, 3),
        "matched": matched_conn, "missing": missing_conn,
        "concept_id": rubric["concept_dimension"].get("connections"),
    }

    # --- decision-driven dimensions (data, api, scalability, reliability, tradeoffs) ---
    for did, spec in rubric.get("decisions", {}).items():
        dim = _dimension_for_decision(scenario, did)
        chosen = set((decisions.get(did) or {}).get("selected", []) or [])
        if "acceptable" in spec:        # single-ish: any chosen that is acceptable, and only acceptable
            acceptable = set(spec["acceptable"])
            ok = bool(chosen) and chosen <= acceptable
            score = 1.0 if ok else 0.0
            dims[dim] = {
                "score": score, "decision_id": did,
                "your_selected": sorted(chosen), "expected": sorted(acceptable),
                "concept_id": rubric["concept_dimension"].get(dim),
            }
        else:                            # multi: exact set match against expected
            expected = set(spec.get("expected", []))
            score = 1.0 if chosen == expected else 0.0
            dims[dim] = {
                "score": score, "decision_id": did,
                "your_selected": sorted(chosen), "expected": sorted(expected),
                "concept_id": rubric["concept_dimension"].get(dim),
            }

    # --- overall (unweighted mean across present dimensions) ---
    present = list(dims.values())
    overall = round(sum(d["score"] for d in present) / len(present) * 100, 1) if present else 0.0

    feedback = scenario.get("feedback", {})
    for dim, d in dims.items():
        d["feedback"] = feedback.get(dim, "")

    # matched/missing requirement summary (functional + nonfunctional are informational; the concrete
    # matched/missing signal is the rubric's required components + connections).
    return {
        "percentage": overall,
        "grade": grade_for(overall),
        "dimensions": dims,
        "missing_components": missing_req,
        "missing_connections": missing_conn,
        "strengths": sorted([dim for dim, d in dims.items() if d["score"] >= 0.75]),
        "weaknesses": sorted([dim for dim, d in dims.items() if d["score"] < 0.5]),
    }


def grade_for(percentage: float) -> str:
    if percentage >= 90:
        return "A"
    if percentage >= 75:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 40:
        return "D"
    return "F"


def dimension_outcomes(result: dict) -> dict[str, str]:
    """Reduce each dimension to a Phase-0 outcome: >=0.75 -> 'correct', <0.5 -> 'incorrect', else 'partial'.
    Used by the signal bridge to decide mastered vs struggled per concept."""
    out: dict[str, str] = {}
    for dim, d in result.get("dimensions", {}).items():
        cid = d.get("concept_id")
        if not cid:
            continue
        s = d["score"]
        out[cid] = "correct" if s >= 0.75 else ("incorrect" if s < 0.5 else "partial")
    return out
