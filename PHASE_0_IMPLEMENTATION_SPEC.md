# CareerLift AI — Phase 0 Implementation Specification

**Phase 0 — Learning Intelligence Foundation + Unified Career Dashboard**

*Implementation-ready spec derived from `ARCHITECTURE_AUDIT.md`, `PRODUCT_ARCHITECTURE_BLUEPRINT.md`, and
`ARCHITECTURE_REFINEMENTS.md`, grounded in the actual code in `agent/` and `frontend/`. Documentation
only — no source was modified to produce it. This is the single new file created in this phase.*

> Hard invariants (enforced in every task below):
> - `agent/fairscore.py` stays the sole authority for interview/communication bands; the model never scores.
> - New tables/columns are added via the existing idempotent `db._migrate` pattern — never drop/recreate.
> - Identity is the authenticated token owner (`api/auth.py:current_student`); 403 on any mismatch.
> - Deterministic tasks (mastery, dedup, ranking, activity) are plain Python — no agent, no model, no AWS.
> - No fabricated numbers: labels + real ratios only; "Not enough evidence" is a first-class state.
> - `bedrock`/`mock` modes unchanged; Phase 0 adds **zero** model calls of its own.

---

## 1. Exact implementation scope

**In scope (Phase 0):**
- Backend: SkillSignal service, LearnerModel (derived + rebuildable), Recommendation engine, Activity
  service, new additive SQLite tables + migration entries, two new API routers (`learning`, `dashboard`),
  a shared ownership dependency, and a one-time **backfill** of existing `answer` rows into SkillSignals.
- Frontend: evolve the existing `Dashboard.jsx` into a unified Career Dashboard that consumes the new
  recommendation/skills/overview/activity endpoints, adds a concept-mastery visualization and an activity
  calendar, and folds the existing Progress / Misconceptions / Reports pages in as linked tabs (kept, not
  replaced). Navigation is extended without breaking existing routes.

**Explicitly OUT of scope for Phase 0** (later phases): Coding Arena, Assessments, System Design, Voice,
multi-question interview sessions. Phase 0 reads only data the current system already produces (interview
answers + misconceptions), plus the new derived model/activity.

---

## 2. Existing files to REUSE (unchanged)

Backend:
- `agent/fairscore.py` — misconception source of truth; mapping of its outputs → signals.
- `agent/db.py` — `connect()`, `_now()`, `init_db()`, `_migrate()`, `_EXPECTED_COLUMNS`, existing
  accessors (`interview_history`, `misconception_tally`, etc.). New functions are **added** here.
- `agent/config.py` — mode switch (Phase 0 is deterministic; no model path touched).
- `api/auth.py` — `current_student` dependency and the authorization pattern (`_authorize_path_student`).
- `agent/data/concepts.json` — the shared concept taxonomy + misconception definitions.
- `agent/planner.py` — existing deterministic planner; Phase 0's recommender generalizes it (the
  existing `/next` becomes a thin wrapper, see §6/§7).

Frontend:
- `frontend/src/components/ui.jsx` — `Card`, `SectionHeading`, `Spinner`, `LoadingBlock`, `EmptyState`,
  `ErrorState`, `Badge`, `BandBar`, `BandGauge` (reused as-is).
- `frontend/src/components/AppLayout.jsx`, `Logo.jsx`, `ProgressChart.jsx`.
- `frontend/src/api/client.js`, `frontend/src/lib/useApi.js`, `frontend/src/context/AuthContext.jsx`,
  `frontend/src/lib/content.js`.
- `frontend/src/pages/Progress.jsx`, `Misconceptions.jsx`, `Reports.jsx` — reused as Dashboard tab bodies.

---

## 3. New files to CREATE

Backend:
```
agent/skills/__init__.py
agent/skills/signals.py        # SkillSignal write/read + dedup + taxonomy validation
agent/skills/learner_model.py  # deterministic mastery state machine (pure, unit-testable)
agent/skills/recommend.py      # deterministic ranking + explanation contract
agent/skills/backfill.py       # one-time, idempotent import of existing answers -> signals
agent/activity.py              # activity-event write/read (streaks, calendar)
api/routers/__init__.py
api/routers/learning.py        # /students/{id}/skills, /recommendations, /next (rewrapped)
api/routers/dashboard.py       # /students/{id}/overview, /activity
api/deps.py                    # shared require_owner(student_id) dependency (one place)
```

Frontend:
```
frontend/src/pages/dashboard/CareerDashboard.jsx   # evolved home (wraps existing tabs)
frontend/src/components/MasteryPanel.jsx           # concept mastery visualization (labels, not fake %)
frontend/src/components/ActivityHeatmap.jsx        # activity calendar (SVG/recharts, real events)
frontend/src/components/RecommendationList.jsx     # ranked recommendations with reasons
frontend/src/lib/mastery.js                        # label -> colour/copy helpers (mirror of content.js style)
```

Tests:
```
tests/test_skill_signals.py
tests/test_learner_model.py
tests/test_recommend.py
tests/test_activity.py
tests/test_backfill.py
tests/test_learning_api.py        # mock-mode + ownership + zero-AWS
tests/test_dashboard_api.py
```

---

## 4. Existing files requiring ADDITIVE modifications (no rewrites)

Each change is strictly additive and agreed per this spec; nothing existing is removed or rewritten.

| File | Additive change |
|---|---|
| `agent/db.py` | Append new `CREATE TABLE IF NOT EXISTS` blocks to `SCHEMA`; add new columns (if any) to `_EXPECTED_COLUMNS`; add new accessor functions (signals, learner_concept, activity). Existing tables/functions untouched. |
| `api/main.py` | (a) `from api.routers import learning, dashboard` + `app.include_router(...)` for each; (b) **one smallest-possible additive edit to the existing `/score` route**: after the answer is successfully persisted (`db.record_answer(...)`), add emission of SkillSignals + activity (§8.1). This is additive only — the scoring call, FairScore result, `ScoreResponse` schema, status codes, PII gate, and authorization are **unchanged**; emission runs *after* persistence and is wrapped so a failure cannot alter the response (§8.1). No existing line of scoring logic is rewritten or removed. |
| `agent/planner.py` | `next_exercise` delegates to `agent/skills/recommend.top()` so there is one ranking source, and adapts the result into the existing `NextExerciseResponse` shape. The **existing `/next` route on `app` is NOT moved or duplicated** (§7.3); only `planner.next_exercise`'s body is additively updated. |
| `frontend/src/App.jsx` | Add routes for the dashboard tabs/new components; keep every existing route working. |
| `frontend/src/components/AppLayout.jsx` | Group nav; existing entries remain and still route to existing pages. |
| `frontend/src/api/client.js` | Add methods: `skills`, `recommendations`, `overview`, `activity`. |

---

## 5. Database schema (additive migration)

Add to `agent/db.py` `SCHEMA` (idempotent `CREATE TABLE IF NOT EXISTS`):

