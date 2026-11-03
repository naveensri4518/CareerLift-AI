# CareerLift AI — Strands Agent Design (AWS execution phase, Recipe 2 delta)

Status: **DESIGN ONLY.** No AWS calls made, no model invoked, no source changed by writing this doc.
This is an *additive* design delta for the AWS execution phase. It does **not** replace the frozen
`DESIGN.md` (the original FairScore Recipe-2 design), which remains authoritative.

> Honest framing up front: the Strands-powered Bedrock agent this assignment asks for **already exists**
> in the codebase (`agent/app.py` — FairScore). "Design my agent" here is therefore a *delta*: confirming
> the existing agent is the right one, naming its blocks against the live product, and designing the one
> genuinely new piece — making the real Bedrock FairScore path the scoring provider for the live product
> surfaces once the account's Bedrock inference verification clears. Per Recipe 2, the normal
> "run the chosen blocks live" step (`ss blocks` / `ss block`, ~5-20 s each on Nova 2 Lite) is **DEFERRED**
> because it invokes Bedrock and the account is under an inference-verification hold. It will be run as the
> approved single controlled connectivity test once verification clears — not looped now.

---

## 1. The agent (confirmed, already implemented)

**FairScore** — a Strands graph agent that scores one interview answer on two independent axes (Technical,
Communication), with a deterministic Verifier and a code-owned band decision. Implemented in `agent/app.py`
(+ `evaluate.py`, `coach.py`, `fairscore.py`, `gates.py`, `models.py`, `mockmodel.py`, `session.py`).

- **Responsibilities:** extract technical claims + communication observations from an answer (model);
  verify claims against the curated concept reference (deterministic); assign bands and the abstain
  decision (deterministic Python); emit evidence + misconception tags.
- **Inputs:** `{text, expected_concepts}` (an answer + the server-owned expected concept ids).
- **Outputs:** `ScoreResult{technical_band, communication_band, *_evidence, misconception_tags,
  abstained_*, message}` — the model never returns a score.
- **Strands architecture:** `GraphBuilder` graph (`evaluate` with a bounded re-extract self-loop →
  deterministic verify), `BedrockModel` (Nova 2 Lite), structured output (Pydantic), a `BeforeModelCallEvent`
  input-gate hook (PII block), and `FileSessionManager` for conversation persistence.
- **Bedrock integration:** `agent/app.py _model()` builds `BedrockModel(model_id=SHIP_MODEL,
  region_name=AWS_REGION, temperature=0.1)`; credentials via `boto3.Session()` (SSO / instance role).
- **Session management:** `agent/session.py` `FileSessionManager` → `CAREERLIFT_SESSIONS` dir.
- **Error handling:** missing creds / Bedrock error → `ModelUnavailableError` → clean **503** (never a
  fabricated score); malformed structured output → one retry then abstain; PII → input gate blocks before
  any token spend.
- **Evaluation criteria:** fairness gap + technical/communication accuracy + unsupported-claim rate +
  abstain rate, FairScore vs a one-prompt baseline, via `ss measure` on signed cases (see `DESIGN.md §12`).

## 2. Blocks used (spine + supporting), each with its job (Recipe 2 Step 1)

Picked for the job they do for CareerLift's users — not for novelty. (All already present in code.)

| Block | Job | Rubric quarter | Shows up as |
|---|---|---|---|
| **graph** (spine) | `evaluate →(loop ≤1)→ verify`; bounded, fail-closed | Technical, Originality | Verifier catches an unsupported claim; unsupported-claim rate in results |
| **tools / structured output** | deterministic rubric + identical claim/observation JSON per answer | Technical | identical fields → deterministic metrics |
| **hooks** (`BeforeModelCallEvent.cancel`) | PII/off-task input gate before any model call | Impact, Originality | blocked input spends 0 tokens |
| **sessions** (`FileSessionManager`) | per-student conversation persistence on disk | Impact | context bounded across turns |
| **Strands Evals / `ss measure`** | FairScore vs baseline on signed cases | Impact, Technical | the headline fairness-gap number |

Deliberately NOT used (unchanged from DESIGN.md): swarm, agents-as-tools, decider, guardrails (MVP uses
the deterministic hook), voice/shell/harness/MCP. No new blocks are added this phase.

## 3. The one genuinely new design element this phase: live Bedrock as the product scoring provider

Today every product surface (Quick Practice `/score`, and Phases 1–4) runs with
`CAREERLIFT_MODEL_MODE=mock` (deterministic, offline). The FairScore Bedrock path is fully coded but only
exercised by `ss run` / `ss measure`. The AWS-phase design decision:

- **Keep `mock` as the default and the kill-switch** (unchanged). Flip to `CAREERLIFT_MODEL_MODE=bedrock`
  only on the deployed instance, once Bedrock inference verification clears, so `/score` (and optionally
  the Interview Studio provider, which already routes through `agent.app.run`) uses the real Nova 2 Lite
  path. **No code change is required** — it is one environment variable on the server plus the instance
  role's `bedrock:InvokeModel` permission.
- **Determinism and FairScore principles are preserved:** bands, abstain, verifier, and fairness checks
  remain pure Python; Bedrock only supplies claim/observation extraction. Phases 2–4 stay deterministic
  (they do not call Bedrock) regardless of the mode.
- **Rollback:** flip the env var back to `mock` + restart → instant return to the offline evaluator with
  no loss of functionality.

This is the smallest change that delivers "Bedrock-backed functionality" without re-opening the frozen
design or duplicating the existing Strands integration.

## 4. The decision that must never be wrong (carried from DESIGN.md §3)

The technical band — a correct answer must not be downgraded for plain English. Owned by deterministic
Python (`agent/fairscore.py`), never by the model. Thresholds (`BAND_CUTS`, `COMM_CUTS`, `FAIR_TOL`,
`ABSTAIN_MIN_SUPPORT`) live in code; changing one triggers `ss measure` re-run + a FAILURES.md entry.
Unchanged this phase.

## 5. Out of scope for this phase

- No new agent, no swarm, no second model, no new blocks (would duplicate the existing integration).
- No change to `recommend.py` / frozen Learning Intelligence.
- No Phase 5.
- Live `ss block` / `ss measure` in bedrock mode until verification clears (then a single controlled test).

## 6. Rubric sanity check (Recipe 2 Step 4), 1–10

- Social impact: 9 — the fairness mechanism is the product; live Bedrock makes the real demo possible.
- Technical execution: 9 — graph + structured output + hook + sessions, code-owned decision, already built
  and tested (186 backend tests).
- Communication: 8 — the two-answers-same-content + fairness-gap story is intact; needs the live demo.
- Originality: 8 — a measured fairness gap on a dual-axis scorer, beyond a plain swarm.
- Buildable in the time left: 10 — the agent is already built; this phase is config + deploy + (deferred)
  measure. Nothing scores under 6.

## 7. Build step (Recipe 3) implication

Because the agent is already built, "build the agent" this phase = **verify** the existing build runs
end-to-end (mock mode) and that the bedrock path is correctly wired (confirmed by the earlier controlled
connectivity test, which reached Bedrock and failed only on the account verification hold — proving the
integration, not a code defect). No new agent code is written; any fix would be a documented regression
fix only.
