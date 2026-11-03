"""CareerLift AI: FairScore — dual-axis, language-fair scoring of a software-interview answer.

    python -m agent.app "A hash map gives O(1) lookup on average" --concepts C-HASH-AVG
    python -m agent.app "binary search need sorted array, it cut half each time" --concepts C-BINSEARCH

Who decides what (DESIGN.md sections 3, 6, 7, 9):
- CODE owns every band and the abstain decision (agent/fairscore.py). The model NEVER returns a score.
- The MODEL only extracts: technical claims (agent/evaluate.py) and communication observations (agent/coach.py).
- A Strands graph runs the Technical Evaluator with a bounded re-extract loop; a deterministic Verifier
  checks the claims and can fail-closed to ABSTAIN; the Communication Coach runs as an independent call.
- An input-gate hook (agent/gates.py) blocks personal data before any model call.
Lines starting with [gate] [verify] [score] are the evidence the video and measure read.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from strands import Agent
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from . import coach, config, evaluate, fairscore, mockmodel, tools
from .gates import REJECT_TEXT, InputGate, find_pii
from .models import CommObservations, ScoreResult, TechnicalClaims

MODEL_ID = os.environ.get("SHIP_MODEL", "us.amazon.nova-2-lite-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")
MAX_EVAL_PASSES = 2
logging.getLogger("strands").setLevel(logging.CRITICAL)  # a cancelled model call is expected, not an error


def _model() -> BedrockModel:
    """Construct the real Bedrock model. Raises a clear, actionable error if credentials are missing.

    This is only called in bedrock mode. Mock mode never touches Bedrock or boto3.
    """
    try:
        import boto3
        from botocore.exceptions import BotoCoreError, NoCredentialsError

        # Verify credentials are resolvable BEFORE we build the model, so a missing-credentials situation
        # becomes a clear 503 rather than an opaque failure deep inside the first model call.
        session = boto3.Session()
        if session.get_credentials() is None:
            raise config.ModelUnavailableError(
                "AI scoring is unavailable: no AWS credentials are configured for Bedrock mode. "
                "Either configure AWS credentials, or run in local demo mode with "
                "CAREERLIFT_MODEL_MODE=mock (no AWS needed)."
            )
    except config.ModelUnavailableError:
        raise
    except Exception as e:  # boto3 import or session failure
        raise config.ModelUnavailableError(
            "AI scoring is unavailable in Bedrock mode. Run in local demo mode with "
            f"CAREERLIFT_MODEL_MODE=mock to test without AWS. ({type(e).__name__})"
        )
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.1)


def structured_once_or_retry(agent, message: str, max_calls: int = 2):
    """Call a Strands agent for structured output AT MOST `max_calls` times.

    Each call is stored once (no hidden second invocation). Returns the first non-None structured
    output, or None if every attempt failed. This replaces the accidental double-call pattern
    `agent(x).structured_output or agent(x).structured_output`, which invoked the model twice EVERY time.
    """
    out = None
    for _ in range(max(1, max_calls)):
        result = agent(message)                 # one model call, stored once
        out = getattr(result, "structured_output", None)
        if out is not None:
            return out
    return out


def _task(answer: str, expected_concepts: list[str]) -> str:
    return (f"Student's interview answer:\n\"\"\"\n{answer}\n\"\"\"\n"
            f"Expected concept ids: {', '.join(expected_concepts)}\n"
            "Return one claim per expected concept.")


def _extract_claims(model, answer: str, expected_concepts: list[str], meta: dict) -> tuple[list[dict], bool]:
    """Run the Technical Evaluator. Returns (claims, gate_tripped).

    Mock mode bypasses the Strands graph (which requires real Strands agent nodes) and calls the
    deterministic mock evaluator directly. The output format is identical, so the SAME deterministic
    verifier/band pipeline runs downstream, unchanged.
    """
    if config.is_mock():
        if find_pii(answer):
            return [], True
        claims = mockmodel.extract_claims(answer, expected_concepts)   # deterministic, from the real answer
        meta["eval_passes"] = 1
        return [c.model_dump() for c in claims.claims], False

    gate = InputGate()

    def again(state) -> bool:
        r = state.results.get("evaluate")
        out = getattr(r.result, "structured_output", None) if r else None
        passes = sum(1 for x in state.execution_order if x.node_id == "evaluate")
        bad = out is None or not getattr(out, "claims", None)
        if bad and passes < MAX_EVAL_PASSES:
            print(f"[verify] pass {passes}: claims malformed -> re-extract", flush=True)
            return True
        return False

    ev = evaluate.agent(model, expected_concepts)
    b = GraphBuilder()
    b.add_node(ev, "evaluate")
    b.add_edge("evaluate", "evaluate", condition=again)
    b.set_entry_point("evaluate")
    b.set_max_node_executions(MAX_EVAL_PASSES)
    b.reset_on_revisit(True)
    b.set_hook_providers([gate])
    try:
        res = b.build()(_task(answer, expected_concepts))
    except RuntimeError:
        if gate.tripped:
            return [], True
        raise
    if gate.tripped:
        return [], True
    out = res.results["evaluate"].result.structured_output
    meta["eval_passes"] = sum(1 for n in res.execution_order if n.node_id == "evaluate")
    if out is None:
        return [], False
    return [c.model_dump() for c in out.claims], False


def _observe(model, answer: str, meta: dict) -> dict | None:
    """Communication Coach as an independent call (DESIGN.md section 4 fallback: coach outside the graph)."""
    if find_pii(answer):   # same deterministic gate, applied before this call too
        return None
    if config.is_mock():
        return mockmodel.observe(answer).model_dump()   # deterministic observations from the real answer
    a = coach.agent(model)
    out = structured_once_or_retry(a, answer, max_calls=2)   # one call, retry once on malformed; abstain otherwise
    if out is None:
        return None
    return out.model_dump()


def run(case: dict) -> dict:
    """Score ONE answer. Contract: returns {"plan": ScoreResult dict, "meta": evidence} for ss run / ss measure."""
    t0 = time.time()
    answer = case["text"]
    lang = case.get("lang") or tools.language_of(answer)
    expected = case.get("expected_concepts") or case.get("concepts") or []
    mode = config.model_mode()
    meta = {"path": "agent", "lang": lang, "expected_concepts": expected, "eval_passes": 0, "model_mode": mode}

    # Input gate (deterministic, before any model work)
    if find_pii(answer):
        print("[gate] personal data detected -> input rejected, no model call", flush=True)
        res = ScoreResult(message=REJECT_TEXT, abstained_technical=True, abstained_communication=True)
        meta["path"] = "rejected_input"
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        return {"plan": res.model_dump(), "meta": meta}

    # Mock mode never builds a Bedrock model (no AWS, no boto3 credential lookup).
    model = None if mode == "mock" else _model()
    # --- Technical axis: extract -> verify (deterministic) -> band (deterministic) ---
    claims, tripped = _extract_claims(model, answer, expected, meta)
    if tripped:
        print("[gate] personal data detected mid-extract -> input rejected", flush=True)
        res = ScoreResult(message=REJECT_TEXT, abstained_technical=True, abstained_communication=True)
        meta["path"] = "rejected_input"
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        return {"plan": res.model_dump(), "meta": meta}

    v = fairscore.verify_claims(claims, expected, answer)
    print(f"[verify] coverage {v['coverage']:.2f} | dropped {len(v['dropped'])} | "
          f"contradictions {len(v['contradictions'])} | abstain {v['abstain']}", flush=True)

    tech_band = None
    tech_evidence: list[str] = []
    misconceptions: list[str] = []
    if v["abstain"]:
        meta["abstained_technical"] = True
    else:
        tech_band = fairscore.band_from_claims(v["best_status"], expected)
        tech_evidence = [c.get("evidence_span", "") for c in v["verified"] if c.get("evidence_span")]
        # Specific misconceptions come ONLY from grounded 'incorrect' assertions that matched a curated
        # misconception signature (Fix 2). The verifier computes these; partial/absent/extraction-noise
        # never yield a tag.
        misconceptions += v.get("misconception_tags", [])

    # --- Communication axis: independent extraction -> band (deterministic) ---
    obs = _observe(model, answer, meta)
    comm_band = None
    comm_evidence: list[str] = []
    if obs is None:
        meta["abstained_communication"] = True
    else:
        comm_band = fairscore.comm_band(obs)
        # Ground communication evidence in the actual answer: keep only quotes that really appear in it.
        comm_evidence = [q for q in obs.get("evidence", []) if q and fairscore.span_is_grounded(q, answer)]

    base_message = (fairscore.ABSTAIN_TEXT if tech_band is None else
                    f"Technical: {tech_band}. Communication: {comm_band or 'not assessed'}.")
    if mode == "mock":
        base_message = f"[{mockmodel.MOCK_LABEL}] " + base_message
        meta["mock"] = True
        meta["mock_label"] = mockmodel.MOCK_LABEL

    res = ScoreResult(
        technical_band=tech_band,
        communication_band=comm_band,
        technical_evidence=tech_evidence,
        communication_evidence=comm_evidence,
        misconception_tags=sorted(set(misconceptions)),
        abstained_technical=tech_band is None,
        abstained_communication=comm_band is None,
        message=base_message,
    )
    meta["latency_ms"] = int((time.time() - t0) * 1000)
    print(f"[score] technical={tech_band} communication={comm_band} "
          f"misconceptions={res.misconception_tags} | {meta['latency_ms']} ms", flush=True)
    return {"plan": res.model_dump(), "meta": meta}


def _print(p: dict) -> None:
    print()
    if p.get("abstained_technical"):
        print("Technical: not assessed (abstained)")
    else:
        print(f"Technical band:     {p['technical_band']}")
    if p.get("abstained_communication"):
        print("Communication: not assessed")
    else:
        print(f"Communication band: {p['communication_band']}")
    if p.get("misconception_tags"):
        print("Misconceptions:     " + ", ".join(p["misconception_tags"]))
    if p.get("message"):
        print(p["message"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agent.app", description=__doc__.splitlines()[0])
    ap.add_argument("text")
    ap.add_argument("--concepts", default="", help="comma-separated expected concept ids")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    expected = [c.strip() for c in a.concepts.split(",") if c.strip()]
    out = run({"text": a.text, "expected_concepts": expected})
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        _print(out["plan"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