```sql
CREATE TABLE IF NOT EXISTS skill_signal (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    concept_id      TEXT NOT NULL,              -- MUST exist in the shared taxonomy
    source_module   TEXT NOT NULL,              -- 'interview' (Phase 0); later: coding|assessment|sysdesign|behavioral
    outcome         TEXT NOT NULL,              -- mastered | partial | struggled | misconception
    strength        TEXT NOT NULL,              -- weak | medium | strong
    confidence      REAL NOT NULL DEFAULT 0,    -- ordering aid only; never shown as a bare %
    evidence_ref    TEXT,                       -- e.g. 'answer:42'
    independent_key TEXT NOT NULL,              -- distinct-item key for independence, per concept (e.g. 'iv:answer:42:C-HASH-AVG')
    dedup_key       TEXT NOT NULL UNIQUE,       -- sha256(student_id|source_module|evidence_ref|concept_id|outcome)
    created_at      TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_signal_student_time ON skill_signal(student_id, created_at);
CREATE INDEX IF NOT EXISTS idx_signal_student_concept ON skill_signal(student_id, concept_id);

CREATE TABLE IF NOT EXISTS learner_concept (
    student_id                TEXT NOT NULL,
    concept_id                TEXT NOT NULL,
    label                     TEXT NOT NULL,    -- Not enough evidence|Emerging|Developing|Proficient|Strong
    confidence                REAL NOT NULL DEFAULT 0,
    evidence_count            INTEGER NOT NULL DEFAULT 0,
    independent_success_count INTEGER NOT NULL DEFAULT 0,
    open_misconception        INTEGER NOT NULL DEFAULT 0,
    last_seen                 TEXT,
    updated_at                TEXT NOT NULL,
    PRIMARY KEY (student_id, concept_id),
    FOREIGN KEY (student_id) REFERENCES student(id)
);

CREATE TABLE IF NOT EXISTS activity_event (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    kind          TEXT NOT NULL,                -- 'interview_scored' | 'misconception_opened' | 'misconception_resolved' | ...
    ref_id        TEXT,
    event_key     TEXT NOT NULL UNIQUE,         -- idempotency key; formula depends on kind (see §8.1)
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_activity_student_time ON activity_event(student_id, created_at);
```

**Migration rules:** `learner_concept` is a **derived cache** — safe to drop and rebuild from
`skill_signal`. `_migrate()` already runs after `CREATE TABLE IF NOT EXISTS`; add any new columns on
existing tables to `_EXPECTED_COLUMNS` (none required for Phase 0 — all new tables). Existing rows in
`student`/`interview`/`answer`/`misconception` are preserved; a fresh and an older DB both converge.

---

## 6. Mastery algorithm and state transitions (deterministic, reversible)

### 6.1 Signal mapping (fixed; exhaustive over the evaluator's actual outputs)
Phase 0 has exactly one source — the **interview** — and reuses the evaluator's persisted per-concept
status plus the misconception tags it produced. The evaluator's per-concept status vocabulary is
`supported | partial | absent` (the verifier's `best_status`), and it emits grounded misconception tags
for demonstrated `incorrect` assertions. **Every** possible output maps as follows — nothing else exists:

| Evaluator output (persisted) | SkillSignal outcome | strength | Emitted? |
|---|---|---|---|
| **persisted per-concept** `supported` (grounded) | `mastered` | medium | yes — only when per-concept evidence is stored |
| **persisted per-concept** `partial` | `partial` | weak | yes — only when per-concept evidence is stored |
| per-concept `absent` | — | — | **no signal** (missing knowledge is neither skill evidence nor a gap) |
| a grounded misconception tag present for a concept | `misconception` | strong | yes (one per tag's concept) |
| overall technical band only (no per-concept detail) | — | — | **no `mastered`/`partial` signal** (a band does not demonstrate each concept) |
| answer abstained / rejected (PII) | — | — | **no signal** (nothing was assessed) |

- There is **no `struggled` signal in Phase 0.** The evaluator does not produce one, so none is invented
  or emitted. The `struggled` *rule* in §6.3.3 exists only for future sources and is unreachable now.
- The mapping is applied identically by **live emission** (§8.1) and **backfill** (§9), so a historical
  answer and a freshly-scored answer yield the same signals.
- **Backfill reads only persisted historical results** (`answer` rows: `technical_band`/per-concept data
  as stored, `misconception_tags`). It **never** re-runs the model/evaluator. What was not persisted is
  simply not backfilled.

> **Granularity rule (corrected — no band-derived fallback).** An **overall technical band must never
> establish mastery of the individual expected concepts.** `mastered`/`partial` signals are emitted
> **only** when **actual persisted per-concept evaluation evidence** exists for that concept (i.e. a
> stored per-concept status such as `supported`/`partial` tied to the concept). A `Solid`/`Strong`
> overall band is **not** evidence that each expected concept was individually demonstrated, so it
> produces **no** per-concept `mastered`/`partial` signal.
>
> **Misconceptions are the exception and the only guaranteed per-concept signal from current data:** each
> grounded tag in the answer's stored `misconception_tags` maps (via the existing tag→concept map in
> `agent/fairscore.py`) to a `misconception` signal for that tag's concept.
>
> **Historical answers that stored only an overall band (no per-concept detail) therefore produce no
> `mastered`/`partial` signal at all** — only any misconception signals their stored tags imply. This is
> correct and honest: absence of per-concept evidence must not be upgraded into mastery.
>
> Consequence for Phase 0 data: with the current persisted schema, the reliably available per-concept
> signal is the **misconception** signal. If we want `mastered`/`partial` per concept going forward, the
> scorer must **persist per-concept status at scoring time** (a later, separate change — NOT done in
> Phase 0, NOT a backfill reconstruction). Backfill never reconstructs missing per-concept detail and
> never reruns the evaluator/model (§9).

(Future sources — coding/MCQ/sysdesign — slot into this same outcome set in later phases.)

### 6.2 Independence & deduplication
- `dedup_key = sha256(student_id | source_module | evidence_ref | concept_id | outcome)`, UNIQUE. The
  `concept_id` is part of the key **so that one answer covering several expected concepts produces one
  independent signal per concept** — not a single collapsed signal. Re-emitting the *same concept's* result
  for the *same answer* is a no-op insert (INSERT OR IGNORE). This keeps writes idempotent and
  backfill-safe while preserving multi-concept coverage.
- `independent_key` identifies the distinct item **per concept** (Phase 0: `iv:answer:<id>:<concept_id>`).
  Independence for a *given concept's* mastery counts **distinct `independent_key`s for that concept**, so
  re-scoring the same answer counts that concept once, while a second answer addressing the same concept
  adds genuine independent evidence.
- **Worked example:** answer #42 has `expected_concepts = [C-HASH-AVG, C-BIGO-WORSTCASE]` and FairScore
  marks the first `supported` and the second `partial`. Two signals are written —
  `dedup_key` = `…|answer:42|C-HASH-AVG|mastered` and `…|answer:42|C-BIGO-WORSTCASE|partial` — each
  advancing its own concept independently. Re-scoring answer #42 inserts neither again.

### 6.2.1 Same-evidence precedence (one answer, one concept → one non-contradictory outcome)
A single answer could, for the **same concept**, yield both a positive reading (`supported`) and a
grounded **misconception** (the student both touched the idea and stated something demonstrably wrong
about it). One evidence item must **not** produce contradictory positive and negative signals for the
same concept. Precedence rule:

- **Grounded misconception WINS for that (answer, concept).** When an answer produces a grounded
  misconception for concept C, that same answer emits a `misconception` signal for C and **does NOT** emit
  a `mastered`/`partial` signal for C. The answer's `independent_key` for C is therefore **not** counted
  as a positive independent success — a misconception cannot also count as mastery evidence from the same
  item.
- Concretely, at emission/backfill time: compute the concept's misconception tags first; for any concept
  with a grounded misconception tag **on this answer**, suppress that concept's positive signal from the
  same answer. Other concepts on the same answer are unaffected (the multi-concept rule, §6.2, still
  holds).
- **Legitimate evidence from separate answers is preserved.** A later, *different* answer that genuinely
  demonstrates C with `supported` is a new `independent_key` and counts as a real independent success —
  and, per §6.3, contributes toward resolving the misconception. Precedence is per-answer, not permanent.
- This keeps the invariant: for a given `(answer, concept)` there is **at most one** mastery-relevant
  outcome, and it is the negative one when a grounded misconception exists.

### 6.3 Mastery label state machine (pure function of a concept's ordered signals)

States (ordinal): `Not enough evidence`(0) → `Emerging`(1) → `Developing`(2) → `Proficient`(3) → `Strong`(4).

Constants (defaults; confirm in §14):
- `EVIDENCE_FLOOR = 3` — independent successes required to reach `Proficient`.
- `STRONG_FLOOR = 5` — independent successes required to reach `Strong` (explicit; no vague "sustained").
- `RESOLVE_N = 2` — consecutive independent successes (no intervening misconception) to resolve a misconception.
- `RECENCY_WINDOW_DAYS = 30` — used by **recommendation ranking only**, never by the label (see §6.3.4).

#### 6.3.1 Chronological ordering & deterministic tie-breaking
The label is a pure function of that concept's `skill_signal` rows evaluated **in ascending
`(created_at, id)` order**. `created_at` is the primary key of order; `id` (the autoincrement surrogate)
is the deterministic tie-breaker when timestamps are equal. Because `id` is strictly increasing and
unique, ordering is total and reproducible regardless of insert interleaving or equal timestamps.

#### 6.3.2 Per-concept accumulators (reset to these at the start of every evaluation/rebuild)
```
label_ordinal              = 0          # Not enough evidence
independent_success_keys   = set()      # distinct independent_key of mastered signals counted
evidence_count             = 0          # all non-ignored signals seen for the concept
open_misconception         = False
resolve_streak             = 0          # consecutive independent mastered since last misconception
last_seen                  = None       # created_at of the most recent signal
```

#### 6.3.3 Transition rules (applied once per signal, in order)
For each signal `s` (fields: `outcome`, `independent_key`, `created_at`):
`evidence_count += 1`; `last_seen = s.created_at`.

- **outcome = mastered**
  - If `s.independent_key` is **new** for this concept (a genuine, not-yet-counted independent success):
    - add it to `independent_success_keys`; `isucc = len(independent_success_keys)`.
    - If `open_misconception`: `resolve_streak += 1`.
      - If `resolve_streak >= RESOLVE_N`: `open_misconception = False`; `resolve_streak = 0`; record a
        `misconception_resolved` transition at **this signal's id** (collected in the transition list,
        §6.3.8). The cap is lifted.
    - Recompute `label_ordinal` from `isucc` via the **ladder** (§6.3.5), then apply the open-misconception
      cap (§6.3.6).
  - If `s.independent_key` is **NOT new** (a duplicate of an already-counted success for this concept):
    **no change to independence, no change to `resolve_streak`, no change to `label_ordinal`.** A duplicate
    must neither advance nor reset the resolution streak. (It still increments `evidence_count` only.)

