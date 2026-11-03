# CareerLift AI — Product Architecture Blueprint

*Evolution plan for the existing React + FastAPI + SQLite + Strands application. This is a blueprint, not
a rewrite: every section builds on the current code described in `ARCHITECTURE_AUDIT.md`. No existing
source was modified to produce this document — it is the only new file written in this phase.*

> Source-of-truth rules carried from the audit and honored throughout:
> 1. `agent/fairscore.py` remains the immutable authority for all bands; the model never emits a score.
> 2. Tables are **extended via migrations** (`db._migrate` pattern) — never dropped or recreated.
> 3. `bedrock` and `mock` model modes stay first-class; never switch silently.
> 4. Every metric is real or an honest empty state — no fabricated statistics.
> 5. No internal technology names (Strands / Bedrock / Nova / FastAPI / Python) surface in the UI.

---

## 0. Guiding product thesis (why this is not six apps or a LeetCode clone)

CareerLift AI's differentiator is **one learner knowledge model** fed by every module. A coding mistake,
an MCQ error, an interview answer, and a system-design exercise all write to the **same** skill/concept
graph, and the **same** FairScore principle (separate *what you know* from *how you said it*, never
penalize plain English) governs any human-language evaluation across all six modules.

The six modules are **surfaces**; the shared Learning Intelligence (Module 5) is the **spine**. If we
removed the shared spine, we would have a LeetCode clone plus four side tools. We are building the spine
first-class and treating the surfaces as producers/consumers of it.

Concretely, the integration contract is:
- Every module emits **SkillSignals** (concept_id, outcome, evidence, confidence, source_module).
- Learning Intelligence consumes SkillSignals → updates a **LearnerModel** (per-concept mastery + the
  existing misconception tally) → produces **Recommendations** consumed by the Career Dashboard, the
  Learning Planner, and each module's "what next" surface.

---

## A. Existing system mapping (capability → status)

Legend: **DONE** implemented · **PART** partial · **EXT** needs extension · **NEW** missing.

### Module 1 — Interview Studio
| Capability | Status | Where today |
|---|---|---|
| Single-question technical interview | DONE | `agent/interview.py`, `POST /interviews`, `Practice.jsx` |
| Dual-axis FairScore feedback | DONE | `agent/fairscore.py`, `POST /score` |
| Multi-question sessions | NEW | `interview`/`answer` are single-question today |
| Follow-up questions | NEW | — |
| Behavioral interviews | EXT | FairScore communication axis exists; needs behavioral rubric + question bank |
| Coding interviews | EXT | depends on Module 2 execution |
| Voice interviews | NEW | `session.py` scaffolding only; no audio pipeline |

### Module 2 — Coding Arena
| Capability | Status | Where today |
|---|---|---|
| DSA problem library / filters / difficulty | NEW | — |
| Code editor + language selection | NEW | — |
| Test-case execution (run/submit) | NEW | — (must be sandboxed; see §H) |
| Submission history | EXT | `answer` table pattern reusable; new `submission` table needed |
| Complexity analysis, debugging feedback | NEW | FairScore technical pattern reusable for *explanation* grading |
| Daily challenges / study plans | NEW | planner pattern reusable |

### Module 3 — Technical Assessment
| Capability | Status | Where today |
|---|---|---|
| Topic MCQs, timed assessments | NEW | — |
| Java/Python/SQL/CS-fundamentals banks | NEW | concept reference (`agent/data/concepts.json`) is the seed taxonomy |
| Explanations for wrong answers | EXT | misconception copy (`frontend/src/lib/content.js`) reusable |
| Performance analytics | EXT | history/reporting patterns reusable |

### Module 4 — System Design Academy
| Capability | Status | Where today |
|---|---|---|
| HLD/LLD lessons, case studies, diagrams | NEW | — |
| Interactive design exercises + evaluation | NEW | FairScore rubric pattern reusable for qualitative grading |
| Progress tracking | EXT | reuse LearnerModel |

