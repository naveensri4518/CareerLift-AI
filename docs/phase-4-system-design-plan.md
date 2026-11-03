# Phase 4 — System Design Academy: Implementation Plan

Status: **PLAN ONLY — not implemented.** Scope approved; awaiting approval of this finalized plan before
any code is written.

This document is the deliverable of a repository inspection. It does not modify any source. It proposes
how to add an interactive System Design learning environment as an additive Phase 4, reusing the exact
patterns established by Phases 0–3.

## 0. Approved scope decisions (locked)

The following were approved and are now the fixed scope for Phase 4:

1. **Structured-model System Design Canvas** for the MVP (component list + connection builder + decision
   prompts). No freehand drag-and-drop diagramming in Phase 4; a visual layer may render the same model
   later with no backend change.
2. The canvas supports: **component selection, connections, database/API design, architecture decisions,
   and scalability trade-off evaluation.**
3. **Deterministic, rubric-based grading.** No LLM in the grading path.
4. **Phase 0 integration** via the existing `SkillSignals → LearnerModel → recommendations` pipeline,
   using `source_module="sysdesign"`.
5. **Investigate** a backward-compatible extension to recommendation target mapping so System Design
   recommendations can link to relevant practice. This is an **investigation + design only** in this
   phase — `recommend.py` is **NOT modified yet** and any edit to it requires separate approval
   (see §13). Until then, SD recommendations surface by mastery/misconception/priority with a `null`
   practice target.

Guardrails reaffirmed: no changes to Phase 0–3 source without separate approval; `recommend.py` not
touched yet; no AWS/Bedrock; no Strands-Ship commands; no new runtime dependencies; no Phase 5 scope.

---

## 1. Existing architecture findings

### 1.1 Repository shape
```
agent/                         # deterministic domain logic (no web framework)
  db.py                        # single SQLite layer: one SCHEMA string + CRUD + idempotent migration
  config.py                    # CAREERLIFT_MODEL_MODE (bedrock|mock); ModelUnavailableError -> 503
  fairscore.py / models.py     # FairScore core + concept taxonomy loader (concepts.json)
  activity.py                  # idempotent activity_event recorder (streak/heatmap feed)
  skills/
    signals.py                 # Phase 0 interview signal emission (source_module="interview")
    learner_model.py           # mastery state machine (replay of skill_signal rows)
    recommend.py               # deterministic recommendation ranking (3 tiers)
    backfill.py                # one-time signal backfill
  interview*.py                # Phase 1
  coding_*.py                  # Phase 2 (bank, languages, exec, eval, signals)
  assessment_*.py              # Phase 3 (bank, eval, signals)
  data/                        # concepts.json, assessment_concepts.json, *_questions.json, coding_problems.json, guidance.json
api/
  main.py                      # FastAPI app; lifespan calls db.init_db(); CORS; include_router(...) per phase
  auth.py                      # bearer-token auth; current_student dependency
  deps.py                      # require_owner (403 on student_id mismatch)
  schemas.py                   # shared Pydantic models (older endpoints); newer routers inline their models
  routers/                     # learning, dashboard, studio, coding, assessment
frontend/src/
  api/client.js                # single `api` object; request() helper; VITE_API_BASE or /api proxy
  lib/                         # content.js, mastery.js, studio.js, coding.js, assessment.js, useApi.js
  components/                  # ui.jsx (Card, Badge, StatCard, Band*, EmptyState…), AppLayout.jsx, charts
  pages/                       # Dashboard, Landing, Register, Practice, Progress, Misconceptions,
                               # Planner, Reports, studio/, coding/, assessment/
tests/                         # 16 test files (166 tests currently passing)
```

