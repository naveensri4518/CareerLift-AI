"""Offline fairness report (DESIGN.md section 2). NO model, NO AWS.

Given scored rows that carry pair_id, register, technical_band and the human-labelled band, this computes:
  - mean & max fairness gap over paraphrase pairs (ordinal band distance),
  - technical accuracy vs human labels (the anti-flattening guard, reported ALONGSIDE the gap),
  - per-pair failures where the gap exceeds FAIR_TOL.

A row is a dict like the one agent/score.py returns (it includes pair_id, register, technical_band,
expected_technical_band). Pairs are matched by pair_id with registers 'plain' and 'advanced'.
"""
from __future__ import annotations

import statistics

from . import fairscore
from .models import BANDS

VALID_REGISTERS = ("plain", "advanced")


def _abstained(row: dict) -> bool:
    return row.get("technical_band") is None or bool(row.get("abstained_technical"))


def _valid_band_or_none(b) -> bool:
    """A technical band may be a valid band name OR None (an abstained row is legitimately bandless)."""
    return b is None or b in BANDS


def validate_rows(rows: list[dict]) -> dict:
    """Validate the paired dataset BEFORE computing metrics. Never silently overwrites duplicates.

    Returns:
      valid:        rows that passed structural checks (dedup key preserved)
      labelled:     valid rows that ALSO carry a valid expected_technical_band (usable for accuracy)
      unlabelled:   valid rows WITHOUT ground truth (excluded from accuracy, reported separately)
      invalid:      [{index, pair_id, register, reasons}] for each rejected row (structurally bad / duplicate)
      by_pair:      {pair_id: {register: row}} built ONLY from valid, non-duplicate rows
      duplicates:   list of (pair_id, register) seen more than once

    Ground-truth rule (Fix 3): a MISSING expected_technical_band is NOT a structural error — the row is
    kept as 'unlabelled' and excluded from technical-accuracy. A PRESENT-but-not-a-band value IS invalid.
    """
    invalid: list[dict] = []
    seen_keys: dict[tuple, int] = {}
    duplicates: list = []
    by_pair: dict[str, dict[str, dict]] = {}
    valid: list[dict] = []
    labelled: list[dict] = []
    unlabelled: list[dict] = []

    for i, r in enumerate(rows):
        reasons = []
        pid = r.get("pair_id")
        reg = r.get("register")
        tech = r.get("technical_band")
        exp = r.get("expected_technical_band")
        has_label_key = "expected_technical_band" in r and r.get("expected_technical_band") is not None

        if not pid:
            reasons.append("missing pair_id")
        if reg not in VALID_REGISTERS:
            reasons.append(f"invalid register {reg!r} (expected one of {VALID_REGISTERS})")
        if not _valid_band_or_none(tech):
            reasons.append(f"invalid technical_band {tech!r}")
        # Ground truth: if PRESENT it must be a valid band. If ABSENT, the row is unlabelled (not invalid).
        if has_label_key and exp not in BANDS:
            reasons.append(f"invalid expected_technical_band {exp!r}")

        if reasons:
            invalid.append({"index": i, "pair_id": pid, "register": reg, "reasons": reasons})
            continue

        key = (pid, reg)
        if key in seen_keys:
            # Do NOT overwrite the earlier record; flag the duplicate and reject this one.
            duplicates.append(key)
            invalid.append({"index": i, "pair_id": pid, "register": reg,
                            "reasons": [f"duplicate (pair_id, register) {key}; earlier row kept, this one rejected"]})
            continue
        seen_keys[key] = i
        by_pair.setdefault(pid, {})[reg] = r
        valid.append(r)
        if has_label_key:
            labelled.append(r)
        else:
            unlabelled.append(r)

    return {"valid": valid, "labelled": labelled, "unlabelled": unlabelled,
            "invalid": invalid, "by_pair": by_pair, "duplicates": sorted(set(duplicates))}


