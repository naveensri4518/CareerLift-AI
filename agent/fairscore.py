"""CareerLift AI — the deterministic FairScore core. NO model calls in this file.

This is the code that owns the facts (DESIGN.md sections 3, 6, 7). The model only extracts
claims and observations; everything here is pure, unit-testable Python:

  - verify_claims()  : the Verifier. Checks concept-id validity, evidence-span grounding,
                       relevance, internal contradiction; computes coverage support; decides abstain.
  - band_from_claims(): maps verified claim coverage -> a technical band. Prose style is NEVER an input.
  - comm_band()       : maps four {present/partial/absent} observations -> a communication band.
                        Grammar / accent / vocabulary / length are NEVER inputs.
  - fairness_gap()    : OFFLINE only. Ordinal distance between a paraphrase pair's technical bands.

Honesty (DESIGN.md section 2 & 6): grounding an evidence span proves the model quoted the student,
NOT that the answer is technically correct. Correctness is established only against human labels offline.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from .models import BANDS

DATA = Path(__file__).parent / "data"

# ---- calibrated constants (DESIGN.md section 3). Our own values; change -> re-measure -> log in FAILURES.md.
BAND_CUTS = (0.85, 0.60, 0.30)   # coverage >= .85 Strong, >= .60 Solid, >= .30 Partial, else Weak
COMM_CUTS = (3.5, 2.5, 1.5)      # observation-sum cutoffs for Strong / Solid / Partial (see comm_band)
ABSTAIN_MIN_SUPPORT = 0.30       # below this coverage the Verifier abstains (fail-closed)
FAIR_TOL = 1                     # offline: a paraphrase pair may differ by at most this many bands

ABSTAIN_TEXT = ("We could not confidently assess the technical content of this answer: too few of the "
                "expected points were clearly addressed. Here is what we did recognise; try explaining "
                "those parts again in your own words.")


@lru_cache(maxsize=1)
def concepts() -> dict:
    return json.loads((DATA / "concepts.json").read_text(encoding="utf-8"))


def concept_ids() -> set[str]:
    return {c["id"] for c in concepts()["concepts"]}


def concept_by_id() -> dict:
    return {c["id"]: c for c in concepts()["concepts"]}


def exclusion_pairs() -> list[set[str]]:
    return [set(p) for p in concepts().get("exclusion_pairs", [])]


# Word tokens that, if present in a concept's key_points, we look for in the evidence span to decide
# whether the quoted text PLAUSIBLY touches the concept's substance. This is a weak overlap heuristic,
# NOT proof of correctness (DESIGN.md section 6). It only gates "supported" vs "partial".
_WORD = re.compile(r"[a-z0-9()]+")


def _keypoint_terms(concept_id: str) -> set[str]:
    c = concept_by_id().get(concept_id, {})
    terms: set[str] = set()
    for kp in c.get("key_points", []):
        terms |= {w for w in _WORD.findall(kp.lower()) if len(w) > 2}
    for alias in c.get("aliases", []):
        terms |= {w for w in _WORD.findall(alias.lower()) if len(w) > 2}
    # drop very common words that carry no signal
    stop = {"the", "and", "all", "are", "can", "use", "uses", "with", "over", "each", "once",
            "lower", "upper", "across", "value", "values", "time", "space", "where", "than", "that"}
    return terms - stop


def evidence_supports_keypoints(concept_id: str, evidence_span: str) -> bool:
    """Weak check: does the quoted evidence share vocabulary with the concept's key points?

    True does NOT mean the answer is technically correct — only that the quote plausibly concerns this
    concept. Used to decide whether to TRUST a 'supported' claim or downgrade it to 'partial'.
    """
    terms = _keypoint_terms(concept_id)
    if not terms:
        return True  # no key points to check against -> do not penalise
    ev = {w for w in _WORD.findall(_norm(evidence_span)) if len(w) > 2}
    return bool(terms & ev)


# States the verifier distinguishes (Fix 2):
#   "supported"  -> correct enough to trust (grounded + on-topic)
#   "partial"    -> incomplete explanation (NOT a misconception)
#   "absent"     -> missing knowledge (NOT a misconception)
#   "incorrect"  -> the student made an explicit, grounded WRONG assertion. A SPECIFIC misconception is
#                   assigned only when that wrong assertion matches a curated misconception signature;
#                   otherwise the error is real but UNCERTAIN (no specific tag).
#   "extraction_inconsistency" -> conflicting extraction labels with no grounded incorrect assertion
#                   (a model artefact, never a misconception).
def match_misconception(concept_id: str, incorrect_text: str) -> list[str]:
    """Match a grounded incorrect assertion to a SPECIFIC misconception via curated signatures.

    Returns the misconception id(s) whose signature phrases appear in the incorrect assertion. Empty if
    the error does not match any known misconception (then it is a real-but-uncertain error, no tag).
    This is a heuristic match against curated definitions; it does NOT prove the student's internal belief.
    """
    text = _norm(incorrect_text)
    if not text:
        return []
    out = []
    for m in concepts().get("misconceptions", []):
        if m.get("about") != concept_id:
            continue
        signatures = [_norm(s) for s in m.get("signature", [])]
        if any(sig and sig in text for sig in signatures):
            out.append(m["id"])
    return out


def misconception_for(concept_id: str, status: str, incorrect_text: str = "") -> list[str]:
    """Return a SPECIFIC misconception tag ONLY for a grounded 'incorrect' assertion matching a signature.

    'supported'/'partial'/'absent'/'contradicted'/'extraction_inconsistency' never yield a specific
    misconception by themselves. Only an explicit grounded WRONG assertion whose wording matches a
    curated misconception signature does. Insufficient/unmatched evidence -> no tag (uncertain).
    """
    if status != "incorrect":
        return []
    return match_misconception(concept_id, incorrect_text)


# ---------------------------------------------------------------------------
# Evidence-span grounding
# ---------------------------------------------------------------------------
def _norm(s: str) -> str:
    """Normalise for substring grounding: unicode NFKC, casefold, collapse whitespace."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()