### 1.2 Backend conventions (to mirror exactly)
- **App wiring:** `api/main.py` registers each phase with `from .routers import X as X_router` + `app.include_router(X_router.router)`. Prefix-style routers set their own prefix (`APIRouter(prefix="/coding", ...)`).
- **DB:** stdlib `sqlite3` only. One big `SCHEMA` string of `CREATE TABLE IF NOT EXISTS`, per-phase section headers. `connect()` context manager (`row_factory=Row`, `PRAGMA foreign_keys=ON`, commit/close). `init_db()` runs the schema then `_migrate()` (idempotent `ALTER TABLE ADD COLUMN`). Timestamps via `_now()` (UTC ISO). Lists/dicts stored as `json.dumps`, read with `json.loads`. New tables need **no** migration entry.
- **Auth/ownership:** `current_student` (Header bearer → student_id, 401 on bad token). Prefix routers take `student_id: str = Depends(current_student)` and compare the stored row's `student_id` (403 on mismatch), exactly as `studio.py` / `coding.py` / `assessment.py` do.
- **Errors:** `HTTPException` with 400/401/403/404/409/422/503. Pydantic `Literal[...]` for enums → automatic 422.
- **Idempotency:** guarded `UPDATE ... WHERE status='in_progress'` for one-time finalization (assessment submit); `INSERT OR IGNORE` on unique keys for signals/activity.

### 1.3 Phase 0 Learning Intelligence pipeline (the integration spine)
`skill_signal` rows → `learner_model.update(student_id, concept_id)` (deterministic replay → label in
{Not enough evidence, Emerging, Developing, Proficient, Strong} + misconception lifecycle) → `learner_concept`
cache → `recommend.rank()` + `/students/{id}/skills|overview|activity`.

Two precedents already feed this from outside interviews, **without touching Phase 0 files**:
- `agent/coding_signals.py` — `source_module="coding"`.
- `agent/assessment_signals.py` — `source_module="assessment"`, validates concept ids against the
  **union** of `fairscore.concept_ids()` and the assessment taxonomy.

The `skill_signal.source_module` column comment already reserves `sysdesign` as a future value. Phase 4
will add `agent/sysdesign_signals.py` with `source_module="sysdesign"` following the assessment bridge
verbatim.

### 1.4 Frontend conventions (to mirror exactly)
- `api/client.js`: add methods to the single exported `api` object using the `request()` helper.
- `lib/useApi.js`: `useApi(fetcher, deps)` → `{data, loading, error, retry}` with 401 session-drop.
- `App.jsx`: `<Route path="/app/..." element={<Protected><Page/></Protected>} />`.
- `components/AppLayout.jsx`: add one entry to the `NAV` array (lucide icon + label + `to`).
- `components/ui.jsx`: reuse `Card`, `SectionHeading`, `Badge`, `StatCard`, `BandBar`, `BandGauge`,
  `EmptyState`, `ErrorState`, `LoadingBlock`, `Spinner`, `Toast`; dark dotted-grid shell + accent palette.
- `lib/<phase>.js`: static label/metadata mapping (e.g. `assessment.js` category/grade/difficulty meta).

### 1.5 Current test baseline
16 test files, **166 tests passing**. API-test template: `tests/conftest.py` `temp_db` fixture
(throwaway SQLite, `monkeypatch` DB path, `init_db`) + a `client` fixture forcing
`CAREERLIFT_MODEL_MODE=mock` and `TestClient(main.app)`; helpers `_reg(client)` and `_auth(token)`.

---

## 2. Reusable assets for Phase 4 (no new infra required)

| Need | Reuse (existing) |
|---|---|
| Auth + ownership | `api/auth.current_student`, `api/deps.require_owner` |
| Persistence | `agent/db.py` (add tables + CRUD; same patterns) |
| Mastery pipeline | `db.insert_skill_signal` → `skills/learner_model.update` (unchanged) |
| Activity/streak | `agent/activity.record(student_id, kind, ref_id)` |
| Deterministic timed/attempt lifecycle | mirror `api/routers/assessment.py` (states, server timing, idempotent submit) |
| Server-owned bank + answer-key hiding | mirror `assessment_bank.py` / `coding_problems.py` public-view pattern |
| Mock-mode guard (no AWS) | `agent/config.py` (`is_mock()`, `ModelUnavailableError` → 503) |
| Frontend shell/components | `AppLayout`, `ui.jsx`, `useApi`, `client.js` `request()` |
| Concept taxonomy pattern | `agent/data/assessment_concepts.json` (separate file; union-validated) |

