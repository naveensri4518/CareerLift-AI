"""Phase 3 — Technical Assessment Engine tests. No AWS/model; deterministic.

Covers: bank validation, selection, option randomization, grading (single/multi/tf, correct/incorrect/
unanswered), manual + auto (timeout) submission, duplicate-submit prevention, persistence/restoration,
auth, ownership isolation, answer-key protection, Phase 0 integration, and history.
"""
from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from agent import assessment_bank, assessment_eval


@pytest.fixture()
def client(temp_db, monkeypatch):
    monkeypatch.setenv("CAREERLIFT_MODEL_MODE", "mock")
    import api.main as main
    return TestClient(main.app)


def _reg(client):
    b = client.post("/register", json={}).json()
    return b["student_id"], b["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


# ---- question bank validation ----

def test_bank_has_all_categories_and_difficulties():
    stats = assessment_bank.bank_stats()
    assert stats["total"] >= 120
    # every one of the 12 categories is represented
    for cat in assessment_bank.CATEGORIES:
        assert stats["by_category"].get(cat, 0) >= 1, f"missing category {cat}"
    for diff in assessment_bank.DIFFICULTIES:
        assert stats["by_difficulty"].get(diff, 0) >= 1
    for typ in ("single", "multi", "tf"):
        assert stats["by_type"].get(typ, 0) >= 1


def test_bank_questions_are_well_formed_and_unique():
    seen = set()
    for q in assessment_bank.all_questions():
        assert q["id"] not in seen, f"duplicate id {q['id']}"
        seen.add(q["id"])
        assert q["concept_ids"], f"{q['id']} has no concept_ids"
        if q["type"] == "single":
            assert len(q["correct_options"]) == 1, f"{q['id']} single must have exactly one correct"
            opt_ids = {o["id"] for o in q["options"]}
            assert set(q["correct_options"]) <= opt_ids
        elif q["type"] == "multi":
            assert len(q["correct_options"]) >= 1
            opt_ids = {o["id"] for o in q["options"]}
            assert set(q["correct_options"]) <= opt_ids
        elif q["type"] == "tf":
            assert isinstance(q["correct_bool"], bool)


def test_concept_ids_resolve_against_taxonomy():
    from agent import fairscore
    valid = set(fairscore.concept_ids()) | set(assessment_bank.assessment_concept_ids())
    for q in assessment_bank.all_questions():
        for cid in q["concept_ids"]:
            assert cid in valid, f"{q['id']} references unknown concept {cid}"


# ---- selection + randomization ----

def test_selection_is_seed_reproducible_and_filtered():
    a = assessment_bank.select_questions("python", "mixed", 5, seed=42)
    b = assessment_bank.select_questions("python", "mixed", 5, seed=42)
    assert a == b                      # same seed -> identical set/order
    for qid in a:
        assert assessment_bank.get_question(qid)["category"] == "python"


def test_option_order_is_a_permutation():
    q = next(x for x in assessment_bank.all_questions() if x["type"] in ("single", "multi"))
    order = assessment_bank.option_order(q, seed=7)
    assert sorted(order) == sorted(o["id"] for o in q["options"])


# ---- deterministic grading ----

def test_grade_single_correct_and_incorrect():
    q = {"id": "X", "type": "single", "category": "c", "difficulty": "beginner", "marks": 1,
         "correct_options": ["a"]}
    assert assessment_eval._answer_is_correct(q, {"selected": ["a"]}) is True
    assert assessment_eval._answer_is_correct(q, {"selected": ["b"]}) is False
    assert assessment_eval._answer_is_correct(q, {"selected": ["a", "b"]}) is False  # extra selection
    assert assessment_eval._answer_is_correct(q, None) is False


def test_grade_multi_requires_exact_set():
    q = {"id": "Y", "type": "multi", "category": "c", "difficulty": "advanced", "marks": 2,
         "correct_options": ["a", "c"]}
    assert assessment_eval._answer_is_correct(q, {"selected": ["a", "c"]}) is True
    assert assessment_eval._answer_is_correct(q, {"selected": ["a"]}) is False          # partial
    assert assessment_eval._answer_is_correct(q, {"selected": ["a", "c", "d"]}) is False # extra
    assert assessment_eval._answer_is_correct(q, {"selected": ["c", "a"]}) is True       # order-independent


def test_grade_tf_exact_match():
    q = {"id": "Z", "type": "tf", "category": "c", "difficulty": "beginner", "marks": 1,
         "correct_bool": True}
    assert assessment_eval._answer_is_correct(q, {"bool": True}) is True
    assert assessment_eval._answer_is_correct(q, {"bool": False}) is False
    assert assessment_eval._answer_is_correct(q, {"bool": None}) is False


# ---- API lifecycle ----

def _start(client, tok, **over):
    body = {"category": "python", "difficulty": "mixed", "num_questions": 10, "duration_min": 20}
    body.update(over)
    return client.post("/assessment/attempts", json=body, headers=_auth(tok))


def test_catalog_requires_auth(client):
    assert client.get("/assessment/catalog").status_code == 401


def test_catalog_lists_12_categories(client):
    _sid, tok = _reg(client)
    cat = client.get("/assessment/catalog", headers=_auth(tok)).json()
    ids = {c["id"] for c in cat["categories"]}
    assert "mixed" in ids and len(ids - {"mixed"}) == 12
    assert cat["bank_stats"]["total"] >= 120


def test_start_attempt_hides_answer_keys(client):
    _sid, tok = _reg(client)
    r = _start(client, tok)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "in_progress"
    assert len(body["questions"]) == 10
    for q in body["questions"]:
        assert "correct_options" not in q and "correct_bool" not in q and "explanation" not in q
    assert body["remaining_sec"] > 0


def test_invalid_config_rejected(client):
    _sid, tok = _reg(client)
    assert _start(client, tok, num_questions=7).status_code == 400
    assert _start(client, tok, duration_min=15).status_code == 400
    assert _start(client, tok, category="banana").status_code == 422   # pydantic Literal


def test_save_and_restore_answers(client):
    _sid, tok = _reg(client)
    att = _start(client, tok).json()
    aid = att["attempt_id"]
    qid = att["questions"][0]["id"]
    qtype = att["questions"][0]["type"]
    ans = {"bool": True} if qtype == "tf" else {"selected": [att["questions"][0]["options"][0]["id"]]}
    r = client.post(f"/assessment/attempts/{aid}/answers", json={"answers": {qid: ans}}, headers=_auth(tok))
    assert r.status_code == 200 and r.json()["answered"] == 1
    # restore: GET returns the saved draft, still in progress
    got = client.get(f"/assessment/attempts/{aid}", headers=_auth(tok)).json()
    assert got["status"] == "in_progress"
    assert qid in got["answers"]


def test_manual_submit_grades_and_is_idempotent(client):
    _sid, tok = _reg(client)
    att = _start(client, tok, num_questions=10).json()
    aid = att["attempt_id"]
    # answer everything correctly using the server's review endpoint would leak keys, so just submit blank
    sub = client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok))
    assert sub.status_code == 200
    body = sub.json()
    assert body["status"] == "submitted"
    assert body["result"]["max_score"] > 0
    assert body["result"]["unanswered"] == 10   # submitted blank
    # second submit is idempotent
    again = client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok)).json()
    assert again["already_submitted"] is True
    assert again["result"]["total_score"] == body["result"]["total_score"]


