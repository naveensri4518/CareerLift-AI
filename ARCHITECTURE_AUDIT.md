# CareerLift AI — Architecture Audit (read-only)

*Produced from inspection of the actual source on disk. No existing source files were modified,
moved, renamed, or deleted. This is the only new file written during this phase.*

---

## 0. Scope and method

I inspected the live source tree, the running SQLite database, and the frontend/backend wiring. Findings
below are grounded in the files and the database as they exist now — not from memory of earlier phases.

Verified at audit time:
- Project root layout (see §1).
- Live SQLite schema and row counts (see §4).
- Frontend `src/` file set and backend `agent/` + `api/` module set (see §2–§3).
- `.venv-win\Scripts\python.exe` exists (a Windows virtualenv was added since the last build phase).

---

## 1. System overview (what this product is today)

CareerLift AI is a **working, locally-runnable** interview-preparation platform with three tiers:

1. **Frontend** — React 18 + Vite SPA (`frontend/`), dark SaaS UI, 8 pages, token auth, charts.
2. **Backend API** — FastAPI (`api/`), 7 endpoints, bearer-token auth, CORS for the local dev frontend.
3. **Agent / scoring core** — the FairScore engine (`agent/`): Strands-SDK graph + deterministic
   Python owning all bands, with a **bedrock** mode and a **mock** (no-AWS) mode.
4. **Persistence** — SQLite (`careerlift.db`) for students, interviews, answers, misconceptions, tokens;
   Strands file-sessions scaffolding exists but is **not wired into scoring** (documented honestly).

It runs end-to-end locally today in **mock mode** (no AWS). Bedrock mode is intact but needs credentials.

---

## 2. Backend inventory (`agent/` + `api/`)

### 2a. API layer (`api/`)
| File | Role |
|---|---|
| `api/main.py` | FastAPI app, 7 routes, CORS, lifespan DB init, auth dependency, error mapping (400/401/403/404/409/503) |
| `api/schemas.py` | Pydantic request/response models (no internal ids/infra leaked) |
| `api/auth.py` | Local bearer-token auth: server-generated student id, SHA-256(token+pepper) storage, `current_student` dependency |

### 2b. Agent / scoring core (`agent/`)
| File | Role | Status |
|---|---|---|
| `app.py` | Orchestrator `run(case)`; input gate → extract → verify → deterministic bands; mode switch | Working |
| `fairscore.py` | **The FairScore engine** — verifier, `band_from_claims`, `comm_band`, fairness gap, misconception matching. Owns all facts. | Working, well-tested |
| `models.py` | Pydantic structured outputs (`Claim`, `TechnicalClaims`, `CommObservations`, `ScoreResult`) | Working |
| `config.py` | `CAREERLIFT_MODEL_MODE` switch + `ModelUnavailableError` | Working |
| `mockmodel.py` | Deterministic offline extractor (no AWS) | Working |
| `evaluate.py` / `coach.py` | Strands extractor agents (technical claims / communication observations) — bedrock path | Working (needs creds to invoke) |
| `baseline.py` | One-prompt baseline grader for `ss measure` | Working (bedrock) |
| `gates.py` | Deterministic PII/off-task input gate (hook + function) | Working |
| `verify`/misconception logic | Inside `fairscore.py`: id-validity, grounding, contradiction vs extraction-inconsistency, four states | Working |
| `interview.py` | Deterministic question bank (7 topics) + `generate_question` | Working |
| `planner.py` | Deterministic next-exercise selection from misconception tally | Working |
| `db.py` | SQLite persistence + idempotent migration + token storage | Working |
| `session.py` | Strands `FileSessionManager`/`SlidingWindow` constructors | **Scaffolding only — not wired into scoring** |
| `fairness_report.py` | Offline fairness-gap + accuracy + dataset validation | Working (used by analysis/tests, not the API) |
| `tools.py` / `plan.py` | Language helpers / back-compat shim | Working |
| `score.py` | Maps dual-axis results onto the `ss measure` harness contract | Working (measurement path) |

### 2c. Endpoints (as implemented in `api/main.py`)
| Method | Path | Auth | Model? | Notes |
|---|---|---|---|---|
| GET | `/health` | none | no | liveness |
| POST | `/register` | none | no | **server generates** student id + token; token shown once |
| POST | `/interviews` | bearer | no | returns a question; stores question + expected concepts server-side |
| POST | `/score` | bearer | **yes** (bedrock) / deterministic (mock) | the only model-touching route; PII → deterministic abstain |
| GET | `/students/{id}/next` | bearer | no | planner recommendation |
| GET | `/students/{id}/history` | bearer | no | interview history |
| GET | `/students/{id}/misconceptions` | bearer | no | misconception tally |

---

## 3. Frontend inventory (`frontend/src/`)