**Conclusion: Phase 4 needs no new runtime dependencies and no AWS.** The entire feature can be built
deterministically (rubric-based evaluation) exactly like Phase 3, keeping Bedrock off until explicitly
requested in a later phase.

---

## 3. Proposed Phase 4 architecture

An **interactive System Design challenge** is modeled as a *scenario* (server-owned brief + requirements
+ a deterministic rubric) that a student answers by building a **design submission**: a set of
**components** (e.g. Load Balancer, API Gateway, Cache, SQL DB, Queue…), **connections** between them, and
structured **design decisions** (DB choice, API style, scaling/reliability trade-offs). The submission is
graded deterministically against the scenario's rubric — **no LLM required** — producing a score, per-
dimension breakdown, matched/missing requirements, and feedback. Results emit `sysdesign` SkillSignals.

```
Student → SysDesign Academy (landing) → pick scenario
        → Design Canvas (add components, connect them, answer decision prompts)
        → Submit → deterministic rubric evaluation (agent/sysdesign_eval.py)
        → Result (score, dimensions, matched/missing requirements, trade-off feedback, review)
        → emit sysdesign SkillSignals → shared mastery + recommendations + dashboard/activity
```

Design principle (consistent with the whole project): **code owns the facts.** The rubric — required
components, required connections, expected decisions, scoring weights, canonical trade-offs — lives in
curated JSON + pure Python. The model is not in the grading path. This keeps Phase 4 fully testable,
deterministic, and AWS-free.

---

## 4. Feature breakdown

1. **Scenario bank** (server-owned): e.g. "Design a URL shortener", "Design a news feed", "Design a rate
   limiter", "Design a chat system", "Design an image-upload service". Each scenario: title, difficulty,
   prompt, functional + non-functional requirements, a palette of allowed component types, a rubric, and
   decision prompts (DB design, API design, scalability, reliability). Hidden rubric internals (weights,
   canonical answers) are never exposed before submission — same answer-key protection as Phase 3.
2. **Design canvas** (frontend): add/remove components from a palette, position them, draw directed
   connections, and answer structured decision prompts. Starts as a **form-plus-graph** model (component
   list + connection list + decision selects/multi-selects), not a freehand drawing tool — deterministic
   and gradable. (A richer drag-and-drop diagram is a stretch goal; see Risks.)
3. **Component selection & connections**: constrained to the scenario's palette; connections validated
   server-side against allowed component ids.
4. **Database & API design**: structured decision prompts (e.g. "Primary datastore?" single-select;
   "Which APIs?" multi-select) with deterministic correct/acceptable sets, like assessment MCQs.
5. **Scalability & reliability**: decision prompts covering caching, replication, partitioning, queues,
   failover — scored against the rubric's expected set.
6. **Trade-off analysis**: each scenario carries canonical trade-offs (e.g. SQL vs NoSQL for this use
   case); the student selects the trade-offs that apply; graded as a multi-select against the rubric.
7. **Structured evaluation & feedback**: deterministic score per dimension
   (components, connections, data, API, scalability, reliability, trade-offs), matched vs missing
   requirements, and per-dimension textual feedback drawn from the rubric (not generated).
8. **Learning Intelligence integration**: emit `sysdesign` SkillSignals from the graded result into the
   existing mastery pipeline; record a `sysdesign_scored` activity event.

---

## 5. Database design (additive — new tables only)

Add to the `SCHEMA` string in `agent/db.py` under a `-- ===== Phase 4: System Design Academy =====`
header. No existing table is altered; no migration entry needed (CREATE IF NOT EXISTS).

