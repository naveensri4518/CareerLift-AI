# CareerLift AI — DESIGN (Revised)

*Recipe 2 output, revised after review. Turns the approved IDEA.md (Direction A: FairScore Engine) into a concrete Strands architecture.*

> Status: design only. No code written, no AWS calls, no model invocations, no starter files modified.
> Workspace: `C:\Users\Naveensri\Downloads\Madurai-TamilNadu-kiro` (unchanged).
> Decisions locked: four-band scoring (Weak / Partial / Solid / Strong) on both axes; Tamil secondary; low-cost, minimal model calls.
> This revision addresses six review points: (1) fairness enforcement honesty, (2) real graph topology, (3) session vs SQLite, (4) verifier limits, (5) deterministic communication rubric, (6) hook/abstention control flow.

---

## 0. Verified vs proposed — read this first

To keep the design honest, every SDK claim below is tagged:

- **[VERIFIED 1.62.0]** — confirmed by inspecting the installed `strands-agents==1.62.0` in the setup venv, or by a live-tested kit block (`~/.strands-ship/kit/blocks/*.py`).
- **[PROPOSED]** — CareerLift application logic we will write; not an SDK guarantee.
- **[ASSUMPTION — verify at build time]** — behaviour we expect but have **not** confirmed; must be checked when we start Recipe 3 (no AWS call needed to check most of these).

**What was verified for this revision** (by importing the installed SDK and reading kit blocks, no model calls):

- `strands.multiagent` exports: `GraphBuilder`, `Swarm`, `EdgeCondition`, `EdgeConditionWithContext`, `GraphResult`, `MultiAgentBase`, `Status`, and others. **[VERIFIED 1.62.0]**
- `GraphBuilder` methods: `add_node`, `add_edge`, `build`, `set_entry_point`, `set_max_node_executions`, `set_node_timeout`, `set_execution_timeout`, `reset_on_revisit`, `set_hook_providers`, `set_session_manager`, `set_plugins`, `set_graph_id`. **[VERIFIED 1.62.0]**
- `GraphBuilder.add_node(executor, node_id=None)` — `executor` is an `AgentBase` **or** a `MultiAgentBase`. `GraphBuilder.add_edge(from, to, condition=None)` — `condition` is `Callable[[GraphState], bool]` or `EdgeConditionWithContext`. **[VERIFIED 1.62.0]**
- `strands.hooks` includes **both** `BeforeNodeCallEvent` and `AfterNodeCallEvent`, plus `BeforeModelCallEvent`/`AfterModelCallEvent`, `BeforeToolCallEvent`, `MessageAddedEvent`, etc. **[VERIFIED 1.62.0]**
- `BeforeModelCallEvent.cancel` stops the model call (kit block `b03_hooks.py`, live-tested). **[VERIFIED 1.62.0]**
- `strands.session` provides `FileSessionManager`, `S3SessionManager`, `RepositorySessionManager`, `SessionRepository`, `SessionManager` — **there is no `SqliteSessionManager`.** `FileSessionManager(session_id=..., storage_dir=...)` persists conversation state to **files on disk** (kit block `b08_sessions.py`, live-tested). **[VERIFIED 1.62.0]**

**What is NOT verified and must not be asserted:**

- Whether the graph runs independent branches **concurrently** (true parallelism) vs sequentially. The SDK expresses fan-out/fan-in through *edges*, not a `parallel()`/`join()` primitive. There is no verified parallel-execution or barrier API. **[ASSUMPTION — verify at build time]**
- The exact shape of `GraphState` (attributes like `results`, `execution_order`) beyond what kit block `b05_graph.py` uses (`state.results["<node>"].result.structured_output`, `state.execution_order` with `.node_id`). We rely only on those two, which are live-tested. **[VERIFIED 1.62.0 for those two fields]**

---

## 1. Design principles (carried from IDEA.md, non-negotiable)