### Module 5 — Learning Intelligence (the spine)
| Capability | Status | Where today |
|---|---|---|
| Misconception detection | DONE | `agent/fairscore.py` (grounded, signature-matched) |
| Learning planner (single source) | PART | `agent/planner.py` reads misconception tally only |
| Cross-module skill-gap analysis | NEW | needs LearnerModel + SkillSignals |
| Spaced repetition / targeted revision | NEW | `misconception.last_seen`/`count` are the seed signals |
| Recommendations across ALL modules | NEW | planner is DSA/interview-only today |

### Module 6 — Career Dashboard
| Capability | Status | Where today |
|---|---|---|
| Per-student dashboard | PART | `Dashboard.jsx` (interview-only) |
| History / progress / reports | PART | `Progress.jsx`, `Reports.jsx` (interview-only) |
| Activity calendar, streaks, achievements | NEW | needs an activity/event log |
| Unified mastery across modules | NEW | needs LearnerModel |

**Reused infrastructure (all modules):** auth (`api/auth.py`), DB + migrations (`agent/db.py`), config/
model-mode (`agent/config.py`), mock mode (`agent/mockmodel.py`), FairScore (`agent/fairscore.py`),
input gate (`agent/gates.py`), the React design system (`frontend/src/components/*`), API client
(`frontend/src/api/client.js`), and the fetch hook (`frontend/src/lib/useApi.js`).

---

## B. Frontend architecture

### B1. Navigation (evolve the existing sidebar, don't replace it)
Current sidebar: Dashboard · Practice Interview · My Progress · Misconceptions · Learning Planner ·
Reports. Evolved top-level nav (grouped), reusing `AppLayout.jsx`:

```
Career Dashboard            (Module 6 — home)
Interview Studio            (Module 1)  ├ Technical ├ Behavioral ├ Coding ├ Voice
Coding Arena                (Module 2)  ├ Problems ├ Editor ├ Submissions ├ Daily
Assessments                 (Module 3)  ├ Browse ├ Take ├ Results
System Design Academy       (Module 4)  ├ Learn ├ Case Studies ├ Practice
Learning Planner            (Module 5 surface)
```
"My Progress", "Misconceptions", and "Reports" fold **into** Career Dashboard tabs (their current pages
remain as the tab bodies — reused, not deleted).

### B2. Route structure (additive under `/app`)
```
/app                         Dashboard (existing, extended)
/app/interview               Interview Studio hub
/app/interview/session/:id   multi-question session runner (new)
/app/interview/voice/:id     voice runner (new, Module 1 voice)
/app/practice                existing single-question Practice (kept as a quick-drill entry)
/app/coding                  Coding Arena library
/app/coding/problem/:slug    problem + editor
/app/coding/submissions      submission history
/app/assess                  Assessment browse
/app/assess/:id              assessment runner
/app/system-design           Academy learn/case studies
/app/system-design/:lessonId lesson / exercise
/app/planner                 existing planner (extended to all modules)
/app/progress, /app/misconceptions, /app/reports   existing (kept; linked from Dashboard tabs)
```

### B3. Reusable components (existing → new)
- **Reuse as-is:** `Card`, `SectionHeading`, `Spinner`, `LoadingBlock`, `EmptyState`, `ErrorState`,
  `Toast`, `Badge`, `BandBar`, `BandGauge` (`ui.jsx`); `AppLayout`, `Logo`, `ProgressChart`;
  `useApi`, `AuthContext`, `api/client.js`.
- **New shared:** `CodeEditor` (wrapper around a chosen editor lib), `MarkdownView` (lessons/case
  studies), `DiagramView` (system-design diagrams), `Timer`, `MCQOption`, `DifficultyPill`,
  `ActivityHeatmap`, `MasteryRadar`, `StreakBadge`, `ResultExplainer` (wrong-answer explanations).
- **New feature modules:** one folder per module under `src/pages/<module>/` mirroring the existing
  flat `pages/` convention.

### B4. User-journey principles
- Every module's result screen ends with a **"what next"** card driven by Learning Intelligence.
- Consistent four states on every data view (loading/empty/error/success) — the existing `ui.jsx`
  primitives enforce this.
