"""Phase 2 — Secure Coding Arena tests.

These tests do NOT require Docker. The sandbox (agent.coding_exec) is monkeypatched so the deterministic
evaluation + verdict logic, the API lifecycle, auth/isolation, hidden-test protection, and Phase 0
integration are all exercised without executing real code. A separate live harness
(scripts/verify_sandbox.py) covers the real Docker path when a daemon is available.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent import coding_eval, coding_exec, coding_problems


@pytest.fixture()
def client(temp_db, monkeypatch):
    monkeypatch.setenv("CAREERLIFT_MODEL_MODE", "mock")  # no AWS/model anywhere
    import api.main as main
    return TestClient(main.app)


def _reg(client):
    b = client.post("/register", json={}).json()
    return b["student_id"], b["token"]


def _auth(t):
    return {"Authorization": f"Bearer {t}"}


# ---- fake sandbox: map (stdin) -> ExecResult so we control verdicts deterministically ----

def _fake_exec(monkeypatch, *, compile_ok=True, responder=None, available=True):
    """Patch coding_exec so no Docker is needed.
    responder(stdin) -> ExecResult for each run; defaults to echoing nothing (WRONG ANSWER)."""
    def _preflight(timeout_s=8.0):
        return (True, "ok") if available else (False, "Docker daemon is not running or not reachable.")
    monkeypatch.setattr(coding_exec, "preflight", _preflight)

    def _ensure():
        if not available:
            raise coding_exec.SandboxUnavailableError("The secure code sandbox is unavailable, so code cannot be executed.")
    monkeypatch.setattr(coding_exec, "ensure_available", _ensure)

    def _compile(language, source, *, memory_mb, time_ms):
        _ensure()  # mirror the real guard: fail closed when the sandbox is unavailable
        if language == "python":
            return None
        return coding_exec.CompileOutcome(ok=compile_ok, stderr="" if compile_ok else "error: boom", duration_ms=5)
    monkeypatch.setattr(coding_exec, "compile_source", _compile)

    def _run_once(language, source, *, stdin, time_ms, memory_mb, precompiled_ws=None):
        _ensure()  # mirror the real guard
        if responder is not None:
            return responder(stdin)
        return coding_exec.ExecResult(exit_code=0, stdout="", stderr="", duration_ms=1,
                                      timed_out=False, oom_killed=False)
    monkeypatch.setattr(coding_exec, "run_once", _run_once)


def _correct_sum_two(stdin):
    a, b = (int(x) for x in stdin.split())
    return coding_exec.ExecResult(exit_code=0, stdout=f"{a + b}\n", stderr="", duration_ms=3,
                                  timed_out=False, oom_killed=False)


# ---- catalogue + auth ----

def test_problems_require_auth(client):
    assert client.get("/coding/problems").status_code == 401


def test_list_problems(client):
    _sid, tok = _reg(client)
    r = client.get("/coding/problems", headers=_auth(tok))
    assert r.status_code == 200
    probs = r.json()["problems"]
    assert len(probs) == len(coding_problems.all_problems())
    difficulties = {p["difficulty"] for p in probs}
    assert {"beginner", "intermediate", "advanced"} <= difficulties
    for p in probs:
        assert p["solved"] is False  # fresh student


def test_problem_detail_hides_hidden_tests(client):
    _sid, tok = _reg(client)
    r = client.get("/coding/problems/P-BINARY-SEARCH", headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert "public_tests" in body and len(body["public_tests"]) >= 1
    assert "hidden_tests" not in body                  # never exposed
    assert body["hidden_test_count"] >= 1              # count only
    # and no hidden stdin/stdout anywhere in the serialized payload
    import json as _json
    raw = _json.dumps(body)
    p = coding_problems.get_problem("P-BINARY-SEARCH")
    for h in p["hidden_tests"]:
        assert h["stdin"].strip() not in raw


def test_unknown_problem_404(client):
    _sid, tok = _reg(client)
    assert client.get("/coding/problems/NOPE", headers=_auth(tok)).status_code == 404


def test_languages_listed(client):
    _sid, tok = _reg(client)
    langs = {l["id"] for l in client.get("/coding/languages", headers=_auth(tok)).json()["languages"]}
    assert langs == {"python", "cpp", "java"}


# ---- sandbox status / fail-closed ----

def test_status_reports_unavailable(client, monkeypatch):
    _fake_exec(monkeypatch, available=False)
    _sid, tok = _reg(client)
    body = client.get("/coding/status", headers=_auth(tok)).json()
    assert body["sandbox_available"] is False
    assert "Docker" in body["reason"]


def test_submit_fails_closed_when_sandbox_unavailable(client, monkeypatch):
    _fake_exec(monkeypatch, available=False)
    _sid, tok = _reg(client)
    r = client.post("/coding/submit",
                    json={"problem_id": "P-SUM-TWO", "language": "python", "source": "x=1"},
                    headers=_auth(tok))
    assert r.status_code == 503                         # NO insecure fallback
    # and nothing was persisted
    assert client.get("/coding/submissions", headers=_auth(tok)).json()["submissions"] == []


# ---- verdicts ----

def test_accepted_passes_all_tests(client, monkeypatch):
    _fake_exec(monkeypatch, responder=_correct_sum_two)
    _sid, tok = _reg(client)
    r = client.post("/coding/submit",
                    json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(sum(map(int,input().split())))"},
                    headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"] == "ACCEPTED"
    p = coding_problems.get_problem("P-SUM-TWO")
    total = len(p["public_tests"]) + len(p["hidden_tests"])
    assert body["tests_passed"] == total and body["tests_failed"] == 0


def test_wrong_answer(client, monkeypatch):
    # always outputs 0 regardless of input
    def _wrong(stdin):
        return coding_exec.ExecResult(exit_code=0, stdout="0\n", stderr="", duration_ms=1,
                                      timed_out=False, oom_killed=False)
    _fake_exec(monkeypatch, responder=_wrong)
    _sid, tok = _reg(client)
    body = client.post("/coding/submit",
                       json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(0)"},
                       headers=_auth(tok)).json()
    assert body["verdict"] == "WRONG ANSWER"
    assert body["tests_failed"] >= 1


def test_compilation_error(client, monkeypatch):
    _fake_exec(monkeypatch, compile_ok=False)
    _sid, tok = _reg(client)
    body = client.post("/coding/submit",
                       json={"problem_id": "P-SUM-TWO", "language": "cpp", "source": "int main(){"},
                       headers=_auth(tok)).json()
    assert body["verdict"] == "COMPILATION ERROR"
    assert body["compiled"] is False and body["compile_error"]


def test_time_limit_exceeded(client, monkeypatch):
    def _tle(stdin):
        return coding_exec.ExecResult(exit_code=124, stdout="", stderr="", duration_ms=9999,
                                      timed_out=True, oom_killed=False)
    _fake_exec(monkeypatch, responder=_tle)
    _sid, tok = _reg(client)
    body = client.post("/coding/submit",
                       json={"problem_id": "P-SUM-TWO", "language": "python", "source": "while True: pass"},
                       headers=_auth(tok)).json()
    assert body["verdict"] == "TIME LIMIT EXCEEDED"


def test_runtime_error(client, monkeypatch):
    def _re(stdin):
        return coding_exec.ExecResult(exit_code=1, stdout="", stderr="Traceback...", duration_ms=2,
                                      timed_out=False, oom_killed=False)
    _fake_exec(monkeypatch, responder=_re)
    _sid, tok = _reg(client)
    body = client.post("/coding/submit",
                       json={"problem_id": "P-SUM-TWO", "language": "python", "source": "raise SystemExit(1)"},
                       headers=_auth(tok)).json()
    assert body["verdict"] == "RUNTIME ERROR"


# ---- run (public only) never reveals hidden tests ----

def test_run_only_uses_public_tests(client, monkeypatch):
    seen_inputs = []

    def _rec(stdin):
        seen_inputs.append(stdin)
        return _correct_sum_two(stdin)
    _fake_exec(monkeypatch, responder=_rec)
    _sid, tok = _reg(client)
    r = client.post("/coding/run",
                    json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(1)"},
                    headers=_auth(tok))
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "run"
    p = coding_problems.get_problem("P-SUM-TWO")
    # Only public test inputs were ever executed.
    assert len(seen_inputs) == len(p["public_tests"])
    hidden_inputs = {h["stdin"] for h in p["hidden_tests"]}
    assert not (set(seen_inputs) & hidden_inputs)
    # run results carry only public cases
    assert len(body["public_results"]) == len(p["public_tests"])


# ---- history + cross-user isolation ----

def test_submission_history_and_ownership(client, monkeypatch):
    _fake_exec(monkeypatch, responder=_correct_sum_two)
    sid_a, tok_a = _reg(client)
    _sid_b, tok_b = _reg(client)
    sub = client.post("/coding/submit",
                      json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(1)"},
                      headers=_auth(tok_a)).json()
    sub_id = sub["submission_id"]

    # A sees it
    hist_a = client.get("/coding/submissions", headers=_auth(tok_a)).json()["submissions"]
    assert any(s["id"] == sub_id for s in hist_a)
    assert client.get(f"/coding/submissions/{sub_id}", headers=_auth(tok_a)).status_code == 200

    # B cannot read A's submission, and B's history is empty
    assert client.get(f"/coding/submissions/{sub_id}", headers=_auth(tok_b)).status_code == 403
    assert client.get("/coding/submissions", headers=_auth(tok_b)).json()["submissions"] == []


def test_solved_badge_after_accept(client, monkeypatch):
    _fake_exec(monkeypatch, responder=_correct_sum_two)
    _sid, tok = _reg(client)
    client.post("/coding/submit",
                json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(1)"},
                headers=_auth(tok))
    probs = {p["id"]: p for p in client.get("/coding/problems", headers=_auth(tok)).json()["problems"]}
    assert probs["P-SUM-TWO"]["solved"] is True


# ---- Phase 0 integration ----

def test_accepted_submission_feeds_phase0_skills(client, monkeypatch):
    _fake_exec(monkeypatch, responder=_correct_sum_two)
    sid, tok = _reg(client)
    # P-SUM-TWO maps to concept C-BIGO-DEF
    before = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()["summary"]["tracked"]
    client.post("/coding/submit",
                json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(1)"},
                headers=_auth(tok))
    after = client.get(f"/students/{sid}/skills", headers=_auth(tok)).json()
    assert after["summary"]["tracked"] >= max(1, before)
    assert any(c["concept_id"] == "C-BIGO-DEF" for c in after["concepts"])


def test_accepted_submission_records_activity(client, monkeypatch):
    _fake_exec(monkeypatch, responder=_correct_sum_two)
    sid, tok = _reg(client)
    client.post("/coding/submit",
                json={"problem_id": "P-SUM-TWO", "language": "python", "source": "print(1)"},
                headers=_auth(tok))
    act = client.get(f"/students/{sid}/activity", headers=_auth(tok)).json()
    # at least one activity day recorded
    assert sum(e["count"] for e in act["events"]) >= 1


def test_source_too_large_rejected(client):
    _sid, tok = _reg(client)
    big = "x" * 60001
    r = client.post("/coding/submit",
                    json={"problem_id": "P-SUM-TWO", "language": "python", "source": big},
                    headers=_auth(tok))
    assert r.status_code == 422


def test_invalid_language_rejected(client):
    _sid, tok = _reg(client)
    r = client.post("/coding/submit",
                    json={"problem_id": "P-SUM-TWO", "language": "rust", "source": "fn main(){}"},
                    headers=_auth(tok))
    assert r.status_code == 422