def test_cannot_answer_after_submit(client):
    _sid, tok = _reg(client)
    att = _start(client, tok).json()
    aid = att["attempt_id"]
    client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok))
    qid = att["questions"][0]["id"]
    r = client.post(f"/assessment/attempts/{aid}/answers",
                    json={"answers": {qid: {"bool": True}}}, headers=_auth(tok))
    assert r.status_code == 409


def test_timeout_auto_submits(client, monkeypatch):
    _sid, tok = _reg(client)
    att = _start(client, tok, duration_min=10).json()
    aid = att["attempt_id"]
    # advance the server clock past the deadline
    import api.routers.assessment as asmt
    real_now = asmt._now()
    future = real_now + dt.timedelta(minutes=11)
    monkeypatch.setattr(asmt, "_now", lambda: future)
    # any read of the attempt now finalizes it as timed_out
    got = client.get(f"/assessment/attempts/{aid}", headers=_auth(tok)).json()
    assert got["status"] == "timed_out"
    # result is available and submit is idempotent
    res = client.get(f"/assessment/attempts/{aid}/result", headers=_auth(tok)).json()
    assert res["status"] == "timed_out"


def test_result_exposes_answer_keys_only_after_submit(client):
    _sid, tok = _reg(client)
    att = _start(client, tok).json()
    aid = att["attempt_id"]
    # before submit: result endpoint 409s, questions carry no keys
    assert client.get(f"/assessment/attempts/{aid}/result", headers=_auth(tok)).status_code == 409
    client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok))
    res = client.get(f"/assessment/attempts/{aid}/result", headers=_auth(tok)).json()
    assert res["review"]
    # now keys ARE present in review
    first = res["review"][0]
    assert ("correct_options" in first) or ("correct_bool" in first)
    assert "explanation" in first


def test_cross_student_cannot_access_attempt(client):
    _a, tok_a = _reg(client)
    _b, tok_b = _reg(client)
    aid = _start(client, tok_a).json()["attempt_id"]
    assert client.get(f"/assessment/attempts/{aid}", headers=_auth(tok_b)).status_code == 403
    assert client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok_b)).status_code == 403
    assert client.get(f"/assessment/attempts/{aid}/result", headers=_auth(tok_b)).status_code == 403


def test_history_lists_attempts(client):
    sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok))
    hist = client.get("/assessment/attempts", headers=_auth(tok)).json()["attempts"]
    assert any(a["id"] == aid and a["status"] == "submitted" for a in hist)
    assert hist[0]["percentage"] is not None


# ---- Phase 0 integration (correct answers move mastery) ----

def test_correct_answers_feed_phase0_skills(client):
    """Grade a fully-correct attempt by reading keys server-side (test-only), then verify the concepts
    become tracked in the shared Phase 0 model."""
    sid, tok = _reg(client)
    att = _start(client, tok, category="python", difficulty="mixed", num_questions=10).json()
    aid = att["attempt_id"]
    # build correct answers from the server-owned bank (test harness may inspect keys; the API never leaks them)
    answers = {}
    for q in att["questions"]:
        full = assessment_bank.get_question(q["id"])
        if full["type"] == "tf":
            answers[q["id"]] = {"bool": bool(full["correct_bool"])}
        else:
            answers[q["id"]] = {"selected": list(full["correct_options"])}
    client.post(f"/assessment/attempts/{aid}/answers", json={"answers": answers}, headers=_auth(tok))
    body = client.post(f"/assessment/attempts/{aid}/submit", headers=_auth(tok)).json()
    assert body["result"]["correct"] == 10 and body["result"]["percentage"] == 100.0
    # Phase 0: concepts are now tracked and activity recorded
    skills = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()
    assert skills["summary"]["tracked"] >= 1
    act = client.get(f"/students/{sid}/activity", headers=_auth(tok)).json()
    assert sum(e["count"] for e in act["events"]) >= 1
