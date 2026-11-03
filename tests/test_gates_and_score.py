"""Input gate (PII) and the score.py harness-contract mapping. No model, no AWS."""
from agent import gates, score
from agent.models import ScoreResult


def test_pii_detection():
    assert gates.find_pii("call me on 9876543210")
    assert gates.find_pii("reach me at test@example.com")
    assert gates.find_pii("my aadhaar is 1234 5678 9012")
    assert not gates.find_pii("A hash map is O(1) on average, O(n) worst case")


def _case(**over):
    base = {"id": "c1", "lang": "en", "job": "sde", "text": "A hash map gives O(1) on average.",
            "pair_id": "p1", "register": "plain",
            "expected": {"escalation": "none", "technical_band": "Strong", "communication_band": "Solid"}}
    base.update(over)
    return base


def _out(**plan):
    p = ScoreResult(**plan).model_dump()
    return {"plan": p, "meta": {"path": "agent", "latency_ms": 5}}


def test_score_returns_harness_keys():
    row = score.score(_case(), _out(technical_band="Strong", communication_band="Solid",
                                    technical_evidence=["O(1) on average"]))
    for k in ("emergency_case", "escalated", "risk_correct", "complete", "citations", "citations_valid", "unsafe"):
        assert k in row
    assert row["risk_correct"] is True
    assert row["complete"] == 1.0
    assert row["unsafe"] == []
    assert row["citations"] == 1


def test_score_flags_under_scoring_as_unsafe():
    row = score.score(_case(), _out(technical_band="Weak", communication_band="Solid"))
    assert row["unsafe"], "a Strong-labelled answer scored Weak must be unsafe"


def test_score_abstain_case():
    case = _case(expected={"escalation": "emergency", "technical_band": None, "communication_band": None})
    row = score.score(case, _out(technical_band=None, communication_band=None, abstained_technical=True,
                                 abstained_communication=True))
    assert row["emergency_case"] is True
    assert row["escalated"] is True       # correctly abstained
    assert row["risk_correct"] is True


def test_score_over_abstention_is_unsafe():
    row = score.score(_case(), _out(technical_band=None, abstained_technical=True))
    assert any("over-abstain" in u for u in row["unsafe"])