def report(rows: list[dict]) -> dict:
    validation = validate_rows(rows)
    valid_rows = validation["valid"]
    by_pair = validation["by_pair"]

    total_rows = len(rows)
    abstained_rows = sum(1 for r in valid_rows if _abstained(r))

    gaps: list[int] = []
    failures: list[dict] = []
    incomplete_pairs = 0        # a pair missing one of its two registers
    unscorable_pairs = 0        # both registers present but at least one abstained -> no gap computable
    scorable_pairs = 0

    for pid, pair in by_pair.items():
        if "plain" not in pair or "advanced" not in pair:
            incomplete_pairs += 1
            continue
        gap = fairscore.fairness_gap(pair["plain"].get("technical_band"),
                                     pair["advanced"].get("technical_band"))
        if gap is None:
            unscorable_pairs += 1   # at least one side abstained; cannot claim fairness on this pair
            continue
        scorable_pairs += 1
        gaps.append(gap)
        if gap > fairscore.FAIR_TOL:
            failures.append({"pair_id": pid, "gap": gap,
                             "plain_band": pair["plain"].get("technical_band"),
                             "advanced_band": pair["advanced"].get("technical_band")})

    # Technical accuracy (Fix 3): computed ONLY over LABELLED rows (those with ground truth) that also
    # produced a band (non-abstained). UNLABELLED rows are excluded — missing ground truth is never
    # silently treated as accuracy data. scored_fraction flags non-representative numbers under heavy
    # abstention.
    labelled_rows = validation["labelled"]
    unlabelled_rows = validation["unlabelled"]
    scored = [r for r in labelled_rows if r.get("technical_band")]
    correct = sum(1 for r in scored if r["technical_band"] == r["expected_technical_band"])
    tech_accuracy = round(correct / len(scored), 3) if scored else None
    scored_fraction = round(len(scored) / len(labelled_rows), 3) if labelled_rows else 0.0

    total_pairs = len(by_pair)
    return {
        # dataset validation (transparent: valid vs invalid vs unlabelled vs incomplete vs unscorable)
        "rows_submitted": total_rows,
        "rows_valid": len(valid_rows),
        "rows_labelled": len(labelled_rows),
        "rows_unlabelled": len(unlabelled_rows),
        "rows_invalid": len(validation["invalid"]),
        "invalid_rows": validation["invalid"],
        "duplicate_keys": validation["duplicates"],
        # pair accounting (transparent)
        "total_pairs": total_pairs,
        "pairs_scored": scorable_pairs,
        "incomplete_pairs": incomplete_pairs,
        "unscorable_pairs_due_to_abstention": unscorable_pairs,
        # fairness gap (unchanged calculation, over scorable pairs only)
        "mean_fairness_gap": round(statistics.mean(gaps), 3) if gaps else None,
        "max_fairness_gap": max(gaps) if gaps else None,
        "fair_tol": fairscore.FAIR_TOL,
        "fairness_failures": failures,
        # abstention reported separately (over VALID rows)
        "rows_total": len(valid_rows),
        "rows_abstained": abstained_rows,
        "abstention_rate": round(abstained_rows / len(valid_rows), 3) if valid_rows else 0.0,
        # accuracy, transparent about ground truth and abstention
        "technical_accuracy_on_scored": tech_accuracy,
        "scored_fraction": scored_fraction,
        "accuracy_basis": "labelled, non-abstained rows only",
        "accuracy_representative": bool(scored_fraction >= 0.5 and labelled_rows),
        "note": ("Rows are validated first: structurally invalid rows (missing pair_id, bad register, bad "
                 "band value) and duplicate (pair_id, register) keys are rejected and listed, never silently "
                 "overwritten. Rows WITHOUT expected_technical_band are kept but marked UNLABELLED and "
                 "EXCLUDED from technical accuracy — missing ground truth is never counted as accuracy data. "
                 "Fairness gap is over SCORABLE pairs only; incomplete and abstention-unscorable pairs are "
                 "counted separately so abstaining cannot improve the gap. Accuracy is over labelled, "
                 "non-abstained rows and is flagged non-representative when scored_fraction < 0.5. No claim "
                 "of bias-free live answers."),
    }
