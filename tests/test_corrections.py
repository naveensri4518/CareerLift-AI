"""Regression tests for the targeted correction phase. No model, no AWS."""
from agent import fairscore, fairness_report


# ---------------- P0: contradiction logic ----------------

def test_hash_and_binsearch_not_mutually_exclusive():
    """Different algorithms must both be supportable at once (invalid exclusion pair removed)."""
    assert fairscore.exclusion_pairs() == [] or all(
        {"C-HASH-AVG", "C-BINSEARCH"} != p for p in fairscore.exclusion_pairs()
    )
    ans = "A hash map lookup is O(1) on average; binary search is O(log n) on a sorted array."
    claims = [
        {"concept_id": "C-HASH-AVG", "status": "supported", "evidence_span": "hash map lookup is O(1) on average"},
        {"concept_id": "C-BINSEARCH", "status": "supported", "evidence_span": "binary search is O(log n) on a sorted array"},
    ]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG", "C-BINSEARCH"], ans)
    assert v["contradictions"] == []
    assert v["best_status"]["C-HASH-AVG"] == "supported"
    assert v["best_status"]["C-BINSEARCH"] == "supported"
    assert fairscore.band_from_claims(v["best_status"], ["C-HASH-AVG", "C-BINSEARCH"]) == "Strong"


# ---------------- P0: no duplicate model invocation ----------------

def test_structured_once_or_retry_calls_once_on_success():
    from agent.app import structured_once_or_retry

    class Res:
        def __init__(self, so): self.structured_output = so

    class FakeAgent:
        def __init__(self): self.calls = 0
        def __call__(self, msg):
            self.calls += 1
            return Res("GOOD")

    a = FakeAgent()
    out = structured_once_or_retry(a, "msg", max_calls=2)
    assert out == "GOOD"
    assert a.calls == 1, "must not call the model a second time once it succeeds"


def test_structured_once_or_retry_retries_then_gives_up():
    from agent.app import structured_once_or_retry

    class Res:
        def __init__(self, so): self.structured_output = so

    class AlwaysNone:
        def __init__(self): self.calls = 0
        def __call__(self, msg):
            self.calls += 1
            return Res(None)

    a = AlwaysNone()
    out = structured_once_or_retry(a, "msg", max_calls=2)
    assert out is None
    assert a.calls == 2, "exactly max_calls attempts, no hidden extra call"


# ---------------- P1: evidence presence != technical correctness ----------------

def test_supported_downgraded_when_evidence_offtopic():
    """A 'supported' claim whose quote shares no key-point vocabulary is downgraded to partial."""
    ans = "I really like coding and I practise every day with my friends."
    claims = [{"concept_id": "C-HASH-AVG", "status": "supported",
               "evidence_span": "I really like coding"}]   # grounded, but off-topic for the concept
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert v["best_status"]["C-HASH-AVG"] == "partial"
    assert v["downgraded"], "off-topic evidence should be recorded as downgraded"


def test_supported_kept_when_evidence_matches_keypoints():
    ans = "A hash table lookup is O(1) on average but O(n) in the worst case under collisions."
    claims = [{"concept_id": "C-HASH-AVG", "status": "supported",
               "evidence_span": "hash table lookup is O(1) on average"}]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert v["best_status"]["C-HASH-AVG"] == "supported"


# ---------------- P1: misconception only on demonstrated contradiction ----------------

# ---------------- Fix 2: demonstrated misconception requires a grounded incorrect assertion ----------------

def test_supported_plus_absent_without_incorrect_assertion_is_not_misconception():
    """supported + absent, no explicit wrong assertion -> extraction inconsistency, NOT a misconception."""
    ans = "hash map is O(1) on average. but also hash map is not relevant here."
    claims = [
        {"concept_id": "C-HASH-AVG", "status": "supported", "evidence_span": "hash map is O(1) on average"},
        {"concept_id": "C-HASH-AVG", "status": "absent", "evidence_span": ""},
    ]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert "C-HASH-AVG" in v["extraction_inconsistencies"]
    assert v["misconception_tags"] == []


def test_grounded_incorrect_assertion_assigns_specific_misconception():
    """A grounded wrong assertion matching a curated signature -> that specific misconception."""
    ans = "a hash map lookup is always O(1), it is never O(n)."
    claims = [{"concept_id": "C-HASH-AVG", "status": "incorrect", "evidence_span": "a hash map lookup is always O(1)"}]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert "M-HASH-ALWAYS-O1" in v["misconception_tags"]
    assert "C-HASH-AVG" in v["misconception_concepts"]
    assert v["best_status"]["C-HASH-AVG"] == "incorrect"


