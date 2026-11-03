"""Offline fairness report: mean/max gap AND technical accuracy on paired rows. No model, no AWS."""
from agent import fairness_report


def _row(pair_id, register, tech, expected):
    return {"pair_id": pair_id, "register": register, "technical_band": tech,
            "expected_technical_band": expected}


def test_perfect_fairness_and_accuracy():
    rows = [
        _row("p1", "plain", "Strong", "Strong"),
        _row("p1", "advanced", "Strong", "Strong"),
        _row("p2", "plain", "Partial", "Partial"),
        _row("p2", "advanced", "Partial", "Partial"),
    ]
    r = fairness_report.report(rows)
    assert r["pairs_scored"] == 2
    assert r["mean_fairness_gap"] == 0.0
    assert r["max_fairness_gap"] == 0
    assert r["fairness_failures"] == []
    assert r["technical_accuracy_on_scored"] == 1.0
    assert r["scored_fraction"] == 1.0
    assert r["accuracy_representative"] is True


def test_fairness_failure_detected():
    rows = [
        _row("p1", "plain", "Weak", "Strong"),       # under-scored the plain-English version
        _row("p1", "advanced", "Strong", "Strong"),
    ]
    r = fairness_report.report(rows)
    assert r["max_fairness_gap"] == 3
    assert r["fairness_failures"] and r["fairness_failures"][0]["pair_id"] == "p1"
    # accuracy reported alongside: 1 of 2 rows matches the label
    assert r["technical_accuracy_on_scored"] == 0.5


def test_flattening_is_caught_by_accuracy():
    """A scorer that outputs one band for everything has gap 0 but poor accuracy."""
    rows = [
        _row("p1", "plain", "Partial", "Strong"),
        _row("p1", "advanced", "Partial", "Strong"),
        _row("p2", "plain", "Partial", "Weak"),
        _row("p2", "advanced", "Partial", "Weak"),
    ]
    r = fairness_report.report(rows)
    assert r["mean_fairness_gap"] == 0.0                   # looks "fair"
    assert r["technical_accuracy_on_scored"] == 0.0        # but is useless -> the guard catches it