```sql
-- One attempt at one scenario. Submission content (components/connections/decisions) and the graded
-- result are stored as JSON. status: in_progress | submitted. result is set once on submit.
CREATE TABLE IF NOT EXISTS sysdesign_attempt (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id    TEXT NOT NULL,
    scenario_id   TEXT NOT NULL,                 -- curated scenario id (e.g. 'SD-URL-SHORTENER')
    difficulty    TEXT NOT NULL,                 -- beginner | intermediate | advanced
    status        TEXT NOT NULL DEFAULT 'in_progress',  -- in_progress | submitted
    design        TEXT NOT NULL DEFAULT '{}',    -- json {components:[...], connections:[...], decisions:{...}}
    result        TEXT,                          -- json score+dimensions+feedback (set once on submit)
    started_at    TEXT NOT NULL,
    submitted_at  TEXT,
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES student(id)
);
CREATE INDEX IF NOT EXISTS idx_sysdesign_attempt_student ON sysdesign_attempt(student_id, created_at);
```

Scenarios themselves live in `agent/data/sysdesign_scenarios.json` (server-owned, includes the rubric).
Concepts live in `agent/data/sysdesign_concepts.json` (new taxonomy ids like `SD-SCALING-CACHE`,
`SD-DATA-PARTITION`, `SD-API-REST`, `SD-RELIABILITY-REPLICATION`), validated as the **union** with the
FairScore + assessment taxonomies — never modifying `concepts.json`.

CRUD to add (mirroring assessment): `create_sysdesign_attempt`, `get_sysdesign_attempt`,
`save_sysdesign_design`, `submit_sysdesign_attempt` (guarded idempotent UPDATE),
`list_sysdesign_attempts`.

No persisted answers are editable after submit; the guarded UPDATE prevents duplicate submission.

---

## 6. API design (new router `api/routers/sysdesign.py`, prefix `/sysdesign`)

All owner-authorized via `current_student`; rubric internals hidden until submission.

| Method & path | Purpose |
|---|---|
| `GET  /sysdesign/scenarios` | list scenarios (id, title, difficulty, short prompt; NO rubric) |
| `GET  /sysdesign/scenarios/{id}` | full brief: prompt, requirements, component palette, decision prompts + options (NO correct keys / weights) |
| `POST /sysdesign/attempts` | start an attempt for a scenario (returns attempt id + brief) |
| `GET  /sysdesign/attempts` | my attempt history |
| `GET  /sysdesign/attempts/{id}` | resume: saved design + brief (no keys) |
| `POST /sysdesign/attempts/{id}/design` | save draft design (components/connections/decisions); 409 after submit |
| `POST /sysdesign/attempts/{id}/submit` | deterministic grade, persist, emit `sysdesign` signals; idempotent |
| `GET  /sysdesign/attempts/{id}/result` | full result + rubric review (expected components/decisions + feedback) — only AFTER submit |

Request validation: component/connection ids constrained to the scenario palette (reject unknown ids);
decision keys constrained to the scenario's prompts. Pydantic models inline in the router (studio/coding/
assessment style). `source_module="sysdesign"`.

Agent modules (new, additive):
- `agent/sysdesign_bank.py` — scenario loader + answer-key-stripping public views + palette/decision
  projections + bank stats (mirrors `assessment_bank.py`).
- `agent/sysdesign_eval.py` — deterministic rubric grading + per-dimension analytics + matched/missing
  requirements + canonical feedback.
- `agent/sysdesign_signals.py` — Phase 0 bridge (`source_module="sysdesign"`), union-validated concepts.

---

## 7. Frontend design (new pages under `pages/sysdesign/`)

Reuse the dark design system, `AppLayout`, `ui.jsx`, `useApi`, and `client.js`. Add `lib/sysdesign.js`
(scenario/difficulty/dimension/component metadata + icons). One new nav item ("System Design", e.g.
lucide `Network` / `Workflow` icon) in `AppLayout.NAV`.

| Page | Route | Contents |
|---|---|---|
| **A. Academy landing** | `/app/sysdesign` | scenario cards by difficulty, solved badges, "History" link, start |
| **B. Design workspace** | `/app/sysdesign/attempt/:id` | brief + requirements panel; component palette; added-components list; connection builder (from/to selects); structured decision prompts (DB/API/scalability/reliability/trade-offs); autosave; submit confirmation |
| **C. Result** | `/app/sysdesign/result/:id` | overall score + per-dimension bars; matched vs missing requirements; trade-off feedback; expected-design review; links into Dashboard/Planner |
| **D. History** | `/app/sysdesign/history` | previous attempts, scores, dates, scenario, improvement-over-time |