def span_is_grounded(evidence_span: str, answer: str) -> bool:
    """True if the quoted span actually appears in the student's answer (normalised)."""
    span = _norm(evidence_span)
    if not span:
        return False
    return span in _norm(answer)


# ---------------------------------------------------------------------------
# The Verifier (deterministic). DESIGN.md section 6.
# ---------------------------------------------------------------------------
def verify_claims(claims: list[dict], expected_concepts: list[str], answer: str) -> dict:
    """Check extracted claims against the concept reference and the student's answer.

    Returns a dict with:
      verified:   claims that survived id-validity + relevance + grounding
      dropped:    {claim, reason} for each dropped claim (unknown id / ungrounded span)
      contradictions: list of concept_ids or exclusion pairs flagged
      coverage:   fraction of expected_concepts addressed (supported or partial) by verified claims
      support:    same as coverage (named for the abstain rule)
      abstain:    coverage < ABSTAIN_MIN_SUPPORT
    """
    ids = concept_ids()
    expected = list(dict.fromkeys(expected_concepts))
    verified: list[dict] = []
    dropped: list[dict] = []
    downgraded: list[dict] = []

    # status per expected concept from the surviving, relevant claims
    best: dict[str, str] = {}
    seen_status: dict[str, set[str]] = {}
    # grounded evidence spans seen per concept per status: needed to tell a DEMONSTRATED contradiction
    # (distinct contradictory quotes) from an EXTRACTION INCONSISTENCY (conflicting labels, no real
    # contradictory evidence).
    spans_by_status: dict[str, dict[str, set[str]]] = {}

    # Positive/incorrect claims DROPPED for lack of grounding, per concept. An ungrounded 'incorrect'
    # cannot justify a misconception (Fix 2 requires a GROUNDED wrong assertion).
    ungrounded_positive: set[str] = set()
    # Grounded incorrect assertions per concept: {concept_id: [grounded_text, ...]}.
    incorrect_assertions: dict[str, list[str]] = {}

    for c in claims:
        cid = c.get("concept_id", "")
        status = c.get("status", "absent")
        span = c.get("evidence_span", "")
        if cid not in ids:
            dropped.append({"claim": c, "reason": "unknown concept_id"})
            continue
        if cid not in expected:
            dropped.append({"claim": c, "reason": "not in expected_concepts (kept for feedback only)"})
            continue
        # grounding is required whenever the model asserts anything concrete (present OR wrong)
        if status in ("supported", "partial", "incorrect") and not span_is_grounded(span, answer):
            dropped.append({"claim": c, "reason": "evidence span not found in answer"})
            ungrounded_positive.add(cid)
            continue
        effective = status
        # evidence PRESENCE is not technical CORRECTNESS. A 'supported' claim whose grounded quote
        # shares no vocabulary with the concept's key points cannot be trusted as correct -> downgrade to
        # 'partial'. This never proves truth; it only prevents an off-topic quote counting as 'supported'.
        if status == "supported" and not evidence_supports_keypoints(cid, span):
            effective = "partial"
            downgraded.append({"concept_id": cid, "reason": "evidence does not match key points -> correctness not established"})
            c = {**c, "effective_status": "partial"}
        if effective == "incorrect":
            incorrect_assertions.setdefault(cid, []).append(span)
        verified.append(c)
        seen_status.setdefault(cid, set()).add(effective)
        spans_by_status.setdefault(cid, {}).setdefault(effective, set())
        if span_is_grounded(span, answer):
            spans_by_status[cid][effective].add(_norm(span))
        order = {"absent": 0, "partial": 1, "supported": 2, "incorrect": 3}
        if cid not in best or order.get(effective, 0) > order.get(best[cid], 0):
            best[cid] = effective

    # Classify each concept (Fix 2). A SPECIFIC misconception requires a GROUNDED 'incorrect' assertion
    # that matches a curated misconception signature. Nothing else does:
    #   - 'supported' + 'absent'  -> EXTRACTION INCONSISTENCY (conflicting labels, not a wrong assertion).
    #   - grounded 'incorrect' matching a signature -> that specific misconception tag.
    #   - grounded 'incorrect' with NO signature match -> a real error but UNCERTAIN (no specific tag).
    #   - 'partial' alone -> incomplete explanation. 'absent' alone -> missing knowledge.
    contradictions: list = []                 # kept for back-compat (exclusion pairs only)
    contradicted_concepts: set[str] = set()   # kept for back-compat; no longer fed by supported+absent
    extraction_inconsistencies: set[str] = set()
    misconception_concepts: set[str] = set()  # concepts with a grounded, signature-matched wrong assertion
    incorrect_uncertain: set[str] = set()     # grounded wrong assertion, but no known misconception matched
    specific_misconception_tags: list[str] = []

    for cid, statuses in seen_status.items():
        # conflicting positive/absent labels with no explicit wrong assertion = extraction noise
        if ("supported" in statuses or "partial" in statuses) and "absent" in statuses and "incorrect" not in statuses:
            extraction_inconsistencies.add(cid)

    # grounded incorrect assertions -> try to match a specific misconception
    for cid, spans in incorrect_assertions.items():
        matched_here: list[str] = []
        for span in spans:
            matched_here += match_misconception(cid, span)
        matched_here = list(dict.fromkeys(matched_here))
        if matched_here:
            misconception_concepts.add(cid)
            specific_misconception_tags += matched_here
            best[cid] = "incorrect"
        else:
            incorrect_uncertain.add(cid)
            best[cid] = "incorrect"   # a real error, but we cannot name a specific misconception

    # An ungrounded positive/incorrect claim alongside an 'absent' claim is also extraction inconsistency.
    for cid in ungrounded_positive:
        if "absent" in seen_status.get(cid, set()) and cid not in misconception_concepts:
            extraction_inconsistencies.add(cid)
            best.setdefault(cid, "absent")

    # Exclusion pairs (empty by default): two claims about the SAME thing both 'supported' is a genuine
    # internal contradiction. Kept as a separate, rarely-used signal; it does NOT auto-assign a tag.
    for pair in exclusion_pairs():
        if all(best.get(cid) == "supported" for cid in pair):
            contradictions.append(sorted(pair))
            contradicted_concepts.update(pair)

    # coverage: concepts the student addressed at all. 'incorrect' addresses the concept (wrongly), so it
    # counts toward coverage for the abstain decision, but is weighted 0 in band_from_claims.
    addressed = sum(1 for cid in expected if best.get(cid) in ("supported", "partial", "incorrect"))
    coverage = addressed / len(expected) if expected else 0.0

    return {
        "verified": verified,
        "dropped": dropped,
        "downgraded": downgraded,
        "contradictions": contradictions,
        "contradicted_concepts": sorted(contradicted_concepts),
        "extraction_inconsistencies": sorted(extraction_inconsistencies),
        "ungrounded_positive": sorted(ungrounded_positive),
        "misconception_concepts": sorted(misconception_concepts),
        "incorrect_uncertain": sorted(incorrect_uncertain),
        "misconception_tags": list(dict.fromkeys(specific_misconception_tags)),
        "best_status": best,
        "coverage": coverage,
        "support": coverage,
        "abstain": coverage < ABSTAIN_MIN_SUPPORT,
    }