def test_ungrounded_incorrect_assertion_no_misconception():
    """An 'incorrect' claim whose span is not in the answer is dropped -> no misconception."""
    ans = "I spoke only about recursion, nothing about hashing."
    claims = [{"concept_id": "C-HASH-AVG", "status": "incorrect", "evidence_span": "hash is always O(1)"}]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert v["misconception_tags"] == []
    assert "C-HASH-AVG" in v["ungrounded_positive"]


def test_grounded_incorrect_without_signature_is_uncertain_not_tagged():
    """A grounded wrong assertion that matches no known signature -> real error, but no specific tag."""
    ans = "a hash map is basically a type of linked list, I think."
    claims = [{"concept_id": "C-HASH-AVG", "status": "incorrect", "evidence_span": "a hash map is basically a type of linked list"}]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert v["misconception_tags"] == []
    assert "C-HASH-AVG" in v["incorrect_uncertain"]       # flagged as an error we cannot name
    assert v["best_status"]["C-HASH-AVG"] == "incorrect"


def test_conflicting_extraction_labels_not_misconception():
    """supported + absent with no usable positive evidence -> extraction inconsistency."""
    ans = "I talked about something unrelated to hashing entirely."
    claims = [
        {"concept_id": "C-HASH-AVG", "status": "supported", "evidence_span": "not present in the answer"},
        {"concept_id": "C-HASH-AVG", "status": "absent", "evidence_span": ""},
    ]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert "C-HASH-AVG" in v["extraction_inconsistencies"]
    assert v["misconception_tags"] == []


def test_missing_knowledge_is_absent_not_misconception():
    v = fairscore.verify_claims(
        [{"concept_id": "C-HASH-AVG", "status": "absent", "evidence_span": ""}],
        ["C-HASH-AVG"], "I don't know this.")
    assert v["best_status"].get("C-HASH-AVG", "absent") == "absent"
    assert v["misconception_tags"] == []


def test_incomplete_explanation_is_partial_not_misconception():
    ans = "a hash map is fast"
    v = fairscore.verify_claims(
        [{"concept_id": "C-HASH-AVG", "status": "partial", "evidence_span": "a hash map is fast"}],
        ["C-HASH-AVG"], ans)
    assert v["best_status"]["C-HASH-AVG"] == "partial"
    assert v["misconception_tags"] == []


def test_insufficient_evidence_abstains_from_misconception():
    """No grounded incorrect assertion anywhere -> no misconception tag at all."""
    ans = "hashing is a thing in computer science."
    claims = [{"concept_id": "C-HASH-AVG", "status": "partial", "evidence_span": "hashing is a thing"}]
    v = fairscore.verify_claims(claims, ["C-HASH-AVG"], ans)
    assert v["misconception_tags"] == []


# ---------------- Task 4: fairness dataset validation ----------------

def _vrow(pid, reg, tech, expected):
    return {"pair_id": pid, "register": reg, "technical_band": tech, "expected_technical_band": expected}


def test_validation_valid_dataset():
    rows = [_vrow("p1", "plain", "Solid", "Solid"), _vrow("p1", "advanced", "Solid", "Solid")]
    r = fairness_report.report(rows)
    assert r["rows_valid"] == 2 and r["rows_invalid"] == 0
    assert r["pairs_scored"] == 1


def test_validation_duplicate_pair_register_not_overwritten():
    rows = [
        _vrow("p1", "plain", "Solid", "Solid"),
        _vrow("p1", "plain", "Weak", "Solid"),     # duplicate key -> rejected, earlier kept
        _vrow("p1", "advanced", "Solid", "Solid"),
    ]
    r = fairness_report.report(rows)
    assert ("p1", "plain") in r["duplicate_keys"]
    assert r["rows_invalid"] == 1
    assert r["rows_valid"] == 2


def test_validation_missing_pair_id():
    rows = [_vrow(None, "plain", "Solid", "Solid")]
    r = fairness_report.report(rows)
    assert r["rows_invalid"] == 1
    assert any("missing pair_id" in x["reasons"][0] for x in r["invalid_rows"])


def test_validation_invalid_register():
    rows = [_vrow("p1", "fancy", "Solid", "Solid")]
    r = fairness_report.report(rows)
    assert r["rows_invalid"] == 1
    assert any("invalid register" in rsn for x in r["invalid_rows"] for rsn in x["reasons"])


def test_validation_invalid_technical_label():
    rows = [_vrow("p1", "plain", "Excellent", "Solid")]   # 'Excellent' is not a band
    r = fairness_report.report(rows)
    assert r["rows_invalid"] == 1