Client methods to add to `api`: `sysdesignScenarios`, `sysdesignScenario`, `sysdesignStart`,
`sysdesignAttempts`, `sysdesignAttempt`, `sysdesignSaveDesign`, `sysdesignSubmit`, `sysdesignResult`.

Canvas MVP: a structured list + connection builder (deterministic, gradable, accessible). An SVG/
drag-drop visual layer can render the same component/connection model on top later without backend change.

---

## 8. Backend implementation plan (sequence within Phase 4)

1. `agent/data/sysdesign_concepts.json` — ~12–18 concept ids across scaling/data/API/reliability.
2. `agent/data/sysdesign_scenarios.json` — 5–8 scenarios × rubric (requirements, palette, decision
   prompts + acceptable sets, weights, canonical trade-offs, feedback strings).
3. `agent/sysdesign_bank.py` — loader + public views (strip rubric keys/weights) + validation + stats.
4. `agent/sysdesign_eval.py` — deterministic grading (component coverage, valid connections, decision
   exact/subset matches per rubric, trade-off multi-select) → per-dimension score + feedback.
5. `agent/sysdesign_signals.py` — emit `sysdesign` signals (correct dimension → mastered/medium; weak →
   struggled/medium), union-validated; then `learner_model.update`.
6. `agent/db.py` — add table to SCHEMA + 5 CRUD functions.
7. `api/routers/sysdesign.py` — the 8 endpoints; register in `api/main.py` (one import + one include).
8. Frontend: `lib/sysdesign.js`, 4 pages, client methods, routes, nav.

---

## 9. Testing strategy (new file `tests/test_sysdesign.py`)

Follow the `test_assessment.py` template (`client` fixture, mock mode, `_reg`/`_auth`). Required cases:
- **Scenario bank validation**: ≥N scenarios; every rubric concept id resolves to the union taxonomy;
  palette ids referenced by the rubric exist; decision prompts have defined acceptable sets; no dup ids.
- **Catalog/brief protection**: scenario brief and in-progress attempt payloads contain NO rubric weights
  or correct keys; result endpoint 409s before submit, exposes expected design only after.
- **Deterministic grading**: perfect design → full score; missing required component → lower score +
  listed as missing; invalid connection (unknown id) rejected; decision exact/subset scoring; trade-off
  multi-select exact logic.
- **Lifecycle**: start → save draft → restore (refresh) → submit; duplicate submit idempotent;
  save-after-submit → 409.
- **Auth/authorization**: 401 without token; cross-student access → 403.
- **Phase 0 integration**: a strong submission makes its `sysdesign` concepts tracked in
  `/students/{id}/skills`, records a `sysdesign_scored` activity event.
- **Regression**: run the full suite (expect 166 existing + new to all pass).

Frontend: `npm run build` must stay green; capture screenshots of the 4 pages with real seeded data
(dev-only Playwright harness, as used for Phases 2–3).

---

## 10. Implementation sequence (checkpoints)

1. Data files (concepts + scenarios) → validate by a tiny load check.
2. Bank + eval + signals modules + their unit tests (no HTTP) → green.
3. DB tables + CRUD → migration/no-op verified.
4. Router + registration → API lifecycle tests → green.
5. Full backend suite → confirm 166 existing still pass + new pass.
6. Frontend lib + client + pages + routes + nav → `npm run build` green.
7. Live screenshots of all 4 pages (mock backend) → 0 console errors.
8. Final verification report (verified vs. manual).

---

## 11. Risks and dependencies

- **Diagram richness vs. determinism.** A freehand drag-and-drop diagram is hard to grade deterministically
  and risks scope creep. **Mitigation:** MVP is a structured component/connection/decision model (fully
  gradable); a visual layer renders the same model later with no backend change. Confirm this scope is
  acceptable.