1. **Technical and communication are independent.** Two separate scores, two separate code paths. Neither path's output is an input to the other.
2. **Never penalise correct technical content for plain English, grammar, accent, or vocabulary.** Technical scoring reads *extracted claims*, not prose style.
3. **No fairness-by-flattening.** Technical *accuracy* against human labels is measured alongside the fairness gap. A scorer that outputs one band for everything is accuracy-poor and fails the gate.
4. **Paraphrase-pair fairness is an OFFLINE evaluation property.** A live single answer has no pair; see §2 for exactly what we can and cannot claim at run time.
5. **Honest failure reporting.** Fairness failures are reported as numbers, never hidden; no "guaranteed bias-free" claim is made anywhere.
6. **Deterministic Python over model calls.** Bands, tolerances, thresholds, verification, planner selection, and the fairness gap are pure functions. The model only *extracts claims/observations and phrases words*.
7. **Small, explainable, testable, cheap.**

---

## 2. CORRECTION 1 — Fairness enforcement (what it does and does NOT guarantee)

**The honest limit, stated plainly.** Separating technical scoring from communication scoring, and computing the technical band from extracted claims in Python, **does not mathematically guarantee language fairness.** The reason: **claim extraction itself is done by an LLM.** If the extractor is more likely to miss a correct claim when the answer is in plain English (or Tamil-influenced English), bias re-enters at the extraction step, *before* any deterministic code runs. Deterministic banding cannot fix a biased claim set it was handed. So fairness is a **property we must measure, not a property the architecture proves.**

What the architecture *does* give us:
- It **removes prose style as a direct input to the score** (the band is a function of claims, not of grammar/vocabulary/length). This blocks the most obvious bias channel.
- It makes the remaining bias channel (extraction) **observable and measurable** offline.

### 2.1 Offline paraphrase-pair evaluation [PROPOSED evaluation method]
For evaluation only (not at run time), each signed case carries a **paraphrase pair**: the *same technical content* expressed as
- (a) **plain/simple English** (short words, possibly imperfect grammar), and
- (b) **advanced English** (richer vocabulary, complex sentences),
both human-labelled with the **same** expected technical band and misconception tags (because the technical content is identical by construction).

We run the full FairScore pipeline on (a) and on (b) independently and compare the technical bands.

### 2.2 Technical accuracy against human-labelled concepts [PROPOSED metric]
For every case (both members of each pair), compare the **computed technical band** to the **human-labelled** band. Report agreement (exact-match rate and within-one-band rate). This is the guard against fairness-by-flattening: a flattening scorer scores pairs equally (great fairness gap) but disagrees with human labels (poor accuracy) — the gate catches it.

### 2.3 Mean and maximum fairness gap [PROPOSED metric]
Encode bands as ordinal integers Weak=0, Partial=1, Solid=2, Strong=3. For each pair *i*, `gap_i = |band(a_i) - band(b_i)|`.
- **Mean fairness gap** = average of `gap_i` over all pairs.
- **Maximum fairness gap** = the worst single pair.
Lower is better; 0 means the register never changed the technical band on the dataset. The one-prompt baseline is expected to show a larger gap; FairScore's job is to shrink it **without** losing technical accuracy (§2.2).

### 2.4 How extraction inconsistencies are detected [PROPOSED]
Because (a) and (b) have identical technical content, their *extracted claim sets should also be equivalent*. We compute, per pair, a **claim-set divergence**: concepts marked `supported`/`partial` for one register but not the other. A non-zero divergence localises *where* the extractor is register-sensitive (which concept, which direction). This is reported per concept so we can fix prompts or add examples. Any pair with `gap_i > FAIR_TOL` is flagged as a **fairness failure** and listed individually.

### 2.5 How fairness failures are reported [PROPOSED]
`ss measure` writes numbers to `results/` only (never typed by hand): mean gap, max gap, the count and IDs of pairs exceeding `FAIR_TOL`, and per-concept divergence. The article/video quote these generated numbers. **We never claim every live answer is bias-free.** At run time we can only say: "this answer's technical band was computed from extracted claims; confidence is reduced when verifier support is low (see §6/§7)." The fairness *gap* is a statement about the dataset, not about any individual live answer.

---

## 3. The decision that must never be wrong, and which code owns it

**The decision:** the **technical band** assigned to a student's answer — specifically, that a technically correct answer is **not** downgraded for simple English, grammar, accent, or vocabulary.