- **outcome = partial**
  - Never advances independence and never raises the label.
  - **If `open_misconception` is True, a `partial` is an intervening non-success and RESETS
    `resolve_streak = 0`** — resolution requires *genuinely consecutive* independent `mastered` signals,
    so any intervening `partial` (or any non-mastered evidence) breaks the run.
  - If `label_ordinal == 0` and at least one partial has been seen, the label becomes `Emerging`(1); it
    never exceeds `Emerging` on partials alone.

- **outcome = misconception** (applies to EVERY grounded misconception signal — initial open OR recurrence)
  - `resolve_streak = 0` (always reset).
  - Record a `misconception_opened` lifecycle event at **this signal's id** — **unconditionally**, whether
    `open_misconception` was already True (recurrence) or False (initial open). This does **not** depend on
    a Boolean state flip; it is driven by the signal itself (see §6.3.8).
  - Set `open_misconception = True` (it may already be True; that is fine — the event above is still
    recorded for this distinct signal).
  - Apply the cap: `label_ordinal = min(label_ordinal, 2)` (`Developing`). Prior demonstrated successes
    are **not** erased, but the label cannot read `Proficient`/`Strong` while open. (Mastery reversal.)

**Consecutive-resolution rule, stated plainly:** `resolve_streak` counts only **new independent
`mastered`** signals since the misconception (re)opened. It is incremented solely by a new-key `mastered`,
and reset to 0 by **any** of: a `misconception` signal, a `partial` signal, or (future) a `struggled`
signal. A duplicate already-counted `mastered` does nothing to it. Resolution fires exactly when the
streak reaches `RESOLVE_N` with no intervening reset.

- **outcome = struggled**
  - *Phase 0 note:* the current evaluator does **not** emit `struggled` (see §6.1 and §9). The rule is
    defined for forward-compatibility only and is unreachable in Phase 0: a `struggled` signal would drop
    `label_ordinal` by one step, floored at `Emerging`(1) if any independent success exists, else `0`.

#### 6.3.4 Resolving the recent-activity vs recency-ranking conflict
The **label never depends on recency** — it is a pure function of the ordered signals only, so it is
reproducible forever (a 6-month-old Proficient stays Proficient on rebuild). Recency affects **only
recommendation ranking** (§7): a concept not practised within `RECENCY_WINDOW_DAYS` becomes *due* for
spaced revision and rises in the recommendation list, but its stored label does not change. This removes
the earlier conflict: "recent activity" is a ranking input, not a labelling input. `Proficient`/`Strong`
therefore require only the independence floors below, not a recency check.

#### 6.3.5 The success ladder (independent successes → label, before the cap)
```
isucc >= STRONG_FLOOR (5)  -> Strong (4)
isucc >= EVIDENCE_FLOOR(3) -> Proficient (3)
isucc == 2                 -> Developing (2)
isucc == 1                 -> Emerging (1)
isucc == 0                 -> keep current (0, or Emerging if a partial was seen)
```
This ladder is monotonic in `isucc`; combined with the fixed ordering it guarantees determinism.

#### 6.3.6 Open-misconception cap
After computing the ladder value, if `open_misconception` is True, `label_ordinal = min(label_ordinal, 2)`.
When the misconception resolves, the cap is removed and the next recompute reflects the full ladder value.

#### 6.3.7 Reversibility & reproducibility — incremental IS a replay (Phase 0)
`learner_concept` is a **cache**, never the source of truth.

**Phase 0 decision (simplest + safest): there is no separate incremental algorithm. "Update" = "replay".**
On every new signal for a concept, `learner_model.update(student, concept_id)` performs exactly the same
work as `rebuild` for that concept: it resets the accumulators (§6.3.2) to their initial values and
replays **all** of that student+concept's `skill_signal` rows in `(created_at, id)` order through the
§6.3.3 state machine, then writes the resulting `learner_concept` row. Because `update` and `rebuild`
invoke the identical pure function over the identical ordered rows, their results are **identical by
construction** — there is no accumulator carried across calls that could drift.

- `independent_success_keys` and `resolve_streak` are therefore **never persisted or carried between
  calls**; they are rebuilt from scratch each replay from the ordered signals. (The `learner_concept`
  columns `independent_success_count`/`open_misconception` are outputs of the replay, not inputs.)
- Transition events are handled by the chronological collection in §6.3.8 (NOT by a before/after
  comparison of only the first and final state).
- Performance note: per-concept replay over a single student's signals is trivially cheap at Phase 0 data
  volumes; optimizing to a true incremental accumulator is explicitly **deferred** (not needed now).
- **A test asserts `update`-sequence result == one-shot `rebuild` result for every concept, across
  randomized insert orders and equal timestamps** (§11).