- **Recommendation target mapping.** `skills/recommend.py._rec` hardcodes `target_module="interview"` and
  `_topic_for_concept()` maps concepts only via the interview question bank. SysDesign concepts will still
  surface in mastery, misconceptions, and recommendation *reasons/priority*, but their `target_ref` would
  be `null` (no interview topic). **Approved stance:** ship the Phase 4 MVP with a `null` target for SD
  recommendations, and INVESTIGATE a backward-compatible extension (§13) WITHOUT modifying `recommend.py`
  in this phase. Implementing that extension is a separate, explicitly-approved change.
- **Concept taxonomy design.** Picking the right ~12–18 SD concept ids up front matters (renaming later
  orphans signals). **Mitigation:** curate the taxonomy first and freeze it before writing scenarios.
- **Rubric subjectivity.** System design is inherently open-ended; a deterministic rubric necessarily
  rewards a canonical "acceptable set." **Mitigation:** state this honestly in-product (like the mock/
  demo labels elsewhere), keep rubrics generous (subset/any-of matches), and show expected design on
  review. No fabricated precision.
- **No new dependencies / no AWS / no Bedrock** — by design, grading is deterministic. Honors Phase 4
  rules. (A future phase could add optional LLM feedback behind the existing `config.is_mock()` guard;
  explicitly deferred.)
- **Performance/security**: payloads are small JSON; validate component/connection/decision ids against
  the scenario server-side (reject unknown ids) to prevent oversized or malformed submissions; enforce a
  max design size; all grading server-side; ownership on every route. No user data deleted.

---

## 12. Explicit non-goals for Phase 4

- No AWS/Bedrock/Translate; no new runtime dependencies; no Strands-Ship recipe commands.
- No changes to Phase 0–3 source (the only possible exception — extending `recommend.py` for SD targets —
  is flagged as out of scope and requires separate approval).
- No Phase 5 assumptions.


---

## 13. Recommendation target-mapping investigation (design only — recommend.py NOT modified)

**Goal:** let SD recommendations carry a usable practice target, without regressing interview/coding/
assessment recommendations.

**Finding (current behavior):** `skills/recommend.py._rec(...)` returns a fixed
`{"action", "target_module": "interview", "target_ref": _topic_for_concept(concept_id), ...}`.
`_topic_for_concept` scans only `interview.QUESTION_BANK`, so any concept not present there (all SD
concepts) yields `target_ref=None`, and `target_module` is always `"interview"`. Consumers:
`api/routers/learning.py` `/students/{id}/recommendations` returns `recommend.rank(...)` verbatim; the
frontend `RecommendationList.jsx` renders `reason` + links to `/app/practice`.

**Backward-compatible extension (proposed for a SEPARATE approval):** make the module resolve a target by
*concept namespace* instead of assuming interviews, with interview behavior unchanged as the default:
- Add a pure helper (new function, no signature change to `rank`/`top`) that maps a concept_id to
  `(target_module, target_ref)`: interview topic if the concept is in the interview bank (unchanged path);
  else if it is an SD concept id, `("sysdesign", <scenario_id or null>)`; else keep the current default.
- `_rec` calls this helper instead of hardcoding `"interview"`. Existing interview concepts resolve
  identically (same module, same topic) → **no change to current outputs**; SD concepts gain a target.
- Frontend `RecommendationList.jsx` would branch its link by `target_module` (`/app/sysdesign` vs
  `/app/practice`). This is a Phase 0/frontend-shared edit and is therefore **gated**.

**Compatibility test (to accompany that separate change):** snapshot `recommend.rank()` output for an
interview-only student BEFORE and AFTER the edit and assert equality (no regression), plus a new case
asserting SD concepts resolve to `target_module="sysdesign"`.

**This phase:** implement nothing here. SD recommendations ship with `target_ref=null` and still appear by
mastery/misconception/priority. The extension is pre-designed above so it can be approved and applied in
one tightly-scoped follow-up.

---

## 14. Exact file manifest

### 14.1 Files to CREATE (all additive)
Backend data:
- `agent/data/sysdesign_concepts.json` — SD concept taxonomy (~12–18 ids).
- `agent/data/sysdesign_scenarios.json` — 5–8 scenarios + rubrics (server-owned).