**Who owns it:** plain Python. The model (Technical Evaluator) returns a **structured list of claims** with no score; a deterministic function maps claim coverage → band. Prose style is never an input to that function. (The residual risk is extraction bias, measured per §2 — stated honestly, not hidden.)

**Thresholds / constants, and their source:**

| Constant | Meaning | Source |
|---|---|---|
| `TECH_BANDS = [Weak, Partial, Solid, Strong]` | technical bands | IDEA.md (approved) |
| `COMM_BANDS = [Weak, Partial, Solid, Strong]` | communication bands | IDEA.md (approved) |
| `BAND_CUTS` | claim-coverage → technical band cutoffs | **our calibration** on signed cases; logged in FAILURES.md when tuned |
| `COMM_CUTS` | observation-count → communication band cutoffs (see §7) | **our calibration** |
| `FAIR_TOL` | max allowed technical-band gap per pair (offline) | our calibration; starts at 1 band |
| `ABSTAIN_MIN_SUPPORT` | min fraction of claims the Verifier must support, else abstain | our calibration |

No threshold is a model output. Changing any constant triggers a re-run of `ss measure` and a FAILURES.md entry.

---

## 4. CORRECTION 2 — Actual Strands graph topology [VERIFIED API + PROPOSED wiring]

The earlier draft implied a `parallel`/`join` primitive. The SDK has none. Here is the topology expressed only with **verified** primitives (`add_node`, `add_edge` with a `condition`, `set_entry_point`, `set_max_node_executions`, `reset_on_revisit`), plus an explicit flag on what remains an assumption.

```
                    ┌──────────────────────────────────────────────┐
  entry: "intake"   │  intake node: pass-through of the (question,   │   (a tiny Agent or a
  (set_entry_point) │  expected_concepts, answer). Fan-out point.    │    MultiAgentBase; see note)
                    └───────────────┬───────────────┬──────────────┘
                                    │ add_edge      │ add_edge
                                    ▼               ▼
                        ┌────────────────┐   ┌────────────────────┐
                        │ "evaluate"     │   │ "coach"            │
                        │ Technical Eval │   │ Communication Coach│
                        │ (claims only)  │   │ (observations only)│
                        └───────┬────────┘   └─────────┬──────────┘
            conditional add_edge│ (claims malformed?)   │
            back to "evaluate"  │  ← re-extract once     │
            [EdgeCondition]     ▼                        │
                        ┌────────────────┐               │
                        │ "evaluate"     │ (bounded by   │
                        │  (2nd pass max)│  set_max_node_│
                        └───────┬────────┘  executions)  │
                                │ add_edge               │ add_edge
                                ▼                        ▼
                        ┌──────────────────────────────────────────┐
                        │ "join" node  (fan-in: both inputs ready)   │
                        │ passes evaluate+coach outputs downstream   │
                        └───────────────────┬────────────────────────┘
                                            ▼
                        ┌──────────────────────────────────────────┐
                        │ "verify" node — DETERMINISTIC critic       │
                        │ (claims vs concept reference; abstain flag)│
                        └───────────────────┬────────────────────────┘
                                            ▼
                        graph ends → Python returns GraphResult
                                            ▼
          [outside the graph]  DETERMINISTIC SCORING in Python → ScoreResult
```

**Node-by-node:**