#### 6.3.8 Lifecycle-event collection during replay (every event, chronologically)
A single replay may contain **multiple** misconception **lifecycle events** — e.g. open → resolve →
reopen, or two consecutive misconception signals **while already open** (recurrence). The collector
records **misconception lifecycle events, not Boolean state flips**. This is the key correction: a
recurrence while already open is state `True → True`, so a flip-only rule would silently drop it. The
collector is therefore **signal-driven for opens and streak-driven for resolutions**, not flip-driven.

Rule — as the state machine processes signals in `(created_at, id)` order, it **appends** to an ordered
`events` list for the concept:
- **On every grounded `misconception` signal `s`** (initial open OR recurrence, regardless of current
  `open_misconception`): append `('misconception_opened', s.id, s.created_at)`. (Also resets
  `resolve_streak` and sets `open_misconception = True`, per §6.3.3.)
- **When a new-key `mastered` signal `r` completes `RESOLVE_N`** (the resolution moment): append
  `('misconception_resolved', r.id, r.created_at)`. Resolution events remain tied to the signal that
  completes the streak.

After the replay, `learner_model` offers **each** collected event to
`activity.record_transition(student, kind, signal_id)`. Because the activity `event_key` for these kinds
is keyed on the **triggering/resolving `skill_signal.id`** (§8.1):
- each distinct misconception signal produces its **own** `misconception_opened` event (two
  signals-while-open → **two** distinct events, keyed by their two distinct signal ids);
- each resolution produces its own event keyed by the resolving signal id;
- **re-running the whole replay re-offers the same (kind, signal_id) pairs → all INSERT OR IGNORE
  no-ops**, so repeating the replay persists **zero** additional events.

Net effect: the activity log is a faithful, idempotent projection of the signal history — one
`misconception_opened` per grounded misconception signal (opens **and** recurrences), one
`misconception_resolved` per completed resolution — derivable purely from `skill_signal`, never
duplicated on recompute. A `misconception_resolved` is **not** emitted on every new-key `mastered`, only
on the one that completes `RESOLVE_N`.

### 6.4 Confidence — EXCLUDED from Phase 0
`confidence` is **not computed or used** in Phase 0. The column exists in `skill_signal` and
`learner_concept` for forward-compatibility but is written as `0` and is **never** used for labelling,
ranking, or display in Phase 0. Recommendation ranking (§7) uses only misconception state, the label
ordinal, and recency — no confidence. This removes the earlier ambiguity.

### 6.5 Honest representation
- `GET /students/{id}/skills` returns the **label**, `evidence_count`, `independent_success_count`,
  `open_misconception`, and `last_seen` (no `confidence` surfaced in Phase 0).
- The UI shows the label + a real ratio (e.g. "independent successes: 2 / needs 3 for Proficient") and
  "Not enough evidence" below the floor. No synthesized percentage is ever displayed.

---

## 7. Recommendation algorithm & explanation contract

### 7.1 Ranking (deterministic; generalizes `agent/planner.py`)

**Source of student focus (Phase 0).** There is no explicit goal-selection UI yet, so "focus" is derived
deterministically from the student's **own activity**: the set of concepts that appear in that student's
`skill_signal` rows (i.e. concepts they have actually attempted), plus any concept with an open
misconception. Phase 0 does **not** invent prerequisites for concepts the student has never touched.
(A future phase may add an explicit role/goal that expands focus; noted in §14.)

Order recommendations by priority tier, then deterministic sort within a tier:
1. **Open misconceptions** (highest). Sort by misconception `count` desc, then `last_seen` desc, then
   `concept_id` asc (stable tie-break).
2. **Low-mastery attempted concepts**: concepts in focus whose label is
   `Not enough evidence`/`Emerging`/`Developing`. Sort by label ordinal asc (weakest first), then
   `last_seen` asc, then `concept_id` asc.
3. **Spaced-repetition due** items (see formula below). Sort by most overdue first, then `concept_id` asc.

**Spaced-repetition interval formula (deterministic).**
```
interval_days(label) = { Emerging:1, Developing:3, Proficient:7, Strong:16 }   # SM-2-style, fixed table
due(concept)         = last_seen + interval_days(label) <= now
overdue_by(concept)  = now - (last_seen + interval_days(label))                # larger = more overdue
```
Only concepts with a real `last_seen` are eligible; a concept with no signals has no `last_seen` and is
never "due". `RECENCY_WINDOW_DAYS` bounds how far back a due item is still surfaced.

**No fabrication when evidence is absent.** If the student has **no** signals (new student, or nothing
backfilled), the additive `GET /recommendations` returns an **empty list**. The existing `GET /next`
does **not** change shape: it keeps returning a valid `NextExerciseResponse` (a starter question with an
honest `reason`), exactly as the current planner does today — see §7.3. The engine never manufactures a
concept, a mastery claim, or a "due" item without stored evidence behind it.

### 7.2 Explanation contract (required)
Every `Recommendation` MUST include a non-empty `reason` and an `evidence_summary` of **real counts**:
```json
{
  "action": "revise | practice | assess | learn",
  "target_module": "interview",            // Phase 0 only targets interview/practice
  "target_ref": "<topic or concept>",
  "concept_id": "C-HASH-AVG",
  "reason": "You showed a misconception about hash lookups (seen 2x). Revisit the concept, then try a fresh question.",
  "priority": "misconception | prerequisite | spaced_due",
  "evidence_summary": { "misconception_count": 2, "independent_successes": 0, "last_seen": "..." }
}
```
### 7.3 Integration with the EXISTING `/next` route (verified against source)
Inspected in `api/main.py`: `/students/{student_id}/next` is registered **directly on `app`**:
```python
@app.get("/students/{student_id}/next", response_model=NextExerciseResponse)
def next_exercise(student_id, authed=Depends(current_student)):
    _authorize_path_student(student_id, authed)
    nx = planner.next_exercise(authed)
    return NextExerciseResponse(topic=nx["topic"], question=q["text"], reason=nx["reason"],
                                concept_token=q["expected_concepts"])
```
There is **no `include_router`** today; all routes are decorated on `app`.

**Integration decision (no duplicate route):**
- The new `api/routers/learning.py` exposes **only** `GET /students/{id}/skills` and
  `GET /students/{id}/recommendations`. It does **NOT** register `/students/{id}/next` — registering the
  same GET path on both `app` and a router would create a duplicate/ambiguous route. There must remain
  **exactly one** effective `/next` route (the existing one).
- The recommender integrates **behind** the existing route: `agent/planner.py:next_exercise` delegates to
  `agent/skills/recommend.top(student)` and adapts the top recommendation back into the **unchanged**
  `NextExerciseResponse` shape.
- **Verified existing schema (`api/schemas.py`) — all four fields REQUIRED, none nullable, no
  `recommendation` field:**
  ```python
  class NextExerciseResponse(BaseModel):
      topic: str
      question: str
      reason: str
      concept_token: list[str]
  ```
- **No-recommendation case MUST use this same shape** (not a `{ "recommendation": null }` object). When
  there is no evidence yet, `planner.next_exercise` already returns a valid default question today; the
  delegated version keeps doing so — it returns a real starter `NextExerciseResponse` with a `reason`
  such as "No activity yet — here is a question to get started." The JSON shape of `/next` therefore
  **never changes** and `Planner.jsx` needs no change. (The *separate*, additive `/recommendations`
  endpoint may return an empty list; only `/recommendations` — never `/next` — expresses "nothing yet" as
  emptiness.)
- **Backward compatibility:** `Planner.jsx` keeps calling `/next` and keeps receiving `NextExerciseResponse`
  — no frontend change required for the planner. `/recommendations` is additive, consumed by the new
  dashboard `RecommendationList` only.
