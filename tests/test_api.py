"""REST API integration tests via FastAPI TestClient. The Bedrock boundary (agent.app.run) is
monkeypatched, so NO model is ever called and NO AWS is touched. Auth uses the local bearer-token scheme
with SERVER-generated student ids (clients cannot choose or impersonate an id)."""
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
                    "misconception_tags": ["M-HASH-ALWAYS-O1"],
                    "abstained_technical": False, "abstained_communication": False,
                    "message": "Technical: Solid. Communication: Partial."}
        else:
            plan = {"technical_band": None, "communication_band": None,
                    "technical_evidence": [], "communication_evidence": [],
                    "misconception_tags": [], "abstained_technical": True,
                    "abstained_communication": True, "message": "abstained"}
        return {"plan": plan, "meta": {"path": "agent", "latency_ms": 1}}

    monkeypatch.setattr(main, "score_answer", fake_run)
    return TestClient(main.app)


def _register(client):
    """Register a new anonymous student. Returns (student_id, token), both from the server."""
    r = client.post("/register", json={})
    assert r.status_code == 200
    body = r.json()
    return body["student_id"], body["token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health_open(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


# ---------------- Fix 1: registration security ----------------

def test_register_without_student_id_succeeds(client):
    r = client.post("/register", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["student_id"].startswith("stu_")       # server-generated
    assert "only once" in body["note"].lower()


def test_register_ignores_client_supplied_student_id(client):
    """A client-supplied student_id must NOT become the identity (no impersonation)."""
    r1 = client.post("/register", json={"student_id": "victim", "display_name": "x"})
    assert r1.status_code == 200
    # the server ignores unknown fields and assigns its own id
    assert r1.json()["student_id"] != "victim"
    assert r1.json()["student_id"].startswith("stu_")


def test_two_independent_registrations_get_distinct_identities(client):
    a_id, a_tok = _register(client)
    b_id, b_tok = _register(client)
    assert a_id != b_id and a_tok != b_tok


def test_registration_cannot_attach_to_existing_student(client, temp_db):
    """Even if a student id already exists, a new registration never attaches to it."""
    from agent import db
    db.create_new_student("stu_existing", temp_db)
    a_id, _ = _register(client)
    b_id, _ = _register(client)
    assert a_id != "stu_existing" and b_id != "stu_existing"


# ---------------- authentication boundary ----------------

def test_unauthenticated_request_rejected(client):
    r = client.post("/interviews", json={"topic": "hashing"})
    assert r.status_code == 401


def test_invalid_token_rejected(client):
    r = client.post("/interviews", json={"topic": "hashing"}, headers=_auth("not-a-real-token"))
    assert r.status_code == 401


def test_malformed_auth_header_rejected(client):
    r = client.get("/students/stu_x/history", headers={"Authorization": "Token abc"})
    assert r.status_code == 401


def test_authenticated_happy_path(client):
    sid, token = _register(client)
    start = client.post("/interviews", json={"topic": "hashing"}, headers=_auth(token)).json()
    assert start["interview_id"] > 0 and start["concept_token"] == ["C-HASH-AVG"]
    r = client.post("/score", json={
        "interview_id": start["interview_id"], "question": start["question"],
        "answer": "A hash map is O(1) on average.", "concept_token": start["concept_token"],
    }, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["technical_band"] == "Solid"
    hist = client.get(f"/students/{sid}/history", headers=_auth(token)).json()
    assert len(hist) == 1
    mis = client.get(f"/students/{sid}/misconceptions", headers=_auth(token)).json()
    assert mis and mis[0]["tag"] == "M-HASH-ALWAYS-O1"


def test_cannot_read_another_students_history(client):
    a_id, t_a = _register(client)
    b_id, t_b = _register(client)
    # alice tries to read bob's history using her own (valid) token
    assert client.get(f"/students/{b_id}/history", headers=_auth(t_a)).status_code == 403
    # bob reading his own is fine
    assert client.get(f"/students/{b_id}/history", headers=_auth(t_b)).status_code == 200


def test_cannot_score_another_students_interview(client):
    owner_id, t_owner = _register(client)
    att_id, t_attacker = _register(client)
    start = client.post("/interviews", json={"topic": "hashing"}, headers=_auth(t_owner)).json()
    r = client.post("/score", json={
        "interview_id": start["interview_id"], "question": start["question"],
        "answer": "A hash map is O(1).", "concept_token": [],
    }, headers=_auth(t_attacker))
    assert r.status_code == 403


# ---------------- data-integrity (under auth) ----------------

def test_start_interview_bad_topic(client):
    _sid, token = _register(client)
    r = client.post("/interviews", json={"topic": "nope"}, headers=_auth(token))
    assert r.status_code == 400


def test_score_unknown_interview_404(client):
    _sid, token = _register(client)
    r = client.post("/score", json={
        "interview_id": 999999, "question": "anything", "answer": "A hash map is O(1).", "concept_token": [],
    }, headers=_auth(token))
    assert r.status_code == 404


def test_score_question_mismatch_409(client):
    _sid, token = _register(client)
    start = client.post("/interviews", json={"topic": "hashing"}, headers=_auth(token)).json()
    r = client.post("/score", json={
        "interview_id": start["interview_id"], "question": "a different question",
        "answer": "A hash map is O(1).", "concept_token": [],
    }, headers=_auth(token))
    assert r.status_code == 409


def test_score_rejects_pii_without_model(client):
    _sid, token = _register(client)
    start = client.post("/interviews", json={"topic": "hashing"}, headers=_auth(token)).json()
    r = client.post("/score", json={
        "interview_id": start["interview_id"], "question": start["question"],
        "answer": "my phone is 9876543210", "concept_token": start["concept_token"],
    }, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["abstained_technical"] is True
    assert "personal details" in r.json()["message"].lower()


def test_score_ignores_client_concept_token(client, monkeypatch):
    import api.main as main
    seen = {}

    def capture_run(case):
        seen["expected_concepts"] = case["expected_concepts"]
        return {"plan": {"technical_band": "Solid", "communication_band": "Solid",
                         "technical_evidence": [], "communication_evidence": [],
                         "misconception_tags": [], "abstained_technical": False,
                         "abstained_communication": False, "message": "ok"},
                "meta": {"path": "agent", "latency_ms": 1}}

    monkeypatch.setattr(main, "score_answer", capture_run)
    _sid, token = _register(client)
    start = client.post("/interviews", json={"topic": "hashing"}, headers=_auth(token)).json()
    client.post("/score", json={
        "interview_id": start["interview_id"], "question": start["question"],
        "answer": "A hash map is O(1).", "concept_token": ["C-SQL-INDEX", "C-FAKE"],
    }, headers=_auth(token))
    assert seen["expected_concepts"] == ["C-HASH-AVG"]


def test_token_not_stored_in_plaintext(temp_db):
    """Security: the plaintext token must never appear in the database; only its hash is stored."""
    from agent import db
    from api.auth import register_new_student, hash_token
    student_id, token = register_new_student(temp_db)
    with db.connect(temp_db) as c:
        rows = [dict(r) for r in c.execute("SELECT token_hash, student_id FROM auth_token").fetchall()]
    assert rows and rows[0]["student_id"] == student_id
    assert token not in [r["token_hash"] for r in rows]       # plaintext never stored
    assert rows[0]["token_hash"] == hash_token(token)          # only the hash is


def test_planner_endpoint(client):
    sid, token = _register(client)
    client.post("/interviews", json={"topic": "hashing"}, headers=_auth(token))
    r = client.get(f"/students/{sid}/next", headers=_auth(token))
    assert r.status_code == 200 and r.json()["concept_token"]