| Area | Files | Role |
|---|---|---|
| Entry / routing | `main.jsx`, `App.jsx` | Router, protected routes, auth gate |
| State | `context/AuthContext.jsx` | Session (server id + token) in `localStorage`, 401 → logout |
| API | `api/client.js` | Typed fetch client, error kinds, auth header, friendly messages |
| Hooks/content | `lib/useApi.js`, `lib/content.js` | Fetch-with-retry hook; topic/misconception/band copy + helpers |
| Components | `components/AppLayout.jsx`, `Logo.jsx`, `ui.jsx`, `ProgressChart.jsx` | Sidebar/topbar, UI primitives, states, band visuals, recharts chart |
| Pages | `Landing.jsx`, `Register.jsx`, `Dashboard.jsx`, `Practice.jsx`, `Progress.jsx`, `Misconceptions.jsx`, `Planner.jsx`, `Reports.jsx` | All 8 product pages |

---

## 4. Live database (`careerlift.db`) — verified at audit time

| Table | Rows | Columns |
|---|---|---|
| `student` | 2 | id, created_at |
| `auth_token` | 2 | token_hash, student_id, created_at |
| `interview` | 11 | id, student_id, role, level, topic, question, expected_concepts, created_at |
| `answer` | 2 | id, interview_id, question, expected_concepts, answer_text, technical_band, communication_band, abstained_technical, abstained_communication, misconception_tags, created_at |
| `misconception` | 0 | student_id, concept_id, tag, count, last_seen |
| `sqlite_sequence` | 2 | (sqlite internal) |

Observations:
- The migration-added `interview.question` and `interview.expected_concepts` columns are present and populated → migration ran successfully against the real DB.
- 11 interviews but only 2 answers → most interviews were started but not scored (consistent with the earlier Bedrock credential failures; scoring only began working in mock mode).
- `misconception` is empty → no grounded incorrect assertion has been scored yet in this DB.

---

## 5. Frontend → API → DB mapping

| Frontend page | API call(s) | DB entities touched |
|---|---|---|
| Landing | — (static) | — |
| Register | `POST /register` | `student`, `auth_token` |
| Dashboard | `GET /history`, `GET /misconceptions`, `GET /next` | `answer`+`interview` (history), `misconception`, planner reads `misconception` |
| Practice | `POST /interviews` → `POST /score` | `interview` (create), `answer` (insert), `misconception` (bump) |
| My Progress | `GET /history` | `answer`+`interview` |
| Misconceptions | `GET /misconceptions` | `misconception` |
| Learning Planner | `GET /next` (+ `POST /interviews` to start) | `misconception` (read), `interview` (create) |
| Reports | `GET /history` | `answer`+`interview` |

Identity flow (verified): the **server** generates `student_id` + token at `/register`; the client stores
the token and sends `Authorization: Bearer`; student-specific routes authorize against the token owner
(403 on mismatch). The client cannot choose identity or the concepts an answer is graded against.

---

## 6. Working features (verified)

- Anonymous registration with server-generated identity; token shown once; only the hash stored.
- Token auth + per-student authorization boundaries (401/403).
- Interview question generation (7 deterministic topics) with server-stored expected concepts.
- **FairScore dual-axis scoring**: independent technical + communication bands, computed by deterministic
  Python from model-extracted claims/observations; grounded evidence; fail-closed abstention.
- Misconception detection only from grounded incorrect assertions matched to curated signatures.
- Deterministic learning planner from the misconception tally.
- SQLite persistence with idempotent schema migration.
- **Mock model mode** — full workflow with zero AWS; results labelled `LOCAL DEMO / MOCK EVALUATION`.
- Bedrock mode preserved; missing credentials → clean 503 (not an opaque 500).
- Full React UI: 8 pages, loading/empty/error/success states, responsive, charts, no fabricated stats.
- Test suite: **86 tests passing** (fairscore core, verifier, gates, db, migration, planner, fairness
  report, API with mocked model, mock mode, zero-AWS guarantee).

---

## 7. Incomplete / scaffolded features

| Item | State | Note |
|---|---|---|
| Strands conversation sessions | Constructors exist in `session.py`, **not wired into `run()`** | Scoring is single-shot; no multi-turn memory. Documented, not overstated. |
| Numeric scores | Not implemented by design | Backend returns four bands; UI renders bands, never a fabricated 0–100. |
| Per-concept analytics endpoint | Not present | Dashboard derives "latest band per topic" from history client-side. |
| Voice / Tamil | Out of scope (stretch in DESIGN.md) | No endpoints; UI does not expose. |
| Follow-up questions in an interview | `interview` supports one question per row | No multi-question interview session yet. |
| Topic catalogue endpoint | None | Frontend uses a static topic list mirroring `interview.py`. |

---