- A **route-registration test** (§11) asserts exactly one route object answers `GET
  /students/{student_id}/next` after all routers are included.

---

## 8. API contracts (new routers, owner-authorized)

All require `Authorization: Bearer <token>`; all authorize `path student_id == current_student` via the
shared `require_owner` dependency (403 otherwise), matching the existing pattern. No model calls.

```
GET /students/{id}/skills
 -> { "concepts": [ { "concept_id","label","evidence_count",
                      "independent_success_count","open_misconception","last_seen" } ],
      "summary": { "proficient_or_above": N, "developing": N, "open_misconceptions": N, "tracked": N } }
 # NOTE: `confidence` is NOT in the Phase 0 response contract (see §6.4). The frontend client
 #       (frontend/src/api/client.js `skills`) and MasteryPanel must not read a `confidence` field.
 #       The `confidence` DB columns remain (written 0) only for forward compatibility; they are never
 #       serialized by the Phase 0 response model.

GET /students/{id}/recommendations
 -> { "recommendations": [ Recommendation, ... ] }        # ranked; each has reason + evidence_summary

GET /students/{id}/next   # EXISTING route on `app`, UNCHANGED NextExerciseResponse shape:
                          #   { topic: str, question: str, reason: str, concept_token: list[str] }  (all required)
                          # NOT re-registered in the new router. Body (planner.next_exercise -> recommend.top)
                          # draws from the recommender; the no-recommendation case STILL returns a full
                          # NextExerciseResponse (a starter question + honest reason) — never a different shape.

GET /students/{id}/overview
 -> { "interviews_completed": N, "answers_scored": N,
      "skills": { "tracked": N, "proficient_or_above": N, "open_misconceptions": N },
      "streak_days": N, "recent": [ activity_event... ] }   # all from stored data; honest zeros

GET /students/{id}/activity?days=90
 -> { "events": [ { "date","kind","count" } ] }             # aggregated per day for the calendar
```
Response models **omit** internal ids where the UI shouldn't show them (concept ids may be mapped to
friendly titles client-side via `content.js`, as today).

### 8.1 Signal emission point (smallest additive edit to the existing `/score` route)
This is the **one permitted additive edit** to the existing `/score` route in `api/main.py` (see §4).
It is additive, not a rewrite: the scoring call, FairScore output, `ScoreResponse` schema, status codes,
PII gate, and authorization all stay exactly as they are.

Placement and ordering (strict):
1. The existing `/score` flow runs unchanged and **persists the answer** via `db.record_answer(...)`.
2. **Only after that persistence succeeds**, emit — in this order:
   `agent.skills.signals.emit_from_answer(student_id, answer_row)` (writes SkillSignals + triggers the
   per-concept mastery replay), then `agent.activity.record(student_id, 'interview_scored', answer_id)`.
   If persistence did not occur (abstain/PII-reject/validation/credential error paths), **no emission
   happens** — there is no answer to derive signals from.
3. **Emission is wrapped in `try/except` and can never alter the `/score` response.** Any emission
   exception is swallowed (logged at debug, referencing ids only — never tokens/code/answers) so an
   otherwise-successful `/score` still returns its normal `ScoreResponse`.
   **Recoverability after an emission failure is partial, by design (consistent with §9.1):**
   - **SkillSignals and the derived mastery (including misconception lifecycle events —
     `misconception_opened`/`misconception_resolved`) ARE recoverable**: they are a function of the
     persisted `answer` rows, so re-running backfill (§9) re-derives them idempotently (UNIQUE
     `dedup_key` / signal-id-keyed `event_key` make re-derivation a no-op where they already exist).
   - **Historical `interview_scored` activity events are NOT recoverable by backfill** — §9.1
     deliberately does **not** backfill them (doing so would require inventing a `created_at`
     timestamp). Therefore a **failed `interview_scored` write is permanently missing** from the activity
     calendar for that scoring moment under Phase 0. This is an accepted, honest limitation — **not**
     every activity event can be recovered after an emission failure, and Phase 0 adds **no retry
     mechanism** to compensate (that would be an architecture-scope change, explicitly out of scope).
   - Net effect of a failed emission on a successful `/score`: the answer is persisted and returned
     normally; skills/mastery/misconception events can be restored via backfill; only that one day's
     `interview_scored` calendar mark may be absent. The answer still appears in the interview **history**
     view (which renders real `answer.created_at`), so no scoring data is lost — only a calendar dot.
4. Emission is **deterministic and local**: it reads only the persisted `answer_row`/stored fields and
   the concept taxonomy. **No model call and no AWS call** occur in emission (Phase 0 adds zero model
   calls anywhere).

Implementation placement options (both additive; pick the smallest `api/main.py` diff): inline the two
calls at the end of the `/score` handler after `record_answer`, **or** put them in a thin helper the
handler calls on its success path. Either way it is a small additive block, not a rewrite of scoring.

**Activity idempotency (kind-dependent key).** `agent.activity.record(...)` inserts with **INSERT OR
IGNORE** on the UNIQUE `event_key`. The key must be idempotent for *reprocessing the same transition* yet
**distinct for a genuinely new recurrence/resolution**. A `sha256(student|kind|concept_id)` key is wrong
for misconception transitions — it would suppress a legitimate *reopen* of the same concept. The correct
keys:

| kind | `event_key` formula | Why |
|---|---|---|
| `interview_scored` | `sha256(student \| 'interview_scored' \| answer:<id>)` | one scoring event per answer; re-scoring the same answer is a no-op |
| `misconception_opened` | `sha256(student \| 'misconception_opened' \| triggering_signal_id)` | **one event per grounded misconception signal** — the `skill_signal.id` is the unique identity; an initial open AND every recurrence each have their own signal id → their own event |
| `misconception_resolved` | `sha256(student \| 'misconception_resolved' \| resolving_signal_id)` | the `skill_signal.id` of the success that completed `RESOLVE_N` → distinct per resolution |

Because the key is the **signal id** (not a Boolean state flip):
- **Two misconception signals while the misconception stays open** (recurrence) → **two distinct
  `misconception_opened` events** (keyed by the two distinct signal ids). This is the behavior the
  flip-only rule would have missed.