- **Entry node `intake`** [VERIFIED `set_entry_point`] — a single entry is required; it fans out to the two extractors via two `add_edge` calls.
- **Fan-out to `evaluate` and `coach`** [VERIFIED `add_edge`] — two outgoing edges from `intake`. **Whether these run concurrently is [ASSUMPTION — verify at build time].** The design is correct either way: there is no data dependency between them, so sequential execution only costs latency, not correctness. We will verify concurrency behaviour by inspecting `GraphResult.execution_order`/timing in Recipe 3 (no AWS needed beyond the normal evaluate call).
- **Conditional self-loop on `evaluate`** [VERIFIED `add_edge(condition=...)` + `set_max_node_executions` + `reset_on_revisit`, pattern from live block `b05_graph.py`] — if the claims structured-output is malformed/empty, re-run `evaluate` **at most once**. The condition function reads `state.results["evaluate"]` and counts prior `evaluate` executions in `state.execution_order` (the exact fields used by the live block).
- **Fan-in `join` node** [VERIFIED `add_edge` for the two incoming edges; PROPOSED node] — a node with two incoming edges that forwards both extractor outputs. **[ASSUMPTION — verify at build time]:** that a node with two incoming edges waits for both before executing (barrier semantics). If the SDK does **not** barrier automatically, the fallback (below) removes the need for a join node entirely.
- **`verify` node** — deterministic critic (no model call); see §6.
- **Scoring is OUTSIDE the graph** — after `graph.build()(...)` returns a `GraphResult`, Python computes the bands and fairness-related fields. This placement is deliberate and drives CORRECTION 6 (hooks can't gate it).

**Fallback topology if fan-in/parallel is not supported as assumed [PROPOSED, zero new risk]:**
Run the **Communication Coach outside the graph** as a plain `Agent` call, and keep the graph as a simple linear `intake → evaluate →(loop once)→ verify`. The two axes are independent, so running coach as a separate call preserves every design principle and simply trades the (unverified) in-graph parallelism for two explicit calls. This fallback is fully expressible with verified primitives and is the default we implement first; the in-graph two-branch version is an optimisation we attempt only after verifying barrier semantics.

---

## 5. Strands blocks selected (spine + supporting), each with its job

| Block | Job in CareerLift | Rubric quarter | Shows up as | Status |
|---|---|---|---|---|
| **graph** (`GraphBuilder`, conditional edge, `set_max_node_executions`) | **Spine.** `intake → evaluate →(loop once)→ verify` (+ optional coach branch). Counted, bounded, fail-closed. | Technical, Originality | demo: Verifier catches an unsupported claim; `results` shows unsupported-claim rate | [VERIFIED 1.62.0] |
| **tools / structured output** (`@tool` + Pydantic `structured_output_model`) | Deterministic rubric functions; structured claim/observation extraction so every answer has identical fields | Technical | identical JSON per answer → deterministic metrics | [VERIFIED 1.62.0] |
| **hooks** (`HookProvider`, `BeforeModelCallEvent.cancel`) | The **input gate** before model calls (PII/off-task). See §6 for why the *abstain* decision is NOT a hook. | Impact, Originality | demo: off-task/PII input blocked before any token spend | [VERIFIED 1.62.0] |
| **sessions** (`FileSessionManager` + `SlidingWindowConversationManager`) | Strands-side conversation persistence per student (files on disk). Distinct from app SQLite — see §8. | Impact | before/after across two sessions | [VERIFIED 1.62.0] |
| **Strands Evals / `ss measure`** | Proof: FairScore vs one-prompt baseline on signed paraphrase-paired cases — fairness gap **and** technical accuracy, gated | Impact, Technical | the headline numbers | [VERIFIED 1.62.0] |

**Deliberately NOT used (unchanged reasoning):** swarm (no case-dependent triage), agents-as-tools (no orchestrator pattern), decider (needs a key; the technical verdict must be an explainable code-owned rubric, not an opaque score), guardrails (a deterministic input hook covers MVP; Bedrock Guardrails is a stretch), voice/shell/harness/MCP (no visible MVP job).

---

## 6. CORRECTION 4 — Verifier design (what Python can and cannot prove)

The Verifier is **deterministic Python, zero model calls**. Here is precisely what it does with each field, and — importantly — **what it cannot prove.**

**Inputs:**
- `expected_concepts`: the concept IDs the question targets (from the curated concept reference). [PROPOSED data]
- `TechnicalClaims.claims`: list of `{concept_id, status, evidence_span}` from the extractor. [model output]
- concept reference: `{concept_id → {canonical_name, key_points, aliases}}`. [PROPOSED data]

**What the Verifier checks (all deterministic):**
1. **Concept-ID validity.** Every `claim.concept_id` must exist in the concept reference. Unknown IDs (model hallucinated a concept) are **dropped**.
2. **Relevance.** Claims whose `concept_id` is not in this question's `expected_concepts` are set aside (not counted toward coverage; retained for feedback only).
3. **Evidence-span presence & grounding.** `evidence_span` must be non-empty **and be an actual substring (normalised) of the student's answer.** If the span is empty or not found in the answer, the claim is **unsupported** (the extractor asserted something without pointing to the text). This catches fabricated support.
4. **Internal contradiction.** If the same `concept_id` appears with conflicting statuses (e.g. `supported` and `absent`), or if two mutually-exclusive concept IDs (declared as an exclusion pair in the reference) are both `supported`, the pair is flagged **contradictory** and both are demoted to `partial` pending the score rubric.
5. **Support threshold.** Compute `support = (# claims surviving 1–4 that are supported/partial) / (# expected_concepts)`. If `support < ABSTAIN_MIN_SUPPORT`, set **abstain = true** (fail-closed).

**What deterministic Python genuinely proves:**
- That a claimed concept ID is real (exists in the reference).
- That the claim points to text that actually appears in the answer (evidence grounding).
- That the claim set is internally consistent and relevant to the question.
- That enough of the expected concepts were addressed to justify a confident band (coverage).

**What it CANNOT prove (stated honestly):**
- That a `supported` claim is **technically correct**. Verifying the evidence span exists in the answer is **not** proof the answer is right — only that the model quoted the student. **Simple ID membership and substring grounding are checks of consistency and coverage, not of truth.** Establishing truth would require either a human label (what the offline dataset provides) or an external authoritative source per concept (a future `key_points` entailment check, which itself would likely need a model and is therefore out of the deterministic core). The Verifier therefore gates **confidence**, not **correctness**; correctness is measured only against human labels offline (§2.2).

This distinction is load-bearing: at run time we present a *coverage- and consistency-checked* band with an abstain path, never a claim of proven correctness.

---

## 7. CORRECTION 5 — Deterministic four-band communication rubric

Communication is scored from four observations only: **clarity, logical structure, relevance, organisation.** Each is extracted as one of `{present, partial, absent}` by the Communication Coach (which never sees the technical claims or band). The Coach is **explicitly instructed and the rubric is explicitly designed** to ignore: simple English, grammar mistakes, accent/spelling, vocabulary sophistication, and answer length on its own.

**Deterministic mapping (pure Python `comm_band()`):** score each observation `present=1, partial=0.5, absent=0`, sum over the four dimensions → `S ∈ [0, 4]`.

| Communication band | Rule on S (the four dimensions) | Plain meaning |
|---|---|---|
| **Strong** | `S ≥ 3.5` **and** no dimension is `absent` | all four largely present; well-organised and on-point |
| **Solid** | `2.5 ≤ S < 3.5` **and** at most one dimension `absent` | mostly clear and structured, minor gaps |
| **Partial** | `1.5 ≤ S < 2.5` | some structure/clarity but noticeably incomplete |
| **Weak** | `S < 1.5` | largely unclear/disorganised/off-point |

**Anti-bias guards baked into the rubric (not just the prompt):**
- Length is **not** a dimension and cannot move the band. A correct two-sentence answer can be **Strong**.
- Grammar/accent/vocabulary are **not** dimensions. "Relevance" asks *does it address the question*, not *is the English fluent*. "Clarity" asks *can the point be understood*, explicitly allowing plain English.
- Because `comm_band()` consumes only the four `{present/partial/absent}` labels, no prose feature outside those four can influence the band.

**Residual honesty:** as with the technical axis, the *extraction* of the four observations is done by the model, so register-sensitivity is possible at extraction. We therefore apply the **same paraphrase-pair divergence check to the communication observations** offline and report any register-driven communication-band gap alongside the technical one. (Communication *should* legitimately differ if structure differs — so we only flag divergence on pairs constructed to hold structure constant while varying register.)

---

## 8. CORRECTION 3 — Session vs database architecture (they are NOT interchangeable)

Verified fact: **`FileSessionManager` persists to files on disk, not SQLite. There is no `SqliteSessionManager` in strands-agents 1.62.0.** The earlier draft wrongly implied `FileSessionManager + SQLite` were one thing. They are two separate layers:

| Layer | What it is | Backed by | Owns | Status |
|---|---|---|---|---|
| **Strands conversation/session** | `FileSessionManager(session_id, storage_dir)` + `SlidingWindowConversationManager(window_size)` | **files on disk** (Strands' own format) | the LLM conversation state / message window for a student's live interview turn, so context is bounded and cheap | [VERIFIED 1.62.0] |
| **CareerLift application persistence** | our own SQLite database (`careerlift.db`) accessed via Python `sqlite3`/SQLModel | **SQLite** | durable application records: students, interviews, per-answer `ScoreResult`s, misconception tally | [PROPOSED] |

**Why both, and the boundary:**
- Strands sessions keep the *model conversation* coherent and context-bounded within an interview. We do **not** try to make Strands write our analytics schema.
- SQLite is CareerLift's **source of truth** for everything we report and track: interview history and the misconception map. The app writes a row per scored answer after the graph returns.
- **Interview history** [PROPOSED]: SQLite tables `student`, `interview`, `answer(score_result, abstained, created_at)`.
- **Misconception tracking** [PROPOSED]: SQLite table `misconception(student_id, concept_id, count, last_seen)`, incremented from `ScoreResult.misconception_tags`. The Learning Planner reads this table (deterministic selection), not the Strands session.

Mapping key: both layers key on the same `student_id` / `session_id` string so a student's conversation files and their SQLite rows line up. [PROPOSED]

---

## 9. CORRECTION 6 — Hooks and abstention: exact control flow

The earlier draft said a hook would "cancel the scoring node." That is wrong given §4: **scoring runs in Python *after* the graph returns, so no graph/agent hook event fires there.** Hooks fire on the **agent loop / graph node execution**, verified events being `BeforeModelCallEvent`, `BeforeNodeCallEvent`, etc. Corrected design:

**Where each gate actually operates:**

1. **Input gate = a real hook.** A `HookProvider` on `BeforeModelCallEvent.cancel` (verified pattern from `b03_hooks.py`) runs **before any extractor model call**. It deterministically scrubs/rejects PII and off-task input. If it cancels, **no tokens are spent** and the API returns a fixed "please rephrase / no personal data" result. This is the one place a hook is the right tool.

2. **Abstention = deterministic Python, NOT a hook.** The Verifier (a deterministic node/step) sets `abstain=true` when `support < ABSTAIN_MIN_SUPPORT`. The abstain decision and the user-facing abstain text are produced by **plain Python in the scoring step**, which runs after the graph. No hook, no model, involved.

**Actual control flow from verification failure to API result:**

```
answer → [BeforeModelCallEvent hook: input gate]
            │ cancelled? → return {status:"rejected_input", message: FIXED_TEXT}  (0 model calls)
            ▼ not cancelled
         graph runs: intake → evaluate (→loop once) → (coach) → verify(node, deterministic)
            │
            ▼ graph returns GraphResult (claims, verified set, abstain flag, observations)
         [Python scoring step, OUTSIDE the graph]
            │ abstain == true ?
            │     yes → ScoreResult{ technical_band: null, abstained_technical: true,
            │                        message: FIXED_ABSTAIN_TEXT, evidence: surviving claims }
            │     no  → ScoreResult{ technical_band = band_from_claims(verified),
            │                        communication_band = comm_band(observations), evidence, tags }
            ▼
         FastAPI returns ScoreResult as JSON → UI renders two panels, or the abstain state
```

**User-facing feedback on abstain [PROPOSED]:** the UI shows a non-judgmental state — "We couldn't confidently assess the technical content of this answer (not enough of the expected points were clearly addressed). Here's what we did recognise: …" — plus the surviving evidence and an invitation to try the explain-again loop. It never shows a guessed band, and it never says the answer was "wrong."

---

## 10. Structured outputs (Pydantic, design-time shapes) [PROPOSED]

- `Question{ text: str, expected_concepts: list[str], difficulty: str }`
- `TechnicalClaims{ claims: list[Claim] }`, `Claim{ concept_id: str, status: Literal["supported","partial","absent"], evidence_span: str }`
- `CommObservations{ clarity, structure, relevance, organisation: Literal["present","partial","absent"], notes: str }`
- `ScoreResult{ technical_band: Band|None, communication_band: Band|None, evidence: {...}, misconception_tags: list[str], abstained_technical: bool, abstained_communication: bool }`, `Band = Literal["Weak","Partial","Solid","Strong"]`

The model produces only `Question`, `TechnicalClaims`, `CommObservations`. `ScoreResult` is produced by Python.

---

## 11. Agents and files (design-time; nothing created now)

| Component | Model? | File (created at build time) |
|---|---|---|
| Interviewer (question + ≤1 follow-up; concepts chosen from reference) | 1 call/question (cacheable) | `agent/interview.py` [PROPOSED] |
| Technical Evaluator (claims, no score) | 1 call (+1 retry max) | `agent/evaluate.py` [PROPOSED] |
| Communication Coach (observations, no score, no technical view) | 1 call (+1 retry max) | `agent/coach.py` [PROPOSED] |
| Verifier (deterministic critic) | 0 | `agent/verify.py` [PROPOSED] |
| Input gate hook + abstain text | 0 | `agent/gates.py` [PROPOSED] |
| Deterministic scoring (`band_from_claims`, `comm_band`, fairness helpers) | 0 | fills in the **starter** `agent/score.py` at build time (untouched now) |
| Learning Planner (deterministic selection; optional phrasing) | 0 (or 1 optional) | fills in the **starter** `agent/plan.py` at build time (untouched now) |
| Pydantic models | — | `agent/models.py` [PROPOSED] |
| Concept reference | — | `agent/data/concepts.json` [PROPOSED] |

Starter files (`agent/app.py`, `agent/plan.py`, `agent/tools.py`, `agent/score.py`, `agent/baseline.py`, `cases.jsonl`, `video.json`) are **replaced/filled at implementation, untouched during design.**

---

## 12. What is measured, and the baseline [PROPOSED metrics via `ss measure`]

Case shape (offline, signed): question, `expected_concepts`, the paraphrase pair (plain / advanced), human-labelled technical band and misconception tags. (Exact field names finalised at build time; starter `cases.jsonl` not edited now.)

Metrics (agent vs one-prompt baseline), all written to `results/` by `ss measure`:
1. **Mean & max fairness gap** (§2.3) — headline.
2. **Technical accuracy** vs human labels (§2.2) — the anti-flattening guard.
3. **Communication accuracy** vs human labels.
4. **Misconception detection accuracy.**
5. **Unsupported-claim rate** (Verifier drops), agent vs baseline.
6. **Abstain rate** — reported, not hidden.
7. **Per-concept extraction divergence** (§2.4).

Baseline: a single-prompt grader that returns both scores directly, with no claim extraction, no verifier, no code-owned bands. Gate passes only if FairScore is safe on every signed case and beats the baseline on the fairness gap **without** losing technical accuracy.

---

## 13. AWS services and jobs

| Service | Job | MVP? |
|---|---|---|
| Amazon Bedrock (Nova 2 Lite) | extractor model calls | Yes |
| Amazon Translate | Tamil ↔ English fallback | **Secondary** |
| Amazon Transcribe `ta-IN` | Tamil speech in | Future (voice) |
| Amazon Bedrock Guardrails | managed PII redaction | Future (MVP uses deterministic input hook) |

No AgentCore/Lambda/S3/DynamoDB in MVP. SQLite + local FastAPI; zero standing infrastructure.

---

## 14. CORRECTION (model-call estimates incl. retries & evaluation) [realistic]

**Per answer scored:**

| Step | Model calls (typical) | Worst case |
|---|---|---|
| Interviewer (question) | 1 per question, cacheable → ~0 amortised | 1 (+1 retry) |
| Technical Evaluator | 1 | 2 (one retry) |
| Communication Coach | 1 | 2 (one retry) |
| Verifier | 0 | 0 |
| Scoring + fairness | 0 | 0 |
| Planner selection | 0 | +1 only if model-phrased |

- **Typical: 2 calls/answer** (evaluate + coach). **3** including a non-cached question.
- **Worst case: ~5** (both retries fire + optional planner phrasing + non-cached question).

**Evaluation cost (`ss measure`) — this dominates:** for a dataset of **N pairs = 2N answers**, FairScore does ~2 calls/answer → **~4N calls**, and the baseline does ~1 call/answer → **~2N calls**, so a full gated run is **~6N model calls** (plus any retries). Example: N=30 pairs → ~180 calls per full run. Mitigation: iterate with `ss measure --limit`, run the full set only at gate time; Nova 2 Lite; low temperature; cache questions. Translate calls only appear if the (secondary) Tamil path is exercised.

---

## 15. Consistency check: IDEA.md ↔ DESIGN.md

| IDEA.md claim | DESIGN.md status |
|---|---|
| Direction A, FairScore headline | ✔ kept |
| Four bands both axes | ✔ Weak/Partial/Solid/Strong on both (§3, §7) |
| Technical/communication independent | ✔ separate agents, separate code, no cross-input (§1, §7) |
| No penalising plain English/grammar/vocab | ✔ structural in `band_from_claims` and `comm_band` (§3, §7) |
| No fairness-by-flattening | ✔ technical accuracy measured with the gap (§2.2, §12) |
| Paraphrase pairs are offline | ✔ explicit; live answers not claimed bias-free (§2) |
| Verifier fail-closed | ✔ abstain path (§6, §9) |
| sessions for before/after | ✔ Strands sessions + SQLite separated (§8) |
| Tamil secondary | ✔ (§13) |
| Minimal model calls / low cost | ✔ (§14) |
| MVP = dual-axis FairScore + verifier + `ss measure` | ✔ (§5, §12) |

One correction to IDEA.md wording for later: IDEA.md §12 "data flow" says results are persisted "to SQLite (session)" — this revision clarifies session (files) and SQLite (app) are **separate** (§8). No conceptual change; IDEA.md will be reconciled when we touch it (not now).

---

## 16. Assumptions that still require build-time verification (no AWS needed for most)

1. **Graph concurrency / fan-in barrier.** Whether `intake` fan-out runs concurrently and whether a two-incoming-edge `join` waits for both. *Check:* build a tiny graph and inspect `GraphResult.execution_order`. *Fallback:* run Coach outside the graph (§4). — **does not need a billable call beyond a normal evaluate.**
2. **`GraphState` fields** beyond `results` and `execution_order`. *Check:* read the installed `strands.multiagent.graph` source. — no AWS.
3. **Structured-output failure mode.** Exactly how the SDK signals malformed structured output (exception vs `None`) so the retry condition is correct. *Check:* SDK source + one live extractor call during Recipe 3. — one normal call.
4. **`FileSessionManager` storage layout** under `/mnt/c` (DrvFs) — writing session files on the Windows mount. *Check:* a local file write test. — no AWS. (Operational, handled as during init; not a design change.)
5. **Evidence-span substring grounding** robustness (normalisation of whitespace/case/Unicode for Tamil later). *Check:* unit tests. — no AWS.
6. **`BeforeModelCallEvent` availability inside a graph node's agent** (the kit tested it on a standalone Agent). *Check:* attach the hook to the graph via `set_hook_providers` or per-agent and confirm it fires. — one normal call.

---

## 17. Out of scope this week (stretch)

Voice (Nova Sonic / Transcribe `ta-IN`) · Tamil as first-class MVP · Bedrock Guardrails · spaced revision · richer taxonomy · consented field study · hosted deployment — only with explicit cost approval.

---

## 18. Beyond the workshop (one sentence)

The workshop ends at multi-agent swarms; CareerLift goes past that with a **code-owned, four-band scorer whose language-fairness is a measured, honestly-bounded offline property** — not an opaque model verdict and not a hand-off chatbot.

---

## 19. Rubric sanity check (1–10)

| Quarter | Score | Why |
|---|---|---|
| Social impact | 8 | specific underserved group; dataset-measurable harm |
| Technical execution | 9 | verified SDK primitives only, bounded graph, fail-closed deterministic verifier, honest fairness bounds, tight call budget |
| Communication | 8 | one vivid demo + a single generated headline number |
| Originality | 9 | measured fairness gap on dual-axis scoring, past a plain swarm |
| Buildable in days left | 7 | core is a small graph + Python; main risk is authoring a good signed paraphrase-paired dataset |

No quarter below 6; design stands.

---

*Next (requires approval): "build the agent" — Recipe 3. That step writes code and will later make Bedrock calls via `ss bedrock` / `ss measure`, which need your explicit go-ahead because they incur AWS charges.*
