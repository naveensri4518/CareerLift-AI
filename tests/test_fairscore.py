"""Deterministic FairScore core: verifier, grounding, bands, fairness gap. No model, no AWS."""
from agent import fairscore


def test_concepts_load():
    ids = fairscore.concept_ids()
    assert {"C-HASH-AVG", "C-BINSEARCH", "C-BIGO-DEF"} <= ids


def test_evidence_grounding_normalised():
    ans = "A hash map gives O(1) lookup on average but O(n) worst case."
    assert fairscore.span_is_grounded("O(1) lookup on average", ans)
    assert fairscore.span_is_grounded("o(1)   LOOKUP on average", ans)  # whitespace + case
    assert not fairscore.span_is_grounded("binary search", ans)
    assert not fairscore.span_is_grounded("", ans)


def test_verifier_drops_unknown_and_ungrounded():
    ans = "A hash map gives O(1) lookup on average."
    claims = [
        {"concept_id": "C-HASH-AVG", "status": "supported", "evidence_span": "O(1) lookup on average"},
        {"concept_id": "C-NOPE", "status": "supported", "evidence_span": "x"},          # unknown id
        {"concept_id": "C-BINSEARCH", "status": "supported", "evidence_span": "not here"},  # ungrounded
    ]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG", "C-BINSEARCH"], ans)
    assert v["best_status"].get("C-HASH-AVG") == "supported"
    assert "C-BINSEARCH" not in v["best_status"]
    assert len(v["dropped"]) == 2
    assert v["coverage"] == 0.5
    assert v["abstain"] is False


def test_verifier_abstains_on_low_coverage():
    v = fairscore.verify_claims([], ["C-HASH-AVG", "C-BINSEARCH"], "irrelevant")
    assert v["coverage"] == 0.0
    assert v["abstain"] is True


def test_supported_plus_absent_is_extraction_inconsistency_not_misconception():
    """supported + absent (no explicit wrong assertion) is EXTRACTION INCONSISTENCY, not a misconception."""
    ans = "binary search needs a sorted array and runs in log n"
    claims = [
        {"concept_id": "C-BINSEARCH", "status": "supported", "evidence_span": "binary search needs a sorted array"},
        {"concept_id": "C-BINSEARCH", "status": "absent", "evidence_span": ""},
    ]
    v = fairscore.verify_claims(claims, ["C-BINSEARCH"], ans)
    assert "C-BINSEARCH" in v["extraction_inconsistencies"]
    assert v["misconception_tags"] == []


def test_band_from_claims_is_pure_function_of_coverage():
    exp = ["C-HASH-AVG", "C-BINSEARCH"]
    assert fairscore.band_from_claims({"C-HASH-AVG": "supported", "C-BINSEARCH": "supported"}, exp) == "Strong"
    assert fairscore.band_from_claims({"C-HASH-AVG": "supported", "C-BINSEARCH": "absent"}, exp) == "Partial"
    assert fairscore.band_from_claims({"C-HASH-AVG": "absent", "C-BINSEARCH": "absent"}, exp) == "Weak"


def test_band_ignores_prose_entirely():
    """Same claim coverage -> same band regardless of how the answer was phrased.
    (The band function never sees prose; this asserts the structural guarantee.)"""
    exp = ["C-HASH-AVG"]
    plain = {"C-HASH-AVG": "supported"}
    fancy = {"C-HASH-AVG": "supported"}
    assert fairscore.band_from_claims(plain, exp) == fairscore.band_from_claims(fancy, exp)


def test_comm_band_ignores_length_and_grammar():
    allp = {"clarity": "present", "structure": "present", "relevance": "present", "organisation": "present"}
    assert fairscore.comm_band(allp) == "Strong"           # a short all-present answer is Strong
    weak = {"clarity": "absent", "structure": "absent", "relevance": "partial", "organisation": "absent"}
    assert fairscore.comm_band(weak) == "Weak"
    solid = {"clarity": "present", "structure": "present", "relevance": "present", "organisation": "absent"}
    assert fairscore.comm_band(solid) == "Solid"


def test_fairness_gap_ordinal():
    assert fairscore.fairness_gap("Solid", "Solid") == 0
    assert fairscore.fairness_gap("Weak", "Strong") == 3
    assert fairscore.fairness_gap("Partial", "Solid") == 1
    assert fairscore.fairness_gap(None, "Strong") is None


def test_misconception_mapping():
    # a specific misconception requires a grounded INCORRECT assertion matching a curated signature
    assert "M-HASH-ALWAYS-O1" in fairscore.misconception_for("C-HASH-AVG", "incorrect", "hash is always O(1)")
    # non-incorrect statuses never yield a tag
    assert fairscore.misconception_for("C-HASH-AVG", "partial", "") == []
    assert fairscore.misconception_for("C-HASH-AVG", "absent", "") == []
    assert fairscore.misconception_for("C-HASH-AVG", "supported", "") == []
    # an incorrect assertion that matches no signature -> no specific tag (real but uncertain)
    assert fairscore.misconception_for("C-HASH-AVG", "incorrect", "something vaguely wrong") == []