## 8. Bugs / risks observed (no fixes applied — audit only)

1. **Interpreter confusion (operational, recurring).** The backend must run under the Ubuntu
   `~/.strands-ship/venv` (Python 3.12). The Windows Store Python 3.13 has a broken OpenTelemetry install
   → `ImportError: _ExtendedAttributes`. A `.venv-win` now exists; whether it has a consistent OTel is
   unverified. **Recommendation:** standardize on one documented run path.
2. **Stale-process port conflicts.** A previously-started backend can hold port 8000 and silently serve
   old behavior (seen during testing: a Bedrock-mode process blocked a new mock-mode start). No
   single-command lifecycle exists.
3. **No `.env`/run script for the backend.** Env vars (`CAREERLIFT_MODEL_MODE`, DB, pepper) are passed by
   hand; easy to get wrong (the bash-vs-PowerShell paste errors are a symptom).
4. **`AUTH_PEPPER` fallback.** If `CAREERLIFT_AUTH_PEPPER` is unset, a per-process random pepper is used,
   so tokens silently stop validating across restarts. Fine for dev; a foot-gun if unnoticed.
5. **Token in `localStorage`.** Acceptable for a local prototype (documented); not production auth.
6. **`careerlift.db` committed/working-tree artifact.** It is gitignored, but the working DB carries test
   data; worth confirming it is not shipped.
7. **DB connection-per-call.** `db.py` opens a fresh SQLite connection per operation. Fine locally;
   would need pooling/WAL for concurrency.
8. **Starlette downgrade** (from an earlier phase, 1.x → 0.49.3 via FastAPI pin) remains; no observed
   breakage, flagged for awareness.

---

## 9. Proposed future architecture — incremental evolution (not a rewrite)

All items below **build on** the current structure. None require replacing working code.

### Tier 1 — hardening the existing system (low risk, high value)
- **One-command local run.** Add a backend run script / `.env.example` (env-driven) and a documented
  "mock vs bedrock" toggle, plus a port-in-use preflight. *Touches: new script + README only.*
- **Config surface.** Centralize env reads (`config.py` already exists) and add a `/config` or extend
  `/health` to report `model_mode` so the UI can show a mode badge. *Additive.*
- **Graceful model errors in the UI.** The 503 path exists; surface it as a friendly "scoring
  unavailable / switch to demo" banner. *Frontend additive.*

### Tier 2 — completing scaffolded capabilities
- **Multi-question interview sessions.** Evolve `interview` + `answer` into an interview that holds
  several questions; wire `session.py` (Strands sessions) so follow-ups can use prior context. *Extends
  existing tables and `run()`; does not replace FairScore.*
- **Concept-progress endpoint.** Add `GET /students/{id}/concepts` computing per-concept band history
  server-side, replacing the client-side derivation. *New endpoint, reuses `answer` rows.*
- **Topic catalogue endpoint.** `GET /topics` from `interview.QUESTION_BANK` so the frontend stops
  mirroring it statically. *Additive.*

### Tier 3 — product depth
- **Richer learning planner** (spaced repetition using `misconception.last_seen`/`count`). *Extends
  `planner.py`.*
- **Export / report download** from the existing `fairness_report.py` + history. *Additive.*
- **Optional real auth** (email magic-link or OAuth) layered over the current token model, keeping
  anonymous mode as a fallback. *New module; current auth stays.*

### Tier 4 — scale / deploy (only when desired, with explicit approval)
- Swap SQLite → managed DB behind the same `db.py` interface; add connection pooling/WAL.
- Containerize backend + frontend; pin a single Python toolchain to kill the interpreter issue.
- Bedrock deployment (AgentCore/managed) — **billable, out of scope until approved.**

### Evolution principles
1. Preserve `fairscore.py` as the immutable source of truth for bands; never let the model emit a score.
2. Extend tables with migrations (the `db._migrate` pattern already exists) — never drop/recreate.
3. Keep bedrock and mock modes both first-class; never silently switch.
4. Every new metric is real or an honest empty state — no fabricated statistics.
5. No internal implementation names (Strands/Bedrock/Nova/FastAPI) surface in the UI.

---

## 10. Summary

CareerLift AI is a genuinely working product, not a prototype shell: 8-page UI, 7-endpoint API,
token auth with real authorization boundaries, a well-tested deterministic FairScore engine, SQLite
persistence with migrations, and a no-AWS mock mode that runs the full workflow today. The main gaps are
operational (run ergonomics, interpreter standardization) and feature-completeness (multi-turn sessions,
server-side concept analytics) — all addressable as **incremental additions** on top of the existing
structure. The recommended next step is **Tier 1 hardening**, which removes the day-to-day run friction
without touching any working code.

*End of audit. No existing source was changed; only this document and a temporary DB-inspection script
(since removed) were created.*