Backend logic:
- `agent/sysdesign_bank.py` — loader, public views (strip rubric), validation, stats.
- `agent/sysdesign_eval.py` — deterministic rubric grading + per-dimension analytics + feedback.
- `agent/sysdesign_signals.py` — `source_module="sysdesign"` Phase 0 bridge (union-validated concepts).

Backend API:
- `api/routers/sysdesign.py` — the 8 `/sysdesign` endpoints.

Frontend:
- `frontend/src/lib/sysdesign.js` — scenario/difficulty/dimension/component metadata + icons.
- `frontend/src/pages/sysdesign/SysDesignAcademy.jsx` — landing (scenario list).
- `frontend/src/pages/sysdesign/SysDesignWorkspace.jsx` — design canvas (attempt).
- `frontend/src/pages/sysdesign/SysDesignResult.jsx` — result + review.
- `frontend/src/pages/sysdesign/SysDesignHistory.jsx` — attempt history.

Tests:
- `tests/test_sysdesign.py` — bank validation, grading, lifecycle, auth/ownership, answer-key protection,
  Phase 0 integration.

Dev-only (not shipped; mirrors Phase 2/3 harnesses):
- `frontend/scripts/shoot-sysdesign.mjs` — Playwright screenshot harness (dev dependency already present).

### 14.2 Existing files proposed for MODIFICATION (additive edits only; NO Phase 0–3 logic changed)
- `agent/db.py` — append the `sysdesign_attempt` table to the `SCHEMA` string (new `-- Phase 4` section)
  and append 5 CRUD functions at end of file. No existing table/column/function altered.
- `api/main.py` — add `from .routers import sysdesign as sysdesign_router` and one
  `app.include_router(sysdesign_router.router)` line. No other change.
- `frontend/src/api/client.js` — add 8 `sysdesign*` methods to the `api` object. No existing method changed.
- `frontend/src/App.jsx` — add 4 `<Route>` entries + 4 imports. No existing route changed.
- `frontend/src/components/AppLayout.jsx` — add one `NAV` entry (+ one lucide icon import). No other change.

**NOT modified in this phase:** `skills/recommend.py` (see §13), `skills/signals.py`,
`skills/learner_model.py`, `activity.py`, `fairscore.py`, `concepts.json`, `assessment_concepts.json`, and
all Phase 1/2/3 modules/routers/pages. `agent/data/concepts.json` is never touched (preserves the measured
FairScore surface).

### 14.3 Note on PostFileSave hook / measured results
Creating `agent/data/sysdesign_*.json` will trigger the "data changed" hook. These are additive Phase 4
files that do NOT touch the FairScore scoring path or the measured cases, so `results/MEASURE.md` stays
valid and `ss measure` is NOT required (and Bedrock is out of scope). No FAILURES.md entry (not a
failing-case fix). This will be reaffirmed in the final report.

---

## 15. Database migration plan

- **Mechanism:** the existing `init_db()` runs `executescript(SCHEMA)` (CREATE TABLE IF NOT EXISTS) then
  `_migrate()` (idempotent ALTER ADD COLUMN driven by `_EXPECTED_COLUMNS`).
- **Phase 4 change:** add exactly one new table (`sysdesign_attempt`) + one index to `SCHEMA`. Because it
  is `CREATE TABLE IF NOT EXISTS`, a fresh DB gets it on startup and an existing DB (with Phase 0–3 data)
  gets it added on next `init_db()` **without migration, without dropping anything, without touching any
  existing row**. No entry is added to `_EXPECTED_COLUMNS` (that list is only for adding columns to
  pre-existing tables).
- **No destructive operations.** No DROP, no data deletion, no schema change to `student`, `interview`,
  `answer`, `skill_signal`, `learner_concept`, `activity_event`, `studio_*`, `coding_submission`,
  `assessment_attempt`.
- **Rollback:** dropping Phase 4 is reversible — removing the `include_router` line makes the endpoints
  disappear; the unused `sysdesign_attempt` table can be left in place harmlessly or dropped manually.
- **Verification:** `tests/test_migration.py` plus a fresh-DB `init_db()` run; confirm the full suite
  (166 existing) still passes after the schema addition.