# ---------------------------------------------------------------------------
# Deterministic banding. Prose style is NEVER an input here.
# ---------------------------------------------------------------------------
def _weighted_coverage(best_status: dict[str, str], expected_concepts: list[str]) -> float:
    """supported = 1.0, partial = 0.5, absent/missing = 0.0, averaged over expected concepts."""
    expected = list(dict.fromkeys(expected_concepts))
    if not expected:
        return 0.0
    w = {"supported": 1.0, "partial": 0.5, "absent": 0.0, "contradicted": 0.0, "incorrect": 0.0}
    total = sum(w.get(best_status.get(cid, "absent"), 0.0) for cid in expected)
    return total / len(expected)


def band_from_claims(best_status: dict[str, str], expected_concepts: list[str]) -> str:
    """Map weighted concept coverage -> technical band. Pure function of claims, not prose."""
    cov = _weighted_coverage(best_status, expected_concepts)
    strong, solid, partial = BAND_CUTS
    if cov >= strong:
        return "Strong"
    if cov >= solid:
        return "Solid"
    if cov >= partial:
        return "Partial"
    return "Weak"


def comm_band(obs: dict) -> str:
    """Map the four observations -> communication band. Grammar/accent/vocab/length are NOT inputs.

    obs keys: clarity, structure, relevance, organisation, each in {present, partial, absent}.
    """
    val = {"present": 1.0, "partial": 0.5, "absent": 0.0}
    dims = ["clarity", "structure", "relevance", "organisation"]
    vals = [val.get(obs.get(d, "absent"), 0.0) for d in dims]
    s = sum(vals)
    n_absent = sum(1 for v in vals if v == 0.0)
    strong, solid, partial = COMM_CUTS
    if s >= strong and n_absent == 0:
        return "Strong"
    if s >= solid and n_absent <= 1:
        return "Solid"
    if s >= partial:
        return "Partial"
    return "Weak"


# ---------------------------------------------------------------------------
# Offline fairness helpers (DESIGN.md section 2). Used by score.py / measure, never at run time.
# ---------------------------------------------------------------------------
def band_ordinal(band: str | None) -> int | None:
    return BANDS.index(band) if band in BANDS else None


def fairness_gap(band_a: str | None, band_b: str | None) -> int | None:
    """Ordinal distance between the technical bands of a paraphrase pair. None if either abstained."""
    oa, ob = band_ordinal(band_a), band_ordinal(band_b)
    if oa is None or ob is None:
        return None
    return abs(oa - ob)