- Accessibility: keyboard-first (the existing focus rings, `aria-live` states), color-contrast-safe band
  colors already defined in `tailwind.config.js`.

---

## C. Backend architecture

### C1. Module structure (additive packages; existing `api/`, `agent/` untouched)
Proposed new packages (new files only — nothing existing is edited):
```
api/
  main.py            (existing; new routers are included, not rewritten)
  routers/           (NEW) interview.py, coding.py, assessment.py, sysdesign.py,
                     learning.py, dashboard.py        # one APIRouter per module
agent/
  (existing scoring core untouched)
  skills/            (NEW) signals.py, learner_model.py, recommend.py   # Learning Intelligence
  content/           (NEW) problems/ assessments/ sysdesign/            # static curated banks (JSON)
exec/                (NEW, separate service) sandbox runner for code (see §H) — NOT in FastAPI process
```
> `main.py` will eventually `include_router(...)` the new routers. That is an **addition** to `main.py`
> at implementation time, agreed per-phase — this blueprint does not edit it now.

### C2. Service boundaries
- **Deterministic services (no model):** problem catalog, MCQ grading, test-case comparison, complexity
  heuristics, spaced-repetition scheduling, mastery aggregation, streaks/activity. These are plain
  Python — do **not** use an agent for them.
- **Model-assisted services (bedrock or mock):** interview answer extraction (existing), behavioral-answer
  extraction, debugging-hint generation, system-design qualitative feedback. Each follows the existing
  pattern: the model **extracts/explains**, deterministic code **decides** the band.

### C3. Representative new endpoints (contracts)
All require bearer auth and authorize on the token owner, matching the existing pattern.

```
# Module 1 — sessions
POST /sessions                        -> {session_id, kind, first_question}      kind: technical|behavioral|coding
POST /sessions/{id}/answer            -> {feedback: ScoreResponse, next_question|null}
GET  /sessions/{id}                   -> session transcript + per-answer bands

# Module 2 — coding
GET  /problems?topic=&difficulty=&q=  -> [{slug,title,difficulty,topics}]
GET  /problems/{slug}                 -> {statement, examples, starter_code, languages}
POST /problems/{slug}/run             -> {results:[{case, passed, stdout, time_ms}], label:"run"}  (hidden cases excluded)
POST /problems/{slug}/submit          -> {verdict, passed/total, complexity_hint, submission_id}
GET  /submissions                     -> submission history for the student

# Module 3 — assessments
GET  /assessments?topic=&kind=        -> catalog
POST /assessments/{id}/start          -> {attempt_id, questions:[...], time_limit_s}
POST /assessments/{id}/submit         -> {score_summary, per_question:[{correct, explanation}]}

# Module 4 — system design
GET  /sysdesign/lessons               -> learning path
GET  /sysdesign/lessons/{id}          -> {content_md, diagram, exercise?}
POST /sysdesign/exercises/{id}/submit -> {feedback bands (qualitative), rubric_hits}

# Module 5 — learning intelligence
GET  /students/{id}/skills            -> LearnerModel snapshot (per-concept mastery + misconceptions)
GET  /students/{id}/recommendations   -> ranked next actions across ALL modules
GET  /students/{id}/next              -> (existing; becomes a thin wrapper over recommendations)

# Module 6 — dashboard
GET  /students/{id}/overview          -> unified counts, streak, recent activity, mastery radar
GET  /students/{id}/activity          -> activity-log events for the calendar/heatmap
```
Response bodies keep the existing discipline: bands not raw numbers, no internal ids leaked, honest
empty states.

### C4. Strands agent responsibilities (minimal, deliberate)
Reuse the **existing two extractor agents** (`evaluate.py`, `coach.py`). Add **at most**:
- a **behavioral extractor** (reuses the Communication Coach; adds STAR-structure observations — still
  no grammar/accent penalty),
