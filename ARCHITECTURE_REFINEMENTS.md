# CareerLift AI — Architecture Refinements

*Focused pre-implementation refinement of `PRODUCT_ARCHITECTURE_BLUEPRINT.md`. Resolves five areas:
Learning-Intelligence evidence quality, Assessment security, Coding-Arena security, Student-data
security, and Integration contracts. Documentation only — no source file was modified, the original
blueprint is unchanged, and this is the only new file created in this phase.*

> Invariants carried forward (non-negotiable):
> - `agent/fairscore.py` is the sole authority for interview/communication bands; the model never emits a score.
> - Identity is server-generated; auth is a bearer token stored only as `SHA-256(token + pepper)`.
> - Tables extend via the idempotent `db._migrate` pattern — never dropped/recreated.
> - Deterministic tasks use deterministic code, not an agent.
> - No fabricated statistics; insufficient evidence is shown honestly.
> - `bedrock` and `mock` model modes stay first-class and never switch silently.

---

## 1. Learning Intelligence — evidence quality

### 1.1 Problems identified
- The blueprint's "recency-weighted success rate" could let a **single** correct answer imply mastery.
- "Mastery ∈ [0,1]" risks being rendered as an **arbitrary percentage** with no denominator.
- No defined floor for "not enough evidence," so empty/thin data could masquerade as a real label.
- Signal strength was undifferentiated across very different evidence sources (a guessed MCQ vs a
  grounded interview misconception are not equal).

### 1.2 Decisions

**Evidence strength per source (weight + what counts as evidence).**
A SkillSignal carries a `strength` derived deterministically from its source and outcome. Strength is a
small ordinal (not a probability), used only to gate labels and order recommendations.

| Source | Evidence that must exist | Strength | Notes |
|---|---|---|---|
| **MCQ (Assessment)** | chosen option + correct key + `concept_id` | **weak** for a single item | MCQs are guess-prone (25% baseline for 4-option); treat one item as low signal |
| **MCQ, known distractor** | chosen a curated misconception distractor | **medium (misconception)** | a distractor mapped to a misconception is a demonstrated wrong belief |
| **Coding** | hidden+visible test pass ratio for a problem tagged with the concept | **medium** (all pass) / **strong** (all pass twice on distinct problems) | passing tests is harder to fake than an MCQ |
| **Interview (technical)** | FairScore `supported` claim with grounded evidence span | **medium** | reuses the existing verifier; grounding required |
| **Interview, grounded incorrect** | FairScore grounded `incorrect` matched to a signature | **strong (misconception)** | the strongest negative signal we have |
| **System design** | rubric points addressed with grounded evidence | **medium** per rubric area | coverage, not correctness proof |

**Why one correct answer cannot establish mastery.** A single success is consistent with guessing
(MCQ), copying, or a lucky recall. Mastery is a claim about *reliability over varied contexts*, so it
requires **independent** successes — ideally across more than one problem/question and, where possible,
more than one module.

**Minimum evidence before any mastery label.** A concept stays **"Not enough evidence"** until it has at
least **3 independent successful signals** of combined strength ≥ a threshold, where "independent" means
distinct items (different MCQ ids, different problems, different interview questions). A single strong
signal may move a concept to **"Emerging,"** never to **"Proficient."**

