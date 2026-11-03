"""Phase 1 — Advanced Interview Studio. Mock-mode, no AWS. Covers session lifecycle, evaluation,
ownership, resume, and Phase 0 integration."""
import pytest
from fastapi.testclient import TestClient

from agent import interview_studio


# ---- unit: question-set builder ----

def test_build_question_set_technical_uses_real_concepts():
    qs = interview_studio.build_question_set("technical", 3, seed=1)
    assert len(qs) == 3
    assert all(q["category"] == "technical" for q in qs)
    assert any(q["expected_concepts"] for q in qs)   # technical questions carry concepts


def test_build_question_set_hr_has_no_concepts():
    qs = interview_studio.build_question_set("hr", 3, seed=1)
    assert all(q["expected_concepts"] == [] for q in qs)


def test_build_question_set_mixed_and_count_clamp():
    qs = interview_studio.build_question_set("mixed", 8, seed=2)
    assert len(qs) == 8
    cats = {q["category"] for q in qs}
    assert cats <= {"technical", "hr", "behavioral", "project"}


def test_build_question_set_unknown_category():
    with pytest.raises(ValueError):
        interview_studio.build_question_set("nope", 3)


def test_summarize_keeps_axes_separate():
    graded = [
        {"ordinal": 0, "category": "technical", "topic": "hashing", "expected_concepts": ["C-HASH-AVG"],
         "answer_text": "x", "eval": {"technical_band": "Strong", "communication_band": "Partial",
                                        "abstained_technical": False, "abstained_communication": False,
                                        "misconception_tags": []}},
    ]
    s = interview_studio.summarize_session("technical", graded)
    assert s["overall_technical_band"] == "Strong"
    assert s["overall_communication_band"] == "Partial"
    assert s["dimensions"]["technical_correctness"] == "Strong"
    assert s["dimensions"]["communication_clarity"] == "Partial"


# ---- API lifecycle ----

@pytest.fixture()
def client(temp_db, monkeypatch):
    # Force mock mode so no AWS/model call can happen.
    monkeypatch.setenv("CAREERLIFT_MODEL_MODE", "mock")
    import api.main as main
    return TestClient(main.app)


def _reg(client):
    b = client.post("/register", json={}).json()
    return b["student_id"], b["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_create_session_returns_questions_without_concepts(client):
    _sid, tok = _reg(client)
    r = client.post("/studio/sessions", json={"category": "technical", "num_questions": 3},
                    headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["num_questions"] == 3 and len(body["questions"]) == 3
    for q in body["questions"]:
        assert "question_id" in q and "text" in q
        assert "expected_concepts" not in q           # server-owned, never exposed


def test_create_session_requires_auth(client):
    assert client.post("/studio/sessions", json={"category": "hr"}).status_code == 401


def test_create_session_invalid_category(client):
    _sid, tok = _reg(client)
    r = client.post("/studio/sessions", json={"category": "banana"}, headers=_auth(tok))
    assert r.status_code == 422   # pydantic Literal rejects it


def test_save_resume_and_submit_flow(client):
    _sid, tok = _reg(client)
    created = client.post("/studio/sessions", json={"category": "mixed", "num_questions": 3},
                          headers=_auth(tok)).json()
    session_id = created["session_id"]
    qids = [q["question_id"] for q in created["questions"]]

    # save a draft to the first question
    r = client.post(f"/studio/sessions/{session_id}/answer",
                    json={"question_id": qids[0], "answer": "A hash map is O(1) on average, O(n) worst case."},
                    headers=_auth(tok))
    assert r.status_code == 200 and r.json()["saved"] is True

    # resume: GET returns the saved draft
    got = client.get(f"/studio/sessions/{session_id}", headers=_auth(tok)).json()
    first = next(q for q in got["questions"] if q["question_id"] == qids[0])
    assert "hash map" in first["answer"]
    assert got["status"] == "in_progress"

    # answer the rest, then submit
    for qid in qids[1:]:
        client.post(f"/studio/sessions/{session_id}/answer",
                    json={"question_id": qid, "answer": "I would approach it step by step, because planning helps."},
                    headers=_auth(tok))
    sub = client.post(f"/studio/sessions/{session_id}/submit", headers=_auth(tok))
    assert sub.status_code == 200
    ev = sub.json()["evaluation"]
    assert ev["questions_total"] == 3
    assert "overall_communication_band" in ev and "overall_technical_band" in ev
    assert sub.json()["mock"] is True             # honestly labelled as local demo


def test_submit_is_idempotent(client):
    _sid, tok = _reg(client)
    created = client.post("/studio/sessions", json={"category": "hr", "num_questions": 2},
                          headers=_auth(tok)).json()
    session_id = created["session_id"]
    first = client.post(f"/studio/sessions/{session_id}/submit", headers=_auth(tok)).json()
    second = client.post(f"/studio/sessions/{session_id}/submit", headers=_auth(tok)).json()
    assert second.get("already_submitted") is True
    assert first["evaluation"]["questions_total"] == second["evaluation"]["questions_total"]


def test_answer_after_submit_rejected(client):
    _sid, tok = _reg(client)
    created = client.post("/studio/sessions", json={"category": "hr", "num_questions": 2},
                          headers=_auth(tok)).json()
    session_id = created["session_id"]
    qid = created["questions"][0]["question_id"]
    client.post(f"/studio/sessions/{session_id}/submit", headers=_auth(tok))
    r = client.post(f"/studio/sessions/{session_id}/answer",
                    json={"question_id": qid, "answer": "late"}, headers=_auth(tok))
    assert r.status_code == 409


def test_cross_student_cannot_access_session(client):
    _a, tok_a = _reg(client)
    _b, tok_b = _reg(client)
    created = client.post("/studio/sessions", json={"category": "hr", "num_questions": 2},
                          headers=_auth(tok_a)).json()
    sid = created["session_id"]
    assert client.get(f"/studio/sessions/{sid}", headers=_auth(tok_b)).status_code == 403
    assert client.post(f"/studio/sessions/{sid}/submit", headers=_auth(tok_b)).status_code == 403


def test_technical_submit_feeds_phase0_skills(client):
    sid, tok = _reg(client)
    created = client.post("/studio/sessions", json={"category": "technical", "num_questions": 3},
                          headers=_auth(tok)).json()
    session_id = created["session_id"]
    # answer each technical question with a correct-sounding answer
    for q in created["questions"]:
        client.post(f"/studio/sessions/{session_id}/answer",
                    json={"question_id": q["question_id"],
                          "answer": "A hash table lookup is O(1) on average but O(n) in the worst case."},
                    headers=_auth(tok))
    client.post(f"/studio/sessions/{session_id}/submit", headers=_auth(tok))
    # Phase 0 skills should now have at least one tracked concept (integration intact)
    skills = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()
    assert skills["summary"]["tracked"] >= 1
