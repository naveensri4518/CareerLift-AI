"""Phase 4 — System Design Academy tests. No AWS/model; deterministic.

Covers: scenario bank validation, answer-key protection, deterministic grading (components/connections/
decisions/trade-offs), invalid-connection rejection, attempt lifecycle (start/save/restore/submit),
duplicate-submit prevention, save-after-submit rejection, auth + ownership, and Phase 0 signal integration.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent import fairscore, sysdesign_bank, sysdesign_eval


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


# ---- scenario bank validation ----

def test_bank_has_scenarios_and_difficulties():
    stats = sysdesign_bank.bank_stats()
    assert stats["total"] >= 5
    for diff in ("beginner", "intermediate", "advanced"):
        assert stats["by_difficulty"].get(diff, 0) >= 1


def test_scenarios_are_well_formed_and_reference_valid_ids():
    valid_concepts = (set(fairscore.concept_ids())
                      | set(sysdesign_bank.sysdesign_concept_ids()))
    seen = set()
    for s in sysdesign_bank.all_scenarios():
        assert s["id"] not in seen
        seen.add(s["id"])
        palette = set(s["palette"])
        r = s["rubric"]
        # required/recommended components must be in the palette
        for c in r.get("required_components", []) + r.get("recommended_components", []):
            assert c in palette, f"{s['id']}: component {c} not in palette"
        # required connections reference palette ids
        for conn in r.get("required_connections", []):
            assert conn[0] in palette and conn[1] in palette
        # decision prompts: acceptable/expected options exist; concept ids resolve
        prompts = {dp["id"]: dp for dp in s["decision_prompts"]}
        for did, spec in r["decisions"].items():
            assert did in prompts, f"{s['id']}: rubric decision {did} has no prompt"
            opt_ids = {o["id"] for o in prompts[did]["options"]}
            for o in spec.get("acceptable", []) + spec.get("expected", []):
                assert o in opt_ids, f"{s['id']}: decision {did} expects unknown option {o}"
        for dp in s["decision_prompts"]:
            assert dp["concept_id"] in valid_concepts, f"{s['id']}: unknown concept {dp['concept_id']}"
        for dim_cid in r["concept_dimension"].values():
            assert dim_cid in valid_concepts


# ---- deterministic grading (unit-level) ----

def _perfect_design(scenario: dict) -> dict:
    r = scenario["rubric"]
    comps = list(set(r["required_components"] + r.get("recommended_components", [])))
    conns = [list(c) for c in r["required_connections"]] + [list(c) for c in r.get("recommended_connections", [])]
    decisions = {}
    for did, spec in r["decisions"].items():
        chosen = spec.get("acceptable", [None])[:1] if "acceptable" in spec else list(spec.get("expected", []))
        decisions[did] = {"selected": chosen}
    return {"components": comps, "connections": conns, "decisions": decisions}


def test_perfect_design_scores_full():
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    res = sysdesign_eval.grade(s, _perfect_design(s))
    assert res["percentage"] == 100.0 and res["grade"] == "A"
    assert not res["missing_components"] and not res["missing_connections"]


def test_empty_design_scores_low_and_lists_missing():
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    res = sysdesign_eval.grade(s, {"components": [], "connections": [], "decisions": {}})
    assert res["percentage"] < 50
    assert set(res["missing_components"]) == set(s["rubric"]["required_components"])


def test_multiselect_requires_exact_set():
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    # read_scaling expects exactly {cache, read_replicas}; a partial selection scores 0 on that dimension
    design = _perfect_design(s)
    design["decisions"]["read_scaling"] = {"selected": ["cache"]}   # missing read_replicas
    res = sysdesign_eval.grade(s, design)
    assert res["dimensions"]["scalability"]["score"] == 0.0


def test_single_decision_rejects_wrong_option():
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    design = _perfect_design(s)
    design["decisions"]["datastore"] = {"selected": ["file"]}       # not acceptable
    res = sysdesign_eval.grade(s, design)
    assert res["dimensions"]["data"]["score"] == 0.0


def test_decision_never_clobbers_structural_components_dimension():
    """Regression: a decision prompt must never overwrite the structural `components` dimension.

    SD-URL-SHORTENER's `code_gen` decision used to resolve to the `components` key and silently
    discard the real required-components match. The grade must keep BOTH: the structural components
    score (reflecting the diagram) AND the code_gen decision score (under its own key)."""
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    # A design with the RIGHT components/connections but a WRONG code_gen choice.
    design = _perfect_design(s)
    design["decisions"]["code_gen"] = {"selected": ["user_choice"]}  # not acceptable
    res = sysdesign_eval.grade(s, design)
    dims = res["dimensions"]
    # structural components dimension survives and reflects the (correct) component selection
    assert "components" in dims
    assert dims["components"]["score"] == 1.0
    assert "matched" in dims["components"]  # structural payload, not a decision payload
    # the code_gen decision is scored under its OWN namespaced key, and it is wrong -> 0
    assert "decision:code_gen" in dims
    assert dims["decision:code_gen"]["score"] == 0.0
    assert dims["decision:code_gen"]["base_dimension"] == "data"


def test_two_decisions_on_same_base_dimension_are_both_scored():
    """Regression: `datastore` and `code_gen` both map to the `data` base dimension. Both must be
    scored independently (neither silently dropped)."""
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    design = _perfect_design(s)
    res = sysdesign_eval.grade(s, design)
    data_dims = [d for d in res["dimensions"].values() if d.get("base_dimension") == "data"
                 or res["dimensions"].get("data") is d]
    decision_ids = {d.get("decision_id") for d in res["dimensions"].values() if "decision_id" in d}
    assert "datastore" in decision_ids and "code_gen" in decision_ids


def test_validate_design_rejects_unknown_ids():
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    errs = sysdesign_eval.validate_design(s, {"components": ["not_a_component"],
                                              "connections": [["app_server", "ghost"]],
                                              "decisions": {"datastore": {"selected": ["bogus"]}}})
    assert any("unknown component" in e for e in errs)
    assert any("unknown component 'ghost'" in e for e in errs)
    assert any("unknown option" in e for e in errs)


# ---- API: catalog + answer-key protection ----

def test_scenarios_require_auth(client):
    assert client.get("/sysdesign/scenarios").status_code == 401


def test_list_scenarios(client):
    _sid, tok = _reg(client)
    body = client.get("/sysdesign/scenarios", headers=_auth(tok)).json()
    assert len(body["scenarios"]) >= 5
    for s in body["scenarios"]:
        assert "rubric" not in s and s["attempted"] is False


def test_scenario_brief_hides_rubric(client):
    _sid, tok = _reg(client)
    body = client.get("/sysdesign/scenarios/SD-URL-SHORTENER", headers=_auth(tok)).json()
    assert "rubric" not in body and "feedback" not in body
    assert body["palette"] and body["decision_prompts"]
    import json as _json
    raw = _json.dumps(body)
    # acceptable-option ids must not leak; check a known rubric answer is absent as a key marker
    assert "acceptable" not in raw and "expected" not in raw


def test_unknown_scenario_404(client):
    _sid, tok = _reg(client)
    assert client.get("/sysdesign/scenarios/NOPE", headers=_auth(tok)).status_code == 404


# ---- API: lifecycle ----

def _start(client, tok, scenario_id="SD-URL-SHORTENER"):
    return client.post("/sysdesign/attempts", json={"scenario_id": scenario_id}, headers=_auth(tok))


def test_start_attempt_returns_brief_without_keys(client):
    _sid, tok = _reg(client)
    r = _start(client, tok)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "in_progress" and body["brief"]["palette"]
    assert "rubric" not in body["brief"]


def test_save_restore_and_submit_flow(client):
    sid, tok = _reg(client)
    att = _start(client, tok).json()
    aid = att["attempt_id"]
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    design = _perfect_design(s)
    save = client.post(f"/sysdesign/attempts/{aid}/design", json={
        "components": design["components"],
        "connections": design["connections"],
        "decisions": design["decisions"],
    }, headers=_auth(tok))
    assert save.status_code == 200 and save.json()["components"] >= 2
    # restore
    got = client.get(f"/sysdesign/attempts/{aid}", headers=_auth(tok)).json()
    assert got["status"] == "in_progress" and set(got["design"]["components"]) == set(design["components"])
    # submit -> graded
    sub = client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok)).json()
    assert sub["status"] == "submitted" and sub["result"]["percentage"] == 100.0


def test_invalid_connection_rejected_on_save(client):
    _sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    r = client.post(f"/sysdesign/attempts/{aid}/design", json={
        "components": ["app_server"], "connections": [["app_server", "ghost"]], "decisions": {},
    }, headers=_auth(tok))
    assert r.status_code == 400


def test_duplicate_submit_is_idempotent(client):
    _sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    first = client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok)).json()
    second = client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok)).json()
    assert second["already_submitted"] is True
    assert second["result"]["percentage"] == first["result"]["percentage"]


def test_cannot_save_after_submit(client):
    _sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok))
    r = client.post(f"/sysdesign/attempts/{aid}/design", json={"components": ["app_server"], "connections": [], "decisions": {}}, headers=_auth(tok))
    assert r.status_code == 409


def test_result_exposes_expected_only_after_submit(client):
    _sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    assert client.get(f"/sysdesign/attempts/{aid}/result", headers=_auth(tok)).status_code == 409
    client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok))
    res = client.get(f"/sysdesign/attempts/{aid}/result", headers=_auth(tok)).json()
    assert res["expected"]["required_components"]
    assert "dimensions" in res["result"]


def test_cross_student_cannot_access_attempt(client):
    _a, tok_a = _reg(client)
    _b, tok_b = _reg(client)
    aid = _start(client, tok_a).json()["attempt_id"]
    assert client.get(f"/sysdesign/attempts/{aid}", headers=_auth(tok_b)).status_code == 403
    assert client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok_b)).status_code == 403
    assert client.get(f"/sysdesign/attempts/{aid}/result", headers=_auth(tok_b)).status_code == 403


def test_history_lists_attempts(client):
    sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok))
    hist = client.get("/sysdesign/attempts", headers=_auth(tok)).json()["attempts"]
    assert any(a["id"] == aid and a["status"] == "submitted" for a in hist)
    assert hist[0]["percentage"] is not None


# ---- Phase 0 integration ----

def test_strong_design_feeds_phase0_skills(client):
    sid, tok = _reg(client)
    aid = _start(client, tok).json()["attempt_id"]
    s = sysdesign_bank.get_scenario("SD-URL-SHORTENER")
    design = _perfect_design(s)
    client.post(f"/sysdesign/attempts/{aid}/design", json={
        "components": design["components"], "connections": design["connections"], "decisions": design["decisions"],
    }, headers=_auth(tok))
    client.post(f"/sysdesign/attempts/{aid}/submit", headers=_auth(tok))
    skills = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()
    assert skills["summary"]["tracked"] >= 1
    tracked = {c["concept_id"] for c in skills["concepts"]}
    assert any(cid.startswith("SD-") for cid in tracked)
    act = client.get(f"/students/{sid}/activity", headers=_auth(tok)).json()
    assert sum(e["count"] for e in act["events"]) >= 1