- An **open → resolve → reopen** lifecycle → **three distinct events** (open#sigA, resolve#sigB,
  reopen#sigC).
- **Reprocessing the same signals** re-offers the same `(kind, signal_id)` pairs → all INSERT OR IGNORE
  no-ops → **zero** additional events.

Signal + activity emission is wrapped in try/except so an emission failure can never break `/score`.

The mastery replay (§6.3.8) is the single place that detects lifecycle events. It records a
`misconception_opened` for **every grounded misconception signal** (initial open and each recurrence),
and a `misconception_resolved` for **each signal that completes `RESOLVE_N`** — collected in
chronological order and each offered to `activity.record_transition(...)`, which derives the signal-id
key above. It does **NOT** infer events from Boolean `open_misconception` flips (which would drop a
true→true recurrence). So two misconception signals while open yield two events, open→resolve→reopen
yields three, and repeating the replay yields none (INSERT OR IGNORE on the signal-id-keyed `event_key`).

---

## 9. Backfill of existing interview answers (idempotent, no double-count)

`agent/skills/backfill.py`:
- Reads existing `answer` rows (join `interview` for `topic`/`expected_concepts`) — **persisted results
  only**. It **never** calls the model/evaluator; what was not stored is not reconstructed.
- For each answer, derives signals exactly as live emission would, using the §6.1 mapping and the
  per-concept keys: `independent_key = iv:answer:<id>:<concept_id>`,
  `dedup_key = sha256(student|interview|answer:<id>|<concept_id>|outcome)`. Inserts with INSERT OR IGNORE.
- Because `dedup_key` is UNIQUE **and concept-scoped**, running backfill multiple times is safe, cannot
  double-count, and still records one signal per concept per answer.
- After inserting, call `learner_model.rebuild(student)` for affected students.
- Backfill is invoked explicitly (`python -m agent.skills.backfill`, and/or once at router import guarded
  by a run-once flag) — never silently on every request, and never during live scoring.

### 9.1 Historical activity events — NOT backfilled (explicit)
Backfill creates **SkillSignals** (and the derived mastery) from historical answers, and — because the
mastery replay derives misconception transitions from those signals (§6.3.8) — it may create
`misconception_opened`/`misconception_resolved` events whose identity is the (historical) triggering
signal id. These are legitimate: they are a function of real stored evidence, keyed by signal id, and
idempotent.

**`interview_scored` activity events are NOT backfilled.** We do **not** fabricate per-day "you practised"
calendar entries for historical interviews, because:
- the `activity_event.created_at` would have to be invented or set to backfill-time, misrepresenting when
  the student actually practised — which violates "no fabricated statistics / timestamps";
- the activity calendar's purpose is to show real ongoing engagement from Phase 0 onward.

**Decision:** the **activity calendar begins collecting `interview_scored` events from Phase 0 activation
onward.** Historical interviews still populate skills/mastery (from backfilled signals) and still appear
in the existing interview **history** view (which already renders real `answer.created_at`), but they do
**not** retroactively fill the activity heatmap. The heatmap's empty state for pre-activation dates is
honest ("no tracked activity yet for this period"), not a fabricated backfill.

> If a product decision later wants historical practice reflected on the calendar, it must use the real
> stored `answer.created_at` values (never invented dates). That is explicitly out of Phase 0 scope and
> listed in §14.

Verified current data (from the audit's live DB): 2 answers, 0 misconceptions — backfill will create a
small, known set of signals, making the first integration test deterministic.

---

## 10. Frontend routes & components

### 10.1 Routes (additive; existing routes preserved)
```
/app                         -> CareerDashboard (evolved home; tabs: Overview | Progress | Misconceptions | Reports)
/app/practice                -> existing Practice (unchanged)
/app/progress                -> existing Progress (also embedded as a Dashboard tab)
/app/misconceptions          -> existing Misconceptions (also a tab)
/app/planner                 -> existing Planner (unchanged; now backed by the recommender via /next)
/app/reports                 -> existing Reports (also a tab)
```
No existing route is removed. The Dashboard tabs **render the existing page components** (import and
embed `Progress.jsx`, `Misconceptions.jsx`, `Reports.jsx`), so there is zero duplication and zero rewrite.

### 10.2 New components
- `CareerDashboard.jsx` — overview: `RecommendationList` (top items), `MasteryPanel`, `ActivityHeatmap`,
  plus quick-action cards (reuse existing). Tabs wrap existing pages.
- `MasteryPanel.jsx` — per-concept **labels** (not fake %), using `BandBar`-style bars keyed to mastery
  labels via `mastery.js`; "Not enough evidence" state explicit.
- `ActivityHeatmap.jsx` — calendar/streak from `/activity` (SVG or recharts); empty state until events exist.
- `RecommendationList.jsx` — each item shows the **reason** and real evidence counts; links to practice.
- `lib/mastery.js` — label → colour/copy (mirrors `content.js` conventions; no new deps).

### 10.3 States
Every new view implements the four states using existing `ui.jsx` primitives: loading (`LoadingBlock`),
empty (`EmptyState` — e.g. "No activity yet"), error (`ErrorState` with retry via `useApi`), success.
401 → `AuthContext` logout (existing behavior).

---

## 11. Testing & acceptance criteria

All tests run in **mock mode**, assert **zero AWS**, and use a throwaway DB (existing `temp_db` fixture).

| Test file | Must verify |
|---|---|
| `test_skill_signals.py` | dedup includes concept_id (same answer+concept+outcome → one row); multiple concepts from one answer → one independent signal each; taxonomy validation (unknown concept rejected, fail-closed); §6.1 mapping incl. `absent`→no signal and no `struggled` emitted; **an answer with ONLY an overall technical band and NO persisted per-concept evidence produces NO `mastered`/`partial` signal** (only misconception signals from its stored tags, if any) |
| `test_learner_model.py` | ladder Emerging(1)/Developing(2)/Proficient(≥3)/Strong(≥5); `partial` never exceeds Emerging; `absent` ignored; **mastery reversal** (misconception caps an already-Proficient concept to Developing without erasing successes); **equal-timestamp determinism** (tie-break by `id`); confidence not used; **misconception open → resolve (after RESOLVE_N) → reopen on recurrence** with correct cap/uncap each time |
| `test_resolve_streak.py` (new) | **RESOLVE_N requires genuinely consecutive new-key `mastered` signals**: an intervening `partial` resets the streak (open stays open); a **duplicate already-counted `mastered` neither advances nor resets** the streak; resolution fires only on N consecutive true successes |
| `test_same_evidence_precedence.py` (new) | one answer yielding both `supported` and a grounded misconception for the **same concept** → **only the misconception signal** for that concept; that answer's `independent_key` is **not** a positive success; a **separate** later answer with `supported` **does** count and contributes to resolution; other concepts on the first answer unaffected |
| `test_learner_model_equivalence.py` | **incremental (`update` sequence) == one-shot `rebuild`** for every concept, across randomized insert orders AND equal timestamps (the §6.3.7 guarantee) |
| `test_recommend.py` | tier order (misconception > low-mastery attempted > spaced-due); spaced interval table {1,3,7,16}; focus = attempted concepts only (no invented prerequisites); **no evidence → `/recommendations` empty list**, while **`/next` still returns a full `NextExerciseResponse`** (4 required fields, starter question) — same shape as today; every recommendation has non-empty reason + real evidence_summary; deterministic tie-breaks |
| `test_activity.py` | event recording; **`interview_scored` duplicate emission is a no-op** (same answer re-scored → one row); **two misconception signals while the misconception stays OPEN → two distinct `misconception_opened` events** (recurrence-while-open, keyed by distinct signal ids — the §6.3.8 correction); **batch replay containing open→resolve→reopen persists all 3 events in one pass** (keyed by triggering/resolving signal id); **repeating the whole replay persists 0 additional events** (idempotent); `misconception_resolved` emitted only on the signal completing `RESOLVE_N` (not on every mastered); `interview_scored` events are **only** created from Phase 0 activation onward (not backfilled); per-day aggregation; streak on real timestamps |
| `test_historical_activity.py` (new) | backfill creates skills/mastery (and signal-id-keyed misconception transition events) but **does NOT create `interview_scored` events**; the activity calendar shows no fabricated historical practice days; no invented timestamps |
| `test_backfill.py` | existing answers → signals from **persisted data only** (asserts the evaluator/model is NEVER called — e.g. patch `agent.app.run`/model to raise if invoked); **idempotent** (run twice → identical signal/label counts); multi-concept answers backfill one signal per concept; **band-only historical answers produce no `mastered`/`partial` signal**; preserves existing rows |
| `test_learning_api.py` | ownership (403 cross-student, 401 unauth); skills/recommendations shapes; **`skills` response contains NO `confidence` field**; zero AWS asserted (mock-mode, boto3 spy) |
| `test_dashboard_api.py` | overview/activity from stored data only; honest zeros/empty states; ownership (403/401) |
| `test_routes.py` (new) | **exactly one** route answers `GET /students/{student_id}/next` after all routers are included (enumerate `app.routes`, assert a single match for that path+GET) — proves no duplicate registration; its `response_model` is still `NextExerciseResponse`; the no-recommendation response validates against `NextExerciseResponse` (4 required fields, no `recommendation` key); `/skills` and `/recommendations` exist once each |
| `test_migration.py` (extend) | the 3 new tables created on **fresh AND older** DB; **all pre-existing records preserved** (count+checksum unchanged); idempotent re-run (second `init_db` adds nothing) |
| `test_rollback.py` (new, §12.3) | **complete rollback**: 3 tables dropped; pre-existing student/interview/answer/auth rows byte-identical to snapshot; `init_db` reruns cleanly; simulated `/score` after writer-removal does not touch a dropped table |
| frontend | build + manual: four states render on every new view; existing routes still work; dashboard tabs embed the existing Progress/Misconceptions/Reports pages; **MasteryPanel reads no `confidence`**; no fabricated numbers; concept ids not shown raw |

**New scenario explicitly required by THIS revision:** **two grounded misconception signals while the
misconception remains open must record two distinct `misconception_opened` events** (recurrence-while-open
is a signal-driven lifecycle event, not a Boolean flip), and replaying those signals adds zero events
(`test_activity.py`).
**From the prior revision:** consecutive-resolution with intervening-partial reset and duplicate-signal
no-effect (`test_resolve_streak.py`); same-evidence precedence (`test_same_evidence_precedence.py`); batch
replay persisting open→resolve→reopen + repeated-replay idempotency (`test_activity.py`); historical
`interview_scored` NOT backfilled (`test_historical_activity.py`); `/next` no-recommendation validates
against the exact `NextExerciseResponse` (`test_routes.py`, `test_recommend.py`).
**Carried from prior revisions:** band-only answer → no per-concept mastery signal; misconception
open→resolve→reopen label behavior; multi-concept per answer; duplicate `interview_scored`; equal
timestamps; mastery reversal; incremental == rebuild; single effective `/next` route; backfill idempotency;
complete rollback; record preservation; zero-AWS.

**Acceptance criteria (Phase 0 is accepted when):**
1. New tables migrate cleanly on the existing `careerlift.db` with all current rows intact.
2. Backfill is idempotent and produces the expected signals from the 2 existing answers.
3. Mastery labels are reproducible (rebuild == incremental) and respect the 3-independent-success floor.
4. Misconceptions open, resolve after RESOLVE_N, and reopen on recurrence — all covered by tests.
5. Recommendations are ranked and every one carries a reason + real evidence counts.
6. All new endpoints enforce owner authorization (401/403) and make zero AWS calls.
7. Dashboard shows real data or honest empty states; no fabricated numbers anywhere.
8. Existing routes/pages/tests continue to pass (the full suite stays green; new tests added on top).
9. Both model modes still work; Phase 0 added no model calls.

---

## 12. Risks & rollback strategy

| Risk | Mitigation / rollback |
|---|---|
| Migration affects existing data | Only `CREATE TABLE IF NOT EXISTS` + new derived tables; no ALTER on existing data. Rollback: drop the 3 new tables — existing data untouched. |
| `learner_concept` cache drifts from signals | It is derived; `rebuild(student)` regenerates it; a test asserts incremental == rebuild. Rollback: drop + rebuild. |
| Backfill double-counts | UNIQUE `dedup_key` + idempotency test. Rollback: delete signals with `source_module='interview'` and rebuild. |
| `main.py` router include breaks startup | Routers are additive; if an import fails, remove the two `include_router` lines to revert to current behavior. |
| Frontend nav change breaks a route | Existing routes are preserved verbatim; new ones are additive. Rollback: revert `App.jsx`/`AppLayout.jsx` nav additions. |
| Signal emission slows `/score` | Emission is deterministic, local, and tiny; done after persistence; can be wrapped in try/except so a signal failure never breaks scoring. |
| Dependency need (e.g. heatmap lib) | Prefer SVG/recharts (already present). Any new dep requires explicit approval before install. |

### 12.1 Complete rollback procedure (ordered — stop writers before removing tables)
Rollback must remove **every** Phase-0 artifact and must guarantee the application never attempts to
write to a table that rollback has dropped. Order matters:

1. **Frontend first:** revert the additive nav/route changes in `App.jsx` and `AppLayout.jsx`, and remove
   the new components (`CareerDashboard`, `MasteryPanel`, `ActivityHeatmap`, `RecommendationList`,
   `mastery.js`) and the added `client.js` methods. The UI returns to the audited Dashboard.
2. **Stop the writers (backend wiring), before touching the DB:**
   - Remove the `include_router(learning)` / `include_router(dashboard)` lines from `api/main.py`.
   - Remove the additive **signal + activity emission** block from the existing `/score` route in
     `api/main.py`, restoring `/score` to its **exact pre-Phase-0 body** (the emission was the only
     change there; scoring, FairScore, `ScoreResponse`, status codes, PII gate, and authorization were
     never modified, so removing that block fully reverts the route). Also revert any planner delegation
     added to `agent/planner.py` to its pre-Phase-0 body.
   - Remove/disable the new modules (`agent/skills/*`, `agent/activity.py`, `api/routers/*`, `api/deps.py`).
   After this step, **no code path references `skill_signal`, `learner_concept`, or `activity_event`** —
   this is what prevents writes to tables about to be dropped.
3. **Remove the schema additions:** delete the three new `CREATE TABLE IF NOT EXISTS` blocks (and their
   indexes) from `db.py`'s `SCHEMA`, and remove any Phase-0 entries from `_EXPECTED_COLUMNS` (there are
   none for Phase 0 — all additions are new tables).
4. **Drop the tables in the database:** `DROP TABLE IF EXISTS activity_event; DROP TABLE IF EXISTS
   learner_concept; DROP TABLE IF EXISTS skill_signal;` (drop order avoids any FK references; all three
   reference only `student`, which is untouched).

### 12.2 Preservation guarantee
Rollback touches **only** the three new tables. `student`, `interview`, `answer`, `misconception`, and
`auth_token` are never altered or dropped, so all pre-existing student, interview, answer, and
authentication records are preserved byte-for-byte. `learner_concept` is a derived cache (losing it loses
nothing); `skill_signal` and `activity_event` are new Phase-0 data only.

### 12.3 Rollback verification test (required)
Add `tests/test_rollback.py`:
1. Seed a DB with pre-existing `student`/`interview`/`answer`/`auth_token` rows and snapshot their counts
   and checksums.
2. Apply Phase-0 migration (creates the 3 tables) and write some signals/activity.
3. Execute the rollback DROP step.
4. Assert: the 3 Phase-0 tables no longer exist; the pre-existing tables and **every** pre-existing row
   are identical to the snapshot; `init_db()` still runs cleanly afterward (fresh app start works).
5. Assert that with the emission wiring removed, a simulated `/score` persists an answer **without**
   referencing any dropped table (no "no such table" error) — proving writers were stopped before drops.

Phase 0 is therefore fully reversible to the exact pre-Phase-0, as-audited system.

---

## 13. Definition of Done

- [ ] New tables + indexes added via `db.py` SCHEMA; migration idempotent; existing `careerlift.db` rows preserved (verified).
- [ ] `agent/skills/{signals,learner_model,recommend,backfill}.py` and `agent/activity.py` implemented, pure/deterministic, no model/AWS.
- [ ] `api/routers/{learning,dashboard}.py` + `api/deps.py` implemented; `main.py` includes them (additive); all owner-authorized.
- [ ] `/score` has exactly **one** smallest additive edit (§4/§8.1): emission of signals + activity **only after successful `db.record_answer`**, wrapped so a failure **never** alters the `ScoreResponse`; scoring logic, FairScore output, response schema, status codes, PII gate, and authorization unchanged; emission is deterministic/local with **no model or AWS call**; abstain/PII/error paths emit nothing.
- [ ] Backfill run once on the existing DB; idempotent; **reads persisted data only (evaluator/model never invoked)**; band-only answers produce no `mastered`/`partial` signal; signals + labels verified. Backfill recovers **SkillSignals + misconception lifecycle events only** — it deliberately does **NOT** recover historical `interview_scored` events (§9.1), so a failed `interview_scored` emission leaves a permanently-missing calendar mark under Phase 0 (no retry; accepted limitation per §8.1).
- [ ] `/next` remains a **single** route (existing, on `app`); `planner.next_exercise` delegates to the recommender and still returns `NextExerciseResponse` **in every case including no-recommendation** (4 required fields, no `recommendation` key); `test_routes.py` proves no duplicate + schema conformance.
- [ ] `resolve_streak` requires genuinely consecutive new-key `mastered`; intervening `partial` resets it; duplicate `mastered` neither advances nor resets it (`test_resolve_streak.py`).
- [ ] Same-evidence precedence: a grounded misconception blocks the **same answer** from counting as positive mastery for that concept; separate answers still count (`test_same_evidence_precedence.py`).
- [ ] Replay records a `misconception_opened` for **every** grounded misconception signal (initial open AND recurrence-while-open — signal-driven, not a Boolean flip), and a `misconception_resolved` for each signal completing `RESOLVE_N`; two signals while open → 2 distinct events; open→resolve→reopen → 3 events in one pass; repeated replay adds 0 (`test_activity.py`).
- [ ] Historical `interview_scored` activity is **not** backfilled; the calendar starts at Phase 0 activation; no fabricated timestamps (`test_historical_activity.py`).
- [ ] `skills` API and the frontend client/`MasteryPanel` agree: **no `confidence`** field anywhere in Phase 0.
- [ ] Frontend: `CareerDashboard` + `MasteryPanel` + `ActivityHeatmap` + `RecommendationList` + `mastery.js`; existing Progress/Misconceptions/Reports embedded as tabs; all existing routes still work.
- [ ] All four UI states on every new view; no fabricated stats; concept ids not shown raw.
- [ ] New test files pass, **including `test_rollback.py` and the expanded scenarios** (multi-concept, duplicate activity, equal timestamps, mastery reversal, misconception resolution/recurrence, backfill idempotency, record preservation); the full existing suite stays green; zero-AWS asserted in mock mode.
- [ ] `incremental == rebuild` verified for mastery; confidence confirmed unused in Phase 0.
- [ ] No dependency installed/upgraded without explicit approval; no AWS/Bedrock calls; nothing deployed; no existing source rewritten.

---

## 14. Open decisions to confirm before building (defaults proposed)

Resolved in this revision (now fixed unless you object):
- `dedup_key` and `independent_key` are **concept-scoped** (§6.2) — multi-concept answers produce one
  signal per concept.
- **Confidence is excluded from Phase 0** (§6.4): written as 0, never used or shown.
- Mastery ladder uses `EVIDENCE_FLOOR = 3` (Proficient) and **`STRONG_FLOOR = 5` (Strong)** — "Strong" is
  no longer a vague term (§6.3.5).
- Ordering is `(created_at, id)` with `id` as the deterministic tie-breaker (§6.3.1).
- The label never depends on recency; recency affects **recommendation ranking only** (§6.3.4).
- No `struggled` signal is emitted in Phase 0; the rule is future-only and unreachable (§6.1/§6.3.3).
- Focus = the student's **attempted** concepts + open misconceptions; no invented prerequisites (§7.1).
- Spaced interval table = `{Emerging:1, Developing:3, Proficient:7, Strong:16}` days (§7.1).
- Activity emission is idempotent via UNIQUE `event_key` (§8.1); rollback procedure is fully specified (§12).

Resolved in **this** revision (now fixed unless you object):
- **No band-derived per-concept fallback.** `mastered`/`partial` require persisted per-concept evidence;
  an overall band alone yields none; band-only historical answers produce only any misconception signals
  their stored tags imply (§6.1).
- **Misconception activity keys use the triggering/resolving `skill_signal.id`**, so open→resolve→reopen
  are three distinct, idempotent events (§8.1).
- **`confidence` removed from the Phase 0 `skills` API**; DB columns kept (written 0) for forward-compat
  only; frontend must not read it (§6.4, §8).
- **`/next` stays a single existing route**; the recommender integrates via `planner.next_exercise`
  delegation; the new router does not re-register `/next` (§7.3).
- **Incremental update IS a per-concept replay** (no carried accumulators), so update == rebuild by
  construction (§6.3.7).
- **Planner delegation chosen** (one ranking source) — the prior "either is acceptable" is now decided.
- **`resolve_streak` is strictly consecutive**: incremented only by a new-key `mastered`; reset by any
  `misconception`/`partial` (future `struggled`); duplicate `mastered` has no effect (§6.3.3).
- **Same-evidence precedence**: a grounded misconception on `(answer, concept)` suppresses that answer's
  positive signal for that concept; no item yields contradictory outcomes (§6.2.1).
- **Misconception lifecycle events are signal-driven, not flip-driven** (§6.3.3/§6.3.8): every grounded
  misconception signal (initial open AND recurrence-while-open) records its own `misconception_opened`
  keyed by its signal id and resets `resolve_streak`; resolutions are keyed by the signal completing
  `RESOLVE_N`; replay collects all of them chronologically and is idempotent on repeat.
- **`/next` no-recommendation uses the exact `NextExerciseResponse`** (verified in `api/schemas.py`);
  emptiness is expressed only by the additive `/recommendations` (§7.3).
- **Historical `interview_scored` activity is NOT backfilled**; the activity calendar starts at Phase 0
  activation; no invented timestamps (§9.1).

Still to confirm:
1. **Numeric constants:** `EVIDENCE_FLOOR = 3`, `STRONG_FLOOR = 5`, `RESOLVE_N = 2`,
   `RECENCY_WINDOW_DAYS = 30`, and the spaced-interval table `{1,3,7,16}` — confirm or adjust.
2. **Persisting per-concept status at scoring time** (a *later* phase, not Phase 0): since current data
   persists only overall bands + misconception tags, `mastered`/`partial` signals will be sparse until
   the scorer stores per-concept status. Confirm this is acceptable for Phase 0 (misconception-driven
   signals + whatever per-concept detail already exists), with richer per-concept persistence deferred.
3. **Cross-module independence** (later phases): a success in a different module counts as independent
   evidence for the same concept (recommended yes). Moot in Phase 0 (single source); sets the rule.
4. **Signal emission site:** inline additive calls in `api/main.py:/score` vs a thin wrapper — both
   additive; pick the smallest `main.py` diff.
5. **Activity heatmap rendering:** SVG vs recharts (both avoid new deps) — recommend SVG.
6. **Explicit goal/role as a future focus source** (§7.1) — out of Phase 0 scope; confirm deferral.
7. **Historical practice on the calendar** (§9.1): confirm it is acceptable that the activity heatmap
   starts at Phase 0 activation (historical interviews still show in the history view and feed mastery).
   If later you want them on the calendar, it must use real `answer.created_at`, never invented dates.

---

*End of Phase 0 spec (revised). This revision only updated `PHASE_0_IMPLEMENTATION_SPEC.md`; no
application source, database, frontend, dependencies, environment, or other design documents were
modified. Implementation has not begun.*