- a **design-feedback extractor** (extracts which rubric points a design addresses; code decides bands).
No swarm, no agents-as-tools, no per-feature agent. Everything schedulable deterministically stays
deterministic (the audit's rule, reaffirmed).

---

## D. Database architecture (extensions only, migration-compatible)

Follow `agent/db.py`'s `_EXPECTED_COLUMNS` + `_migrate` convention: add tables/columns idempotently,
never drop. Existing tables (`student`, `auth_token`, `interview`, `answer`, `misconception`) are
preserved untouched; new ones are additive.

### D1. New entities (conceptual schema)
```
session(id, student_id, kind, created_at, completed_at)
session_question(id, session_id, ordinal, question, expected_concepts, kind, parent_question_id)
session_answer(id, session_question_id, answer_text, technical_band, communication_band,
               abstained_technical, abstained_communication, misconception_tags, created_at)

problem(slug, title, difficulty, topics_json, statement_md, starter_json, created_at)   # curated bank
testcase(id, problem_slug, input, expected_output, is_hidden)
submission(id, student_id, problem_slug, language, code, verdict, passed, total,
           complexity_hint, created_at)

assessment(id, title, kind, topic, time_limit_s)
question_mcq(id, assessment_id, stem, options_json, answer_index, explanation_md, concept_id)
attempt(id, student_id, assessment_id, started_at, submitted_at, score_correct, score_total)
attempt_answer(id, attempt_id, question_id, chosen_index, correct)

sd_lesson(id, path, ordinal, title, content_md, diagram_ref)
sd_exercise(id, lesson_id, prompt_md, rubric_json)
sd_submission(id, student_id, exercise_id, response_md, rubric_hits_json, created_at)

# Learning Intelligence (the spine)
skill_signal(id, student_id, concept_id, source_module, outcome, confidence, evidence_ref, created_at)
learner_concept(student_id, concept_id, mastery, attempts, last_seen)   # derived, rebuildable from signals
activity_event(id, student_id, kind, ref_id, created_at)                # feeds streaks/calendar
```

### D2. Relationships & indexes
- `skill_signal.concept_id` and `learner_concept.concept_id` key to the **existing** concept reference
  ids (`agent/data/concepts.json`) extended with new modules' concepts — one shared taxonomy.
- Indexes: `skill_signal(student_id, created_at)`, `learner_concept(student_id, mastery)`,
  `submission(student_id, created_at)`, `attempt(student_id)`, `activity_event(student_id, created_at)`.
- `learner_concept` is a **cache** derived from `skill_signal`; it can be rebuilt, so a migration can
  recompute it safely.

### D3. Migration strategy
- Add new `CREATE TABLE IF NOT EXISTS` blocks to the schema and new entries to `_EXPECTED_COLUMNS` for
  any column added to an existing table. `init_db()` already creates-then-migrates and is idempotent.
- Never alter the meaning of existing columns. New per-answer signals are written to `skill_signal`, not
  by changing `answer`.

---

## E. Shared Learning Intelligence (the central differentiator)

### E1. The data path (every module feeds one model)
```
module produces a result
  → emit SkillSignal(concept_id, source_module, outcome∈{mastered,partial,struggled,misconception},
                     confidence, evidence_ref)
  → skill_signal row inserted (append-only, auditable)
  → learner_model.recompute(student, concept) updates learner_concept.mastery
  → recommend.rank(student) produces ordered next actions
  → surfaced in Dashboard / Planner / each module's "what next"
```

**Signal sources (deterministic mapping, no model needed to emit signals):**
- Coding Arena: test-case pass ratio + which concepts the problem tags → mastered/struggled.
- Assessments: per-MCQ correctness + `concept_id` → mastered/struggled; a known distractor → misconception.
- Interview Studio: existing FairScore output — `supported`→mastered, `partial`→partial,
  grounded `incorrect` matched to a signature → **misconception** (reuses `fairscore` exactly).
- System Design: rubric-point hits → partial/mastered per design concept.

### E2. Mastery model (honest, explainable, local)
`mastery ∈ [0,1]` per concept = a transparent, deterministic function of recent signals
(recency-weighted success rate), **not** an opaque ML model. We show it as a band/label, never as a
fabricated percentage unless it is a real computed ratio with its denominator shown. Misconceptions
remain a separate, stronger signal (a demonstrated wrong belief), exactly as FairScore defines them.

### E3. Recommendations
Deterministic ranking: (1) open misconceptions first (highest `count`, most recent), (2) concepts with
lowest mastery that are prerequisites for the student's stated goal, (3) spaced-repetition due items
(`last_seen` + interval). Each recommendation carries a **reason** string (the existing planner already
does this). No model call is required to recommend; a model may *phrase* the suggestion only.

### E4. Tracking improvement
Because `skill_signal` is append-only, before/after is real: mastery deltas over time per concept, and
"misconception resolved" when a previously-failing concept accumulates N consecutive successes. The
Dashboard shows these as genuine trends (empty state until data exists).

---

## F. FairScore integration (unchanged authority, extended reach)

- `agent/fairscore.py` stays the **only** place bands are decided. New modules call its functions; none
  reimplements scoring.
- Technical vs communication independence is preserved and **extended**: behavioral answers get a
  communication/STAR read and a separate content read; coding "explain your approach" uses the technical
  axis for correctness and the communication axis for the explanation — never blended.
- The no-penalty rule (grammar, accent, vocabulary, length, English fluency never lower a technical
  band) applies to **every** human-language evaluation in every module. The Communication Coach prompt
  and `comm_band` already enforce this and are reused verbatim.
- The model never decides a final score anywhere: it extracts claims/observations/rubric-hits; code
  computes the band; abstention is fail-closed. This invariant is a review gate for every new module.

---

## G. Voice Interview architecture (honest about cost/privacy)

### G1. Capture (browser-native, zero external cost)
- Microphone permission + capture via the browser `MediaRecorder` / `getUserMedia` (native, free).
- Turn management is UI state: record → stop → transcribe → agent responds → next turn.

### G2. Speech-to-text — three options, with trade-offs
| Option | Cost | Privacy | Quality | Verdict |
|---|---|---|---|---|
| **Browser Web Speech API** (Chrome) | Free | Audio may be sent to the browser vendor's servers | Good EN, device-dependent | Default for the **local demo**; label it clearly |
| **Local Whisper (e.g. whisper.cpp / faster-whisper)** | Free (compute) | Fully local, private | Strong, offline | Best privacy; heavier setup; optional |
| **Cloud STT (Amazon Transcribe etc.)** | **Paid** | Audio leaves device | Strong, Tamil `ta-IN` | Out of scope until explicitly approved (billable) |

**Recommendation:** ship the demo on the browser Web Speech API (free, no server audio handling),
clearly disclosing that transcription uses the browser's built-in service; offer local Whisper as an
opt-in privacy upgrade. Keep text, not raw audio, as the thing scored — reuse the **existing** text
scoring pipeline, so voice adds an input method, not a new scoring path.

### G3. Interviewer responses & feedback
- Interviewer question text comes from the deterministic bank + (optional) model phrasing.
- The student's transcribed answer flows into the **existing** `/score` path → same FairScore bands.
- Optional TTS for the interviewer voice: browser `SpeechSynthesis` (free). Nova Sonic/Polly are paid and
  out of scope for the free local demo; Nova Sonic also has no Tamil (documented in the catalogue).

### G4. Privacy notes to surface in UI
Mic access is explicit and per-session; audio is not stored server-side in the demo (only the transcript
text is, as with typed answers); the STT provider is disclosed. No audio leaves the device if local
Whisper is chosen.

---

## H. Coding execution architecture (never run untrusted code in FastAPI)

**Hard rule:** untrusted student code must never execute in the FastAPI process or with app privileges.

### H1. Options compared
| Approach | Isolation | Cost | Complexity | Verdict |
|---|---|---|---|---|
| In-process `exec()` | **None** | Free | Trivial | **Rejected** — remote code execution risk |
| Subprocess + OS limits (rlimits, nobody user, no network) | Weak–moderate | Free | Low | Acceptable **only** for a single-language, locked-down local demo |
| **Container-per-run** (Docker: no-network, read-only FS, CPU/mem/time caps, non-root) | Strong | Free locally (Docker Desktop already present) | Moderate | **Recommended** default |
| microVM (Firecracker/gVisor) | Strongest | Free locally / infra later | High | Future / production |
| Hosted judge API (Judge0 self-host, or SaaS) | Strong | Self-host free / SaaS **paid** | Moderate | Self-host optional; SaaS out of scope (cost) |

### H2. Recommended design (local, zero external cost)
A **separate execution service** (`exec/`), not the API process:
- Receives `{language, code, testcases}`; runs each case in a **short-lived container** with: no network,
  read-only rootfs + tmpfs scratch, non-root user, CPU/memory/wall-time limits, output size cap.
- Returns `{per_case: passed/stdout/time_ms}`; the API compares against expected outputs **deterministically**
  (no model) and records a `submission`.
- Docker Desktop is already installed on this machine (seen in the environment), so local containerized
  execution needs no new paid service.
- Language support grows by adding images (python, node, openjdk, a SQL runner). Start with **one or two**
  languages for the demo; expand later.

### H3. Complexity analysis & debugging feedback
- Complexity "hint" is a **heuristic/label**, not a proof — derived from measured time across input sizes
  or static patterns, and clearly labelled as an estimate (never a fabricated Big-O claim).
- Debugging feedback uses the model to *explain* a failing case; the pass/fail verdict is always the
  deterministic test-case comparison.

---

## I. System Design Academy experience

### I1. Content model
- **Lessons** (`sd_lesson`): markdown content + an optional diagram reference, ordered into learning
  paths (HLD path, LLD path). Rendered with `MarkdownView` + `DiagramView`.
- **Diagrams:** author as text-based diagrams (e.g. Mermaid) stored with the lesson, rendered client-side
  — zero external cost, versionable, accessible. Interactive "build the diagram" exercises can start as
  guided drag/drop of predefined components (deterministic grading against a rubric).
- **Case studies:** real-world system walk-throughs (URL shortener, feed, chat, rate limiter) as
  structured lessons with trade-off tables.

### I2. Exercises & evaluation
- `sd_exercise` carries a **rubric** (`rubric_json`: the key decisions a good answer must address:
  data model, scaling, consistency, bottlenecks, trade-offs).
- The student's written design → a **design-feedback extractor** (model) extracts which rubric points are
  addressed with grounded evidence → **deterministic** code maps rubric coverage to bands (same FairScore
  pattern). No single blended score; "coverage" + "communication" are separate.
- Progress feeds `skill_signal` (system-design concepts), so the shared model tracks design skill too.

---

## J. Integrated user journeys (modules working together)

### Journey 1 — "Struggled in a mock interview → targeted recovery"
1. Student does a **technical interview** (Module 1); FairScore marks `C-HASH-AVG` as a grounded
   misconception (always-O(1)).
2. A **SkillSignal(misconception, C-HASH-AVG, source=interview)** is written; `misconception` tally bumps.
3. **Learning Intelligence** ranks this top; **Career Dashboard** shows "1 misconception to fix" and the
   **Planner** recommends: read the hashing concept → attempt a hashing **MCQ** (Module 3) → solve a
   hashing **coding problem** (Module 2).
4. Student passes the MCQ and the coding tests; two **mastered** signals for `C-HASH-AVG` arrive.
5. After N successes with no recurrence, Learning Intelligence marks the misconception **resolved**; the
   Dashboard streak and mastery radar update with **real** deltas.

### Journey 2 — "Coding interview blends execution + explanation"
1. Student starts a **coding interview session** (Module 1 + Module 2): solve a problem *and* explain it.
2. Code runs in the **sandbox** (Module 2 exec service) → deterministic pass/fail + complexity hint.
3. The spoken/typed **explanation** → FairScore: technical axis (is the reasoning correct?) and
   communication axis (is it clear?) **independently**.
4. Session feedback shows three separate things: tests passed, technical band, communication band — never
   merged. Signals for the problem's concepts flow to the shared model.

### Journey 3 — "Assessment reveals a gap → system-design path unlocks"
1. Student takes a timed **CS-fundamentals assessment** (Module 3); misses caching/consistency questions.
2. Wrong-answer **explanations** show immediately; struggled signals written for those concepts.
3. **Learning Intelligence** detects a system-design-adjacent gap and recommends the **System Design
   Academy** caching lesson + case study (Module 4).
4. Student completes the lesson and a design exercise; rubric-coverage signals raise mastery; the
   **Dashboard** shows progress across Assessment **and** System Design from one gap.

---

## K. Implementation roadmap (incremental phases)

Each phase is independently shippable, reuses existing infra, and adds only new files + additive
migrations. "main.py/router include" and "AppLayout nav entry" are additive edits agreed per phase.

### Phase 0 — Foundations for growth (no new module yet)
- **Features:** Learning Intelligence skeleton (SkillSignal + LearnerModel + recommend), activity log,
  Dashboard becomes the unified home (tabs wrap existing Progress/Misconceptions/Reports).
- **Reuse:** `fairscore`, `planner`, `db` migration pattern, all `ui.jsx`, `Dashboard.jsx`.
- **New:** `agent/skills/{signals,learner_model,recommend}.py`; `api/routers/{learning,dashboard}.py`;
  tables `skill_signal`, `learner_concept`, `activity_event`.
- **DB:** additive tables; backfill signals from existing `answer` rows (optional one-off recompute).
- **API:** `/students/{id}/skills`, `/recommendations`, `/overview`, `/activity`; `/next` rewrapped.
- **Frontend:** Dashboard tabs + mastery radar + activity heatmap (new shared components).
- **Deps:** none server-side; frontend may add a heatmap/radar (or draw with existing recharts/SVG).
- **Testing:** deterministic unit tests for signal→mastery→recommendation; API tests with mocked model;
  zero-AWS assertion continues.
- **Risks:** defining mastery transparently (keep it a simple explainable ratio); avoid fabricated %.

### Phase 1 — Interview Studio: multi-question + behavioral (highest demo value)
- **Features:** multi-question sessions, follow-ups, behavioral interviews.
- **Reuse:** `/score`, `fairscore`, `interview.py` question bank, `Practice.jsx` as the per-question UI.
- **New:** `api/routers/interview.py` (sessions); `session*` tables; behavioral question bank + STAR
  observations (reuse Communication Coach); `pages/interview/*`, session runner.
- **DB:** `session`, `session_question`, `session_answer` (additive).
- **Testing:** session state machine, follow-up gating, behavioral rubric; mock-mode e2e.
- **Risks:** follow-up generation needs the model — keep deterministic fallbacks; abstention preserved.

### Phase 2 — Coding Arena (problems + sandboxed execution)
- **Features:** problem library, editor, run/submit against test cases, submission history, complexity hint.
- **Reuse:** auth, LearnerModel signals, submission pattern mirroring `answer`.
- **New:** `exec/` sandbox service (containerized, no network); `api/routers/coding.py`; `problem`,
  `testcase`, `submission` tables; curated problem bank JSON; `CodeEditor` component.
- **Deps:** a code-editor frontend lib; Docker (already present) for the runner. No paid service.
- **Testing:** sandbox isolation tests (no network, limits enforced, times out safely), deterministic
  verdict comparison, malicious-code containment checks.
- **Risks:** **security of code execution is the #1 risk** — must be containerized, never in-process
  (see §H). This phase is prerequisite-heavy; gate it behind a security review.

### Phase 3 — Technical Assessment (MCQs)
- **Features:** topic MCQs, timed attempts, wrong-answer explanations, analytics.
- **Reuse:** LearnerModel, misconception copy, reporting patterns — **entirely deterministic** (no model).
- **New:** `api/routers/assessment.py`; `assessment`, `question_mcq`, `attempt`, `attempt_answer` tables;
  curated MCQ banks; `Timer`, `MCQOption`, `ResultExplainer`.
- **Testing:** grading correctness, timing, signal emission. Pure unit tests, no AWS.
- **Risks:** low; mostly content authoring effort.

### Phase 4 — System Design Academy
- **Features:** lessons, case studies, diagrams, rubric-graded exercises, progress.
- **Reuse:** FairScore rubric pattern, LearnerModel, `MarkdownView`/`DiagramView`.
- **New:** `api/routers/sysdesign.py`; `sd_*` tables; content bank; design-feedback extractor.
- **Testing:** rubric-coverage → band mapping (deterministic); mock-mode feedback.
- **Risks:** qualitative grading must stay rubric-anchored, not an opaque model verdict.

### Phase 5 — Voice & polish
- **Features:** voice interview input (browser STT), optional local Whisper, dashboards/achievements polish.
- **Reuse:** the entire text scoring pipeline (voice only adds an input method).
- **New:** audio capture + transcription adapters; achievements.
- **Deps:** browser APIs (free); optional local Whisper (free compute). No paid cloud STT in the demo.
- **Testing:** transcript → existing `/score`; permission/empty-audio handling.
- **Risks:** browser STT variability; privacy disclosure; keep audio off the server.

---

## L. Prioritization (what to demo first)

**Initial public demonstration (most valuable, lowest external risk):**
1. **Phase 0 (Learning Intelligence spine + unified Dashboard)** — this is the differentiator; without it
   the rest looks like disconnected tools.
2. **Phase 1 (multi-question + behavioral interviews)** — builds directly on the strongest existing asset
   (FairScore) and shows the fair, dual-axis feedback live.
3. **Phase 3 (MCQ assessments)** — cheap, fully deterministic, feeds the spine immediately, demos
   cross-module recommendations quickly.

**Follow later (higher prerequisites/risk):**
4. **Phase 2 (Coding Arena)** — highest value but gated on secure sandbox execution; do it right, not fast.
5. **Phase 4 (System Design Academy)** — content-heavy; strong once the rubric grading is solid.
6. **Phase 5 (Voice)** — a compelling enhancement, but an input method on top of existing scoring; last.

Rationale: lead with the **integration story** (spine + two feeding modules) so the demo proves CareerLift
is one intelligent platform, not six apps. Coding execution — the flashiest but riskiest — follows once
the safe sandbox is in place.

---

## M. Unresolved decisions & open risks (to settle before building)

1. **Code sandbox substrate:** container-per-run (recommended) vs self-hosted Judge0 vs locked-down
   subprocess for a single language. Impacts Phase 2 scope and security posture.
2. **Which languages in the Coding Arena demo?** Start with 1–2 (Python + one more) to bound the runner.
3. **STT for voice:** browser Web Speech (free, vendor-processed) vs local Whisper (private, heavier).
   Needs a privacy decision.
4. **Mastery definition:** confirm the transparent ratio formula and how it maps to a band/label so it is
   never mistaken for a fabricated percentage.
5. **Content authoring ownership:** MCQ banks, problem sets, system-design lessons/case studies are
   substantial curated content — who authors/reviews, and are sources cited (the existing concept
   reference already cites sources; keep that discipline).
6. **Concept taxonomy growth:** all modules key to one shared concept id space; adding modules means
   extending `concepts.json` carefully to avoid id drift.
7. **Interpreter/run ergonomics (from the audit):** standardize one documented run path and a backend
   run script before multiplying moving parts — otherwise each new service worsens the current
   PowerShell-vs-WSL friction.
8. **Follow-up question generation** needs the model; define deterministic fallbacks so the feature
   degrades gracefully in mock mode and when scoring is unavailable (503).

---

## N. What stays invisible to users (product polish rule)
No screen names a model, SDK, cloud, or framework. Users see: interviews, problems, assessments, design
lessons, skills, recommendations, streaks. "Local demo mode" is the one honest exception — it is a
product-level disclosure, not an implementation leak.

*End of blueprint. No existing source files were modified; `PRODUCT_ARCHITECTURE_BLUEPRINT.md` is the
only file created in this phase.*