**Mastery is a LABEL, not a percentage.** Mastery is reported as one of:
`Not enough evidence → Emerging → Developing → Proficient → Strong`.
If any numeric figure is shown, it is a **real ratio with its denominator visible** (e.g. "7/9 recent
attempts correct"), never a synthesized score. The internal `mastery` float is an ordering aid only and
is never surfaced as a bare percentage.

**How repeated successes/failures move the label.**
- Successes: each independent success of sufficient strength advances the label by at most one step;
  advancing to **Proficient**/**Strong** requires successes across ≥2 distinct items and recent activity.
- Failures: a `struggled` signal drops the label by one step; a **grounded misconception** forces the
  concept to **Developing** at most (never Proficient) and opens a misconception record.
- The computation is **monotone and explainable**: given the ordered signal list, the label is a pure
  function of it (recomputable, auditable).

**Confidence & recency in recommendations.**
- `confidence` = a deterministic function of (count of independent signals, their strength, agreement).
  Low confidence never yields a confident label; it yields "Not enough evidence" + a recommendation to
  gather more.
- `recency`: signals older than a configurable window are **down-weighted** for recommendation ranking
  (so stale mastery resurfaces for revision) but are **never deleted** from evidence.
- Recommendation order: (1) open misconceptions, (2) low-confidence/low-mastery prerequisites for the
  goal, (3) spaced-repetition items whose interval has elapsed.

**How misconceptions are resolved.** A misconception opens on a grounded `incorrect` (interview) or a
chosen known-distractor (MCQ). It is marked **resolved** only after **N consecutive successful,
independent signals on that concept with no recurrence** (default N=2, configurable), with the resolving
evidence recorded. Resolution is reversible: a later recurrence reopens it (counts reset).

**Representing insufficient evidence.** Explicit `Not enough evidence` label everywhere, plus the real
counts ("2 attempts so far — need 1 more to assess"). No module may infer a label the evidence floor
does not support.

### 1.3 Revised contract additions
`SkillSignal` gains `strength` (weak|medium|strong) and `independent_key` (the distinct item id used to
prevent double-counting — see §5). `learner_concept` gains `label`, `confidence`, `independent_success_count`,
and `evidence_count`, all **derived** (rebuildable from `skill_signal`).

---

## 2. Assessment security

### 2.1 Problems identified
- An assessment catalog/question endpoint could leak the answer key or explanation before submission.
- Timing could be client-controlled (easy to bypass).
- Replays / duplicate submissions could inflate results.
- Ownership of an attempt must be enforced, like every other resource.

### 2.2 Decisions & requirements

**Answer keys never leave the server pre-submission.**
- Storage: `question_mcq` keeps `stem`, `options_json`, `answer_index`, `explanation_md`, `concept_id`,
  `distractor_misconceptions_json`. The **delivery DTO** to the client includes only `question_id`,
  `stem`, and `options` (text, in randomized display order per attempt). `answer_index`, `explanation`,
  and distractor mappings are **omitted by the Pydantic response model** (mirroring the existing
  "no internal ids leaked" discipline).
- Explanations are returned **only** in the post-submission result, per question.

**Attempt ownership.** `attempt.student_id` is set from the **authenticated token owner** (never a body
field). Every `/assessments/{id}/...` and `/attempts/{id}/...` route authorizes `attempt.student_id ==
current_student`, returning 403 otherwise — identical to the existing `_authorize_path_student` pattern.

**Server-side grading only.** The client submits `{attempt_id, [{question_id, chosen_index}]}`. The
server compares against `answer_index` in the DB and computes the score. The client never sends or sees
correctness until the graded result. Grading is deterministic Python (no model).

**Server-controlled timing.**
- On `POST /assessments/{id}/start`, the server stores `started_at` and the assessment's `time_limit_s`,
  and returns a server-computed `deadline`. The timer shown in the UI is advisory.
- On submit, the server validates `now <= started_at + time_limit_s + grace`. Late submissions are
  accepted but **flagged** (`late=true`) and may be scored per policy (e.g. graded but marked), never
  silently trusted to client time.

**Duplicate submission / replay handling.**
- An `attempt` has a lifecycle: `in_progress → submitted`. `submit` is **idempotent on first success**:
  once `submitted_at` is set, further submits return the **existing** result (HTTP 409 or the stored
  result, by policy) and never re-grade or create a second attempt.
- One active attempt per (student, assessment) unless the assessment explicitly allows retakes; retakes
  create a **new** `attempt` row (history preserved), never overwrite.
- Per-question answers are keyed by `(attempt_id, question_id)` unique → replaying an answer updates
  nothing after submission.

**Prerequisites:** randomized option order stored per attempt (so a submitted `chosen_index` maps back
correctly); a server clock is the only timing authority.

---

## 3. Coding Arena security

### 3.1 Problems identified
- Executing untrusted student code is the single highest risk in the whole platform.
- Hidden test cases must never be exposed via run output or error messages.
- A crashing/hanging execution service must not take down the API.

### 3.2 Decisions & requirements (hard rules)

**Isolation between API and executor.** The execution engine is a **separate service/process** (`exec/`),
never imported or `exec()`'d inside FastAPI. The API talks to it over a narrow local interface
(`{language, code, testcases}` in → `{per_case results}` out). The API process holds no capability to run
arbitrary code; the executor holds no app/DB credentials.

**Container security configuration (per run):**
- **No network** (`--network none`).
- **Non-root** user; drop all Linux capabilities; `--read-only` root filesystem; a small writable `tmpfs`
  scratch mount only.
- `--pids-limit`, `--memory`, `--cpus`, and a **wall-clock timeout** enforced by the orchestrator (kill
  on overrun).
- **Output caps**: stdout/stderr truncated to a fixed size; oversized output = failure, not a dump.
- Ephemeral container per run; **destroyed** after each run (`--rm`), no reuse across students.

**Hidden test-case protection.**
- `testcase.is_hidden=true` cases: their **inputs/expected outputs are never sent to the client**. The
  `run` endpoint executes only **visible** cases and returns their diffs; `submit` executes all cases but
  returns only **pass/fail counts** for hidden ones (never the hidden input/expected/stdout).
- Executor returns only `{case_id, passed, time_ms, truncated_stdout_for_visible_only}`; the API strips
  anything hidden before responding.

**Temporary file cleanup.** Each run uses a fresh scratch dir inside the container's tmpfs, destroyed
with the container. The orchestrator also sweeps orphaned containers/dirs on a timer and on startup
(defensive), so a crash cannot leak student code to disk.

**Student-code execution restrictions.** No network, no filesystem outside scratch, no access to other
students' data, no host env vars, no long-running processes (time-limited), no fork bombs (pid limit).
SQL "execution" (for SQL assessments) runs against a throwaway in-memory/temp database seeded per run,
never the app DB.

**Execution-service failure handling.** If the executor is down, times out, or errors, the API returns a
clean **503 "code execution is temporarily unavailable"** (same pattern as the model 503), never a 500
and never a fabricated verdict. Submissions are not recorded as passed/failed on infrastructure failure;
they are recorded as `verdict=error` and retriable.

**Security tests required before any public demo (gating checklist):**
1. Network egress blocked (attempt a socket/HTTP call → fails).
2. Filesystem escape blocked (write outside scratch → denied; app files unreadable).
3. CPU/memory/time/pids limits enforced (infinite loop, fork bomb, memory bomb all killed within limits).
4. Output flood truncated, not OOM.
5. Hidden test inputs/outputs never present in any `run`/`submit` response.
6. One run cannot observe another run's files or data (isolation between concurrent runs).
7. Executor crash → API returns 503, stays up; orphan cleanup verified.
8. No host credentials/secrets reachable from inside a container.

Until all eight pass, the Coding Arena stays behind a flag and is not demoed.

---

## 4. Student data security

### 4.1 Decisions & requirements

**Authentication / authorization.** Keep the existing model: server-generated `student_id`, bearer
token, `SHA-256(token + pepper)` stored (plaintext never persisted or logged), `current_student`
dependency resolves identity from the token. Every protected route depends on it.

**Ownership on every resource.** A single rule applies to all new entities (sessions, submissions,
attempts, sd_submissions, skills, activity): the row's `student_id` must equal the authenticated owner,
or **403**. Identity is **always** taken from the token, never from a path/body field. This is enforced
in one shared dependency so no module reinvents it.

**Access control specifics.**
- Submissions (code), interview transcripts/answers, assessment attempts, and design responses are all
  per-student and owner-only. No cross-student read, ever. No public listing endpoints.
- Admin/content endpoints (if any) are a separate concern and out of scope for the student token.

**Data retention & deletion.**
- Provide a **delete-my-data** path (per student): removes `student`, `auth_token`, and all owned rows
  (interviews, answers, sessions, submissions, attempts, sd_submissions, skill_signal, learner_concept,
  activity_event) in a transaction. Because `learner_concept` is derived, deleting signals is sufficient
  for the model; the derived cache is dropped too.
- Retention default for the local prototype: data persists until the student deletes it or the local DB
  is reset. Document that this is a local prototype, not a managed data store.

**Token protection.** Tokens are shown once at registration, stored hashed, sent only over the
`Authorization` header, never logged, never returned again, never placed in URLs. Frontend keeps the
token in `localStorage` for the local prototype (documented limitation); logout clears it.

**Safe handling of student code & interview responses.**
- Student code is executed only in the sandbox (§3), not stored on the host outside the DB submission
  row; the DB stores the code text the student submitted (owner-only).
- Interview responses: the existing **PII input gate** rejects phone/email/id-number content before any
  model call; this applies to every text-answer surface (interview, behavioral, system-design response).
  Raw audio (voice) is **not** stored server-side — only the transcript text, like a typed answer.
- Logs must never contain tokens, full student code, or full answers at info level (reference by id).

---

## 5. Integration contracts (SkillSignal / LearnerModel / Recommendation)

### 5.1 Problems identified
- Without a dedup key, replays or double-writes could inflate mastery.
- Provenance and evidence must be explicit and auditable.
- Modules could drift into inventing their own scoring/mastery rules.

### 5.2 Revised contracts

**One shared concept taxonomy.** All modules key to the existing concept-id space (`agent/data/concepts.json`),
extended carefully as modules add concepts. No module invents ad-hoc concept ids; adding a concept is a
reviewed change to the shared reference. A signal with an unknown `concept_id` is rejected (fail-closed),
mirroring the verifier's id-validity rule.

**SkillSignal (append-only, immutable):**
```
skill_signal(
  id,                      # surrogate
  student_id,              # owner (from token, authorized)
  concept_id,              # MUST exist in the shared taxonomy
  source_module,           # interview | coding | assessment | sysdesign | behavioral
  outcome,                 # mastered | partial | struggled | misconception
  strength,                # weak | medium | strong   (deterministic per source/outcome, §1.2)
  confidence,              # derived numeric aid, not shown as a %
  evidence_ref,            # pointer to the producing artifact (answer id / submission id / attempt_answer id / sd_submission id)
  independent_key,         # distinct-item key for dedup (e.g. "coding:two-sum", "mcq:Q123", "iv:session7:q2")
  dedup_key,               # UNIQUE: hash(student_id, source_module, evidence_ref, outcome)
  created_at
)
```
- **Duplicate events do not inflate mastery:** `dedup_key` is UNIQUE; re-emitting the same evidence is a
  no-op insert. Mastery counts "independent successes" by **distinct `independent_key`**, so three
  passes of the *same* problem count once toward independence.
- **Explicit provenance:** every signal carries `source_module` + `evidence_ref`, so any mastery label
  can be traced to the exact artifacts that produced it.

**LearnerModel (`learner_concept`, fully derived & rebuildable):**
```
learner_concept(
  student_id, concept_id,
  label,                     # Not enough evidence | Emerging | Developing | Proficient | Strong
  confidence,
  evidence_count,
  independent_success_count,
  open_misconception,        # bool
  last_seen,
  updated_at
)
```
- Pure function of that student+concept's `skill_signal` rows. A `rebuild(student)` recomputes it from
  scratch — the cache can be dropped and regenerated, so it is never a second source of truth.

**Recommendation (always explainable):**
```
Recommendation(
  action,                    # "practice" | "revise" | "assess" | "learn"
  target_module, target_ref, # where to go
  concept_id,
  reason,                    # human-readable WHY (required, non-empty)
  priority,                  # derived: misconception > low-confidence prereq > spaced-due
  evidence_summary           # the counts behind the reason (real numbers, with denominators)
)
```
- Every recommendation **must** carry a non-empty `reason` and an `evidence_summary` of real counts.
  The existing planner already returns a `reason`; this formalizes it for all modules.

**FairScore remains the authority.** Interview and any human-language evaluation produce bands **only**
via `agent/fairscore.py`. Modules emit SkillSignals *from* FairScore output; they never compute their own
bands. Deterministic modules (MCQ, coding verdicts) compute pass/fail deterministically and map to
signals via the fixed table in §1.2 — they do not define new "scoring rules," only the agreed mapping.

**No module invents mastery or scoring.** Mastery labels are computed in one place (`agent/skills/learner_model.py`,
per the blueprint) from signals; scoring bands live in one place (`fairscore.py`). A module that needs a
new outcome type proposes it as a reviewed change to these shared contracts, not a local override.

---

## 6. Updated implementation prerequisites (before Phase 0)

1. **Freeze the shared contracts** (SkillSignal, LearnerConcept, Recommendation fields above) so all
   phases build against stable shapes.
2. **Define the mastery label state machine** (thresholds N, evidence floor, step rules) as a small,
   unit-tested pure function before any module emits signals.
3. **Decide the dedup/independence keys** per source (the `independent_key` format for coding, MCQ,
   interview, sysdesign) — these must be stable, since mastery independence depends on them.
4. **Assessment delivery DTO** that structurally cannot include `answer_index`/`explanation` (enforced by
   the Pydantic response model, not by discipline alone).
5. **Code-execution security checklist (§3.2, 8 items)** must be the Phase-2 definition of done; Coding
   Arena stays flagged until it passes.
6. **Shared ownership dependency** (one `require_owner(resource)` helper) so every new router authorizes
   identically to the existing pattern.
7. **Delete-my-data transaction** designed alongside the new tables (not bolted on later).
8. **Taxonomy change process**: adding a concept id is a reviewed edit to the shared reference; signals
   with unknown ids are rejected.
9. **Keep both model modes working** for every model-assisted feature, with deterministic fallbacks and a
   clean 503 when unavailable.

---

## 7. Unresolved questions (decide before/at Phase start)

1. **Resolution threshold N** for misconceptions (default 2) and the **evidence floor** (default 3
   independent successes) — confirm values; they shape how quickly labels move.
2. **Recency window** length for down-weighting stale mastery (and whether it differs per module).
3. **Retake policy** per assessment (single attempt vs unlimited retakes; how retakes affect mastery —
   recommend: each retake's items count by their own `independent_key`).
4. **Late-submission policy** for timed assessments (grade-and-flag vs reject after grace).
5. **Sandbox substrate** final choice (container-per-run recommended) and the **initial language set**
   (recommend Python + one more) — bounds the Phase-2 security surface.
6. **Voice STT** choice and its privacy disclosure (browser Web Speech vs local Whisper) — affects what
   data (if any) leaves the device.
7. **Cross-module independence**: should a success in a *different* module count as independent evidence
   toward the same concept's mastery? (Recommend: yes, with its own `independent_key`, since varied
   contexts strengthen a mastery claim.)
8. **Confidence surfacing**: exactly how `confidence` is shown to students without implying a fabricated
   number (recommend: words + real counts, never a bare %).

---

## 8. Summary of problems → decisions

| Area | Problem | Decision |
|---|---|---|
| Learning Intelligence | single answer → "mastery"; arbitrary % | evidence floor (≥3 independent), label states, real-ratio-only numbers, source-weighted strength |
| Assessment | key leakage, client timing, replays | server-only grading, key omitted from DTO, server clock, idempotent submit, owner-checked attempts |
| Coding Arena | untrusted code; hidden-case leaks | separate sandbox service, no-network containers, strict limits, hidden cases never returned, 8-item security gate |
| Student data | ownership, tokens, retention | token-owner authorization everywhere, hashed tokens, delete-my-data, PII gate on all text, no server-side audio |
| Integration | dedup, provenance, drift | UNIQUE `dedup_key`, `independent_key`, explicit provenance, derived rebuildable LearnerModel, FairScore sole authority |

*End of refinements. No existing source files were modified; the original `PRODUCT_ARCHITECTURE_BLUEPRINT.md`
is unchanged; `ARCHITECTURE_REFINEMENTS.md` is the only file created in this phase. No implementation was
started.*