def test_validation_missing_counterpart_is_incomplete():
    rows = [_vrow("p1", "plain", "Solid", "Solid")]       # no advanced side
    r = fairness_report.report(rows)
    assert r["incomplete_pairs"] == 1
    assert r["pairs_scored"] == 0


def test_validation_mixed_valid_and_invalid():
    rows = [
        _vrow("p1", "plain", "Solid", "Solid"),
        _vrow("p1", "advanced", "Solid", "Solid"),
        _vrow(None, "plain", "Solid", "Solid"),           # invalid: missing pid
        _vrow("p2", "bogus", "Solid", "Solid"),           # invalid: register
    ]
    r = fairness_report.report(rows)
    assert r["rows_valid"] == 2 and r["rows_invalid"] == 2
    assert r["pairs_scored"] == 1


# ---------------- Fix 3: ground-truth (expected_technical_band) validation ----------------

def _vrow_nolabel(pid, reg, tech):
    return {"pair_id": pid, "register": reg, "technical_band": tech}   # no expected_technical_band key


def test_valid_labelled_records_counted_for_accuracy():
    rows = [_vrow("p1", "plain", "Solid", "Solid"), _vrow("p1", "advanced", "Solid", "Solid")]
    r = fairness_report.report(rows)
    assert r["rows_labelled"] == 2 and r["rows_unlabelled"] == 0
    assert r["technical_accuracy_on_scored"] == 1.0
    assert r["accuracy_basis"] == "labelled, non-abstained rows only"


def test_missing_ground_truth_is_unlabelled_not_invalid_and_excluded_from_accuracy():
    rows = [_vrow_nolabel("p1", "plain", "Solid"), _vrow_nolabel("p1", "advanced", "Solid")]
    r = fairness_report.report(rows)
    assert r["rows_invalid"] == 0                 # missing label is not a structural error
    assert r["rows_unlabelled"] == 2
    assert r["rows_labelled"] == 0
    assert r["technical_accuracy_on_scored"] is None   # no ground truth -> no accuracy claimed
    assert r["scored_fraction"] == 0.0
    # fairness gap still computes from the bands present
    assert r["pairs_scored"] == 1 and r["mean_fairness_gap"] == 0.0


def test_invalid_ground_truth_band_is_rejected():
    rows = [_vrow("p1", "plain", "Solid", "Amazing")]   # 'Amazing' is not a band
    r = fairness_report.report(rows)
    assert r["rows_invalid"] == 1
    assert any("expected_technical_band" in rsn for x in r["invalid_rows"] for rsn in x["reasons"])


def test_mixed_labelled_and_unlabelled_accuracy_excludes_unlabelled():
    rows = [
        _vrow("p1", "plain", "Solid", "Solid"),          # labelled, correct
        _vrow("p1", "advanced", "Weak", "Solid"),        # labelled, wrong
        _vrow_nolabel("p2", "plain", "Strong"),          # unlabelled -> excluded from accuracy
        _vrow_nolabel("p2", "advanced", "Strong"),       # unlabelled -> excluded
    ]
    r = fairness_report.report(rows)
    assert r["rows_labelled"] == 2 and r["rows_unlabelled"] == 2
    assert r["technical_accuracy_on_scored"] == 0.5      # 1 of 2 labelled rows correct; unlabelled ignored


# ---------------- P1: fairness report transparency about abstention ----------------

def _row(pid, reg, tech, expected, abstained=False):
    return {"pair_id": pid, "register": reg, "technical_band": tech,
            "expected_technical_band": expected, "abstained_technical": abstained}


def test_fairness_report_counts_abstention_and_unscorable_pairs():
    rows = [
        _row("p1", "plain", "Solid", "Solid"),
        _row("p1", "advanced", None, "Solid", abstained=True),   # one side abstained -> unscorable
        _row("p2", "plain", "Strong", "Strong"),
        _row("p2", "advanced", "Strong", "Strong"),
    ]
    r = fairness_report.report(rows)
    assert r["total_pairs"] == 2
    assert r["pairs_scored"] == 1
    assert r["unscorable_pairs_due_to_abstention"] == 1
    assert r["rows_abstained"] == 1
    assert 0.0 < r["abstention_rate"] < 1.0
    # gap computed only over the scorable pair
    assert r["mean_fairness_gap"] == 0.0


def test_fairness_report_accuracy_flagged_nonrepresentative_when_mostly_abstained():
    rows = [
        _row("p1", "plain", None, "Solid", abstained=True),
        _row("p1", "advanced", None, "Solid", abstained=True),
        _row("p2", "plain", "Strong", "Strong"),
        _row("p2", "advanced", None, "Strong", abstained=True),
    ]
    r = fairness_report.report(rows)
    assert r["scored_fraction"] < 0.5
    assert r["accuracy_representative"] is False
