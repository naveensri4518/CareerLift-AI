"""Phase 0 API: learning + dashboard routers, ownership, single /next, no confidence, zero AWS."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(temp_db, monkeypatch):
    import api.main as main

    def fake_run(case):
        answer = case["text"]
        if "O(1)" in answer:
            plan = {"technical_band": "Solid", "communication_band": "Partial",
                    "technical_evidence": ["O(1)"], "communication_evidence": [],
                    "misconception_tags": [], "abstained_technical": False,
                    "abstained_communication": False, "message": "ok"}
        else:
            plan = {"technical_band": None, "communication_band": None,
                    "technical_evidence": [], "communication_evidence": [],
                    "misconception_tags": ["M-HASH-ALWAYS-O1"], "abstained_technical": False,
                    "abstained_communication": False, "message": "ok"}
        return {"plan": plan, "meta": {"path": "agent", "model_mode": "mock", "latency_ms": 1}}

    monkeypatch.setattr(main, "score_answer", fake_run)
    return TestClient(main.app)


def _reg(client):
    b = client.post("/register", json={}).json()
    return b["student_id"], b["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_skills_requires_auth(client):
    assert client.get("/students/stu_x/skills").status_code == 401


def test_skills_cross_student_forbidden(client):
    a_id, a_tok = _reg(client)
    b_id, b_tok = _reg(client)
    assert client.get(f"/students/{b_id}/skills", headers=_auth(a_tok)).status_code == 403
    assert client.get(f"/students/{b_id}/skills", headers=_auth(b_tok)).status_code == 200


def test_skills_response_has_no_confidence(client):
    sid, tok = _reg(client)
    body = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()
    assert "concepts" in body and "summary" in body
    for c in body["concepts"]:
        assert "confidence" not in c            # spec §6.4/§8


def test_score_emits_signals_and_activity(client):
    sid, tok = _reg(client)
    start = client.post("/interviews", json={"topic": "hashing"}, headers=_auth(tok)).json()
    # answer that triggers a misconception tag in the fake scorer
    r = client.post("/score", json={
        "interview_id": start["interview_id"], "question": start["question"],
        "answer": "it is slow sometimes", "concept_token": [],
    }, headers=_auth(tok))
    assert r.status_code == 200
    # skills now reflect the misconception; activity recorded
    skills = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()
    assert skills["summary"]["open_misconceptions"] >= 1
    overview = client.get(f"/students/{sid}/overview", headers=_auth(tok)).json()
    assert overview["answers_scored"] >= 1


def test_overview_and_activity_owner_only(client):
    a_id, a_tok = _reg(client)
    b_id, b_tok = _reg(client)
    assert client.get(f"/students/{b_id}/overview", headers=_auth(a_tok)).status_code == 403
    assert client.get(f"/students/{b_id}/activity", headers=_auth(b_tok)).status_code == 200


def test_recommendations_endpoint(client):
    sid, tok = _reg(client)
    r = client.get(f"/students/{sid}/recommendations", headers=_auth(tok))
    assert r.status_code == 200 and "recommendations" in r.json()


def test_single_next_route():
    # exactly one GET route answers /students/{student_id}/next after routers are included
    import api.main as main
    matches = [
        route for route in main.app.routes
        if getattr(route, "path", None) == "/students/{student_id}/next"
        and "GET" in getattr(route, "methods", set())
    ]
    assert len(matches) == 1


def test_next_response_schema_still_four_fields(client):
    sid, tok = _reg(client)
    r = client.get(f"/students/{sid}/next", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"topic", "question", "reason", "concept_token"}
    assert "recommendation" not in body
