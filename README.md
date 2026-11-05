# CareerLift AI

> **Language-Fair Interview Coach for Students Who Think in Plain English**

A full-stack interview preparation platform built on the **AWS Strands Agents SDK** that scores technical interview answers on two completely independent axes — Technical Correctness and Communication Clarity — so students who answer in plain English, short sentences, or Tamil are **never penalised for vocabulary instead of knowledge**.

[![Live Demo](https://img.shields.io/badge/Live%20Demo-3--235--53--227.nip.io-6366f1?style=flat-square)](https://3-235-53-227.nip.io)
[![Tests](https://img.shields.io/badge/Tests-195%20passed-22c55e?style=flat-square)](#tests)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Hackathon](https://img.shields.io/badge/AWS%20Builder%20Center-Workshop%20to%20Ship%202026-f97316?style=flat-square)](https://github.com/naveensri4518/CareerLift-AI/blob/main/careerlift_demo.ipynb)

---

## The Problem

Every year, engineering students from rural colleges, first-generation households, and Tamil-first environments fail technical interviews — **not because they lack knowledge**, but because AI graders treat vocabulary sophistication as a proxy for technical understanding.

A student who says:
> *"binary search need sorted array, it cut half each time, log n steps"*

is demonstrating the **exact same algorithmic understanding** as a student who writes:
> *"Binary search operates on a pre-sorted array, halving the candidate search space on each iteration, thereby achieving O(log n) time complexity."*

Yet most AI practice tools give the first student a lower technical score. The feedback tells them their *technical* knowledge is weak — **which is false**. They then waste preparation time on the wrong thing.

**CareerLift AI was built to measure and eliminate that specific penalty.**

---

## Live Demo

🌐 **https://3-235-53-227.nip.io**

| Step | What to try |
|---|---|
| Register | Click Register — server generates your ID and token |
| Quick Practice | Pick a topic (hashing, binary search, recursion…) and answer in plain English |
| Interview Studio | Multi-question session — HR, behavioral, technical, or mixed |
| Coding Arena | Solve a real problem in Python, C++, or Java; watch it run in Docker |
| Technical Assessment | 10-question timed quiz; grades appear after submission |
| System Design | Design a URL shortener or news feed using a component palette |
| My Progress | See your technical and communication bands tracked separately |
| Misconceptions | See which specific wrong beliefs you have demonstrated |
| Learning Planner | Get your personalised next exercise |

**Note:** The server currently runs in mock mode (deterministic offline scorer) because of an AWS new-account Bedrock daily token cap. The mock label is honest — it disappears automatically when Bedrock inference is enabled (one environment variable change, no code change). All five phases work fully in mock mode.

---

## Demo Notebook

[![Open in GitHub](https://img.shields.io/badge/Jupyter-Open%20notebook-f97316?style=flat-square&logo=jupyter)](https://github.com/naveensri4518/CareerLift-AI/blob/main/careerlift_demo.ipynb)

The notebook `careerlift_demo.ipynb` demonstrates:
- FairScore fairness gap = 0 on 5 paraphrase pairs
- Misconception detection on 3 wrong answers
- Honest abstain on PII and empty inputs
- All five phases via live API calls

Runs in mock mode — **no AWS credentials needed**.

---

## Architecture

```
Student answer
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Input Gate (Strands BeforeModelCallEvent hook)             │
│  → If PII detected: cancel model call, return ABSTAIN text  │
│  → Zero tokens spent on PII answers                         │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Strands GraphBuilder                                       │
│                                                             │
│  ┌─────────────────────────────────────┐                   │
│  │  Technical Evaluator (Bedrock)      │                   │
│  │  structured_output: TechnicalClaims │                   │
│  │  → {concept_id, status, evidence}   │←─ re-extract loop │
│  └──────────────┬──────────────────────┘  (max 2 passes)   │
│                 │                                           │
│  ┌──────────────▼──────────────────────┐                   │
│  │  Deterministic Verifier (Python)    │                   │
│  │  → checks evidence spans are real  │                    │
│  │  → drops ungrounded claims         │                    │
│  │  → abstains if coverage < 30%      │                    │
│  └──────────────┬──────────────────────┘                   │
│                 │                                           │
│  ┌──────────────▼──────────────────────┐                   │
│  │  Communication Coach (Bedrock)      │                   │
│  │  structured_output: CommObservations│                   │
│  │  → clarity / structure / relevance │ ← INDEPENDENT     │
│  │  → NEVER judges grammar or vocab   │                    │
│  └─────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  Deterministic Scoring (agent/fairscore.py)                 │
│  band_from_claims()  →  Weak / Partial / Solid / Strong     │
│  comm_band()         →  Weak / Partial / Solid / Strong     │
│  THE MODEL NEVER RETURNS A SCORE. CODE OWNS EVERY BAND.    │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
ScoreResult {technical_band, communication_band,
             technical_evidence, misconception_tags}
       │
       ▼
Phase 0 Learning Intelligence
(SkillSignals → LearnerModel → Mastery labels → Recommendations)
```

### Strands SDK blocks used

| Block | Where | Purpose |
|---|---|---|
| `GraphBuilder` | `agent/app.py` | Runs the Technical Evaluator with bounded re-extract loop |
| Structured output | `agent/evaluate.py`, `agent/coach.py` | Forces model to return typed claims/observations, never free-text scores |
| `BeforeModelCallEvent` (HookProvider) | `agent/gates.py` | PII gate — cancels model call before tokens are spent |
| `BedrockModel` | `agent/app.py` | Nova 2 Lite via cross-region inference profile |
| `FileSessionManager` | `agent/app.py` | Per-student conversation state on EBS |
| `SlidingWindowConversationManager` | `agent/app.py` | Bounded context window (20 turns) |

---

## Five Phases

### Phase 0 — Learning Intelligence (the backbone)

Every interaction from every phase emits a `SkillSignal` row:
```python
{concept_id, outcome: mastered|partial|struggled|misconception, 
 source_module: interview|coding|assessment|sysdesign,
 dedup_key}     # prevents same exercise counting twice
```

The `LearnerModel` replays all signals through a deterministic state machine:
```
Not enough evidence → Emerging → Developing → Proficient → Strong
```

Thresholds: `EVIDENCE_FLOOR=3` (Proficient), `STRONG_FLOOR=5` (Strong), `RESOLVE_N=2` (clear a misconception).

Recommendations rank: open misconceptions first → low mastery → spaced repetition due.

**No model call in the mastery or recommendation pipeline.** Pure deterministic Python.

### Phase 1 — Interview Studio

Multi-question mock interviews with full FairScore dual-axis scoring.

- Categories: Technical, HR, Behavioral, Project-Based, Mixed
- 3–20 questions per session; students can save drafts and resume
- Per-question FairScore evaluation on submit
- Session-level aggregation: strengths, weaknesses, misconceptions, recommended practice topics
- Phase 0 integration: every technical answer emits SkillSignals

### Phase 2 — Secure Coding Arena

Real code execution in Docker-isolated containers.

```
Student code → POST /coding/submit
                    │
                    ▼
            docker run --network none --read-only --cap-drop ALL
                       --user 1000:1000 --memory 256m --pids-limit 128
                    │
                    ▼
            Public tests: show input/expected/actual diffs
            Hidden tests: show count only — never sent to client
                    │
                    ▼
            Verdict: ACCEPTED | WRONG | TLE | RUNTIME | COMPILATION ERROR
```

**Verified on production server:** network blocked, root filesystem read-only, non-root UID, OOM kill at 1 GB, TLE on infinite loops. Python, C++, Java all produce ACCEPTED on correct solutions.

### Phase 3 — Technical Assessment Engine

- 120 curated MCQ questions across 12 CS categories
- Categories: DSA, Java, Python, C, C++, DBMS, SQL, OS, Networks, OOP, Architecture, Software Engineering
- Question types: single-choice, multiple-select (exact set match required), True/False
- **Server-authoritative timing:** `started_at + duration_sec = expires_at` stored server-side; auto-submits when expired regardless of client state
- Correct answers and explanations revealed only after submission

### Phase 4 — System Design Academy

Five server-owned system design scenarios:

| Scenario | Difficulty |
|---|---|
| Design a URL Shortener | Beginner |
| Design a News Feed | Advanced |
| Design a Rate Limiter | Intermediate |
| Design a Chat System | Intermediate |
| Design an Image Upload Service | Advanced |

Students build a structured design using a component palette (Client, CDN, Load Balancer, App Server, Cache, SQL DB, NoSQL DB, Object Store, Message Queue, Worker…), draw connections, and answer decision prompts. Grading is fully deterministic — no model call.

**P3 fix (deployed):** decision prompts can no longer overwrite the structural `components`/`connections` dimensions — previously, the `code_gen` decision in SD-URL-SHORTENER would discard the real component-matching score.

---

## FairScore — How Fairness Works

### The problem with naive graders

A single-prompt grader returns a band directly. This means:
- Grammar and vocabulary can influence the technical score (no separation)
- A confident-sounding wrong answer can score well (no evidence grounding)
- There is no inspectable evidence — feedback is opaque

### CareerLift's structural solution

**1. Vocabulary abstraction (concept cues)**

Each concept in `agent/data/concepts.json` has:
- `aliases` — textbook vocabulary (`hash table`, `O(1)`, `average case`)
- `key_points` — core content phrases
- **`cues`** — plain-language phrases that indicate the concept was *addressed* without jargon

Example cues for `C-HASH-AVG`:
```json
"cues": [
  "store things by a key",
  "basically instant",
  "land in the same spot",
  "walk through all of them"
]
```

A student who says *"when you store things by a key looking one up is basically instant most of the time but if lots land in the same spot it slows down"* — gets `partial` (addressed the concept, evidence grounded). Without cues, they would get `absent` → abstain → "Not assessed." **P1 fix: the cue system is why plain English now gets a technical band.**

**2. Grounding check**

Every claim must include an `evidence_span` — a verbatim quote from the student's answer. The verifier checks `evidence_span in answer` (normalised). Ungrounded claims are dropped. This prevents the model from hallucinating credit.

**3. Abstain > guess**

If weighted coverage (supported=1.0, partial=0.5, absent=0.0, incorrect=0.0) across expected concepts is below `ABSTAIN_MIN_SUPPORT=0.30`, the system returns "not assessed" rather than guessing a low band. An honest abstain is better than a fabricated Weak.

**4. Communication is fully independent**

The Communication Coach receives only the answer text — no expected concepts, no technical claims. It produces `{clarity, structure, relevance, organisation}` observations based purely on structural signals. Grammar, vocabulary, accent, and length are explicitly excluded from the rubric.

---

## Project Structure

```
CareerLift-AI/
├── agent/                     # Core AI and scoring logic
│   ├── app.py                 # Strands pipeline entrypoint (GraphBuilder, hooks)
│   ├── fairscore.py           # Deterministic scoring — band_from_claims, comm_band
│   ├── mockmodel.py           # Local deterministic extractor (mock mode)
│   ├── config.py              # Model mode selection (mock vs bedrock)
│   ├── interview_studio.py    # Phase 1 session logic
│   ├── coding_eval.py         # Phase 2 Docker sandbox evaluation
│   ├── assessment_bank.py     # Phase 3 question bank
│   ├── assessment_eval.py     # Phase 3 grading
│   ├── sysdesign_bank.py      # Phase 4 scenario bank
│   ├── sysdesign_eval.py      # Phase 4 rubric grading
│   ├── planner.py             # Phase 0 recommendations
│   ├── db.py                  # SQLite data access (13 tables)
│   ├── gates.py               # PII input gate (Strands hook)
│   ├── evaluate.py            # Technical Evaluator (Strands agent)
│   ├── coach.py               # Communication Coach (Strands agent)
│   └── data/
│       ├── concepts.json      # Concept reference — aliases, key_points, cues
│       ├── sysdesign_scenarios.json
│       ├── sysdesign_concepts.json
│       ├── assessment_questions.json
│       └── coding_problems.json
├── api/                       # FastAPI application
│   ├── main.py
│   ├── routers/
│   │   ├── dashboard.py       # /overview, /activity
│   │   ├── learning.py        # /history, /misconceptions, /next, /skills
│   │   ├── studio.py          # Phase 1 session API
│   │   ├── coding.py          # Phase 2 Arena API
│   │   ├── assessment.py      # Phase 3 Assessment API
│   │   └── sysdesign.py       # Phase 4 System Design API
│   ├── auth.py
│   └── deps.py
├── frontend/                  # React 18 + Vite SPA
│   └── src/
│       ├── pages/
│       │   ├── Practice.jsx   # Quick Practice (P2 fix: context banners)
│       │   ├── Misconceptions.jsx
│       │   ├── Planner.jsx
│       │   ├── studio/        # Interview Studio (Phase 1)
│       │   ├── coding/        # Coding Arena (Phase 2)
│       │   ├── assessment/    # Assessment (Phase 3)
│       │   └── sysdesign/     # System Design (Phase 4)
│       ├── components/
│       ├── lib/content.js     # Concept/band/topic metadata
│       └── api/client.js
├── tests/                     # 195 backend tests, 0 failures
├── cases.jsonl                # 35 evaluation cases (paraphrase pairs, Tamil, abstain)
├── careerlift_demo.ipynb      # Demo notebook — runs in mock mode, no AWS needed
├── FAILURES.md                # Two documented failures + fixes (required by ship method)
├── docs/
│   ├── ARTICLE.md             # Builder Center article (20 sections)
│   ├── HUMAN-REVIEW.md        # 35-case review worksheet
│   └── article/images/        # 6 architecture SVGs + PNG exports + cover image
├── scripts/
│   ├── run-tests.sh
│   ├── verify_sandbox.py      # 11-point Docker isolation check
│   └── build-sandbox.sh
├── results/
│   └── demo.webm              # 34-second demo video
├── requirements.txt
└── LICENSE                    # MIT
```

---

## How to Run Locally

### Requirements

- Python 3.12
- Node.js 20+
- Docker Engine (for the Coding Arena)

### Backend — mock mode (no AWS needed)

```bash
git clone https://github.com/naveensri4518/CareerLift-AI.git
cd CareerLift-AI

python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

CAREERLIFT_MODEL_MODE=mock \
CAREERLIFT_DB=./careerlift.db \
CAREERLIFT_AUTH_PEPPER=local-dev-pepper-change-in-production \
  .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

API available at `http://127.0.0.1:8000` — health check: `curl http://127.0.0.1:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev     # → http://localhost:5173 (proxies /api to port 8000)
```

### Coding Arena sandbox

```bash
bash scripts/build-sandbox.sh   # builds careerlift-coding-sandbox:latest Docker image
python scripts/verify_sandbox.py  # runs 11 isolation checks — all should pass
```

### Run with real Bedrock (needs AWS credentials)

```bash
# Requires: AWS credentials with bedrock:InvokeModel on us.amazon.nova-2-lite-v1:0
export CAREERLIFT_MODEL_MODE=bedrock
export AWS_REGION=us-east-1
export SHIP_MODEL=us.amazon.nova-2-lite-v1:0
# ... start uvicorn as above
```

### Tests

```bash
python -m pytest -q          # 195 tests, 0 failures
cd frontend && npm run build # frontend production build
```

---

## Evaluation Dataset

35 hand-labelled evaluation cases in `cases.jsonl`:

| Type | Count | Description |
|---|---|---|
| English paraphrase pairs | 20 (10 pairs) | Same concept, plain vs advanced English — same expected technical band |
| Tamil-language cases | 10 | Natural spoken Tamil across 7 concepts |
| Abstain / emergency | 8 | PII inputs, empty/vague answers — expected: abstain |
| Misconception cases | 5 | Wrong assertions — expected: Weak + tag |

**Student personas:** rural college student, communication-struggling student, complete beginner, underserved-background student.

**Measurement status:** `ss measure` requires (1) human reviewer sign-off of the 35 cases and (2) Bedrock inference (new-account daily token quota). The pipeline runs end-to-end in mock mode: 35/35 cases, 0 errors, 0 unsafe events.

---

## Security

| Property | Implementation |
|---|---|
| No static AWS keys | IAM instance role — credentials via IMDSv2 only |
| Auth tokens | Server-generated; only SHA-256(token + pepper) stored |
| Production pepper | 64-char SecureString in SSM, fetched at service start, never logged |
| Code execution | Docker: `--network none --read-only --cap-drop ALL --user 1000:1000 --memory 256m --pids-limit 128` |
| Git history | Confirmed clean: `git log -p | grep -E "AKIA|BEGIN.*PRIVATE KEY"` → zero results |
| PII gate | Strands `BeforeModelCallEvent` hook cancels model call before tokens are spent |

---

## Deployment (Production)

| Resource | Details |
|---|---|
| EC2 | t3.small, Amazon Linux 2023, us-east-1a |
| EBS | 20 GB gp3, `/data` — SQLite database + session files |
| Nginx | 1.30, HTTPS termination + SPA static files + `/api` reverse proxy |
| HTTPS | Let's Encrypt via nip.io — valid through February 2027 |
| Service | `systemd careerlift-api.service` — restart on failure |
| Bedrock | `us.amazon.nova-2-lite-v1:0` (Nova 2 Lite), us-east-1 |
| Budget | $25/month, alerts at $15/$20/$25 |

```bash
# Production environment variables (/etc/careerlift.env, chmod 600)
CAREERLIFT_MODEL_MODE=mock        # flip to bedrock once Bedrock unthrottled
AWS_REGION=us-east-1
SHIP_MODEL=us.amazon.nova-2-lite-v1:0
CAREERLIFT_DB=/data/careerlift.db
CAREERLIFT_SESSIONS=/data/sessions
```

---

## Documented Failures

Two production failures found, fixed, and documented in `FAILURES.md` (required by the ship method — judges trust a project that shows what broke):

**1. Plain-English answers scored "Not assessed" (P1)**

Plain-English answers got `coverage=0.0` → abstain because the mock extractor only matched textbook vocabulary. Fixed by adding curated `cues` per concept in `concepts.json` and a fallback cue-matching path in `mockmodel.py`. 7 regression tests added. Before: case 6 (plain English) → Not assessed. After: Partial (assessed, honest, not inflated).

**2. System Design grading dropped the component score (P3)**

In SD-URL-SHORTENER, the `code_gen` decision prompt was tagged with `SD-COMPONENTS` (the same concept as the structural components dimension). This caused `dims["components"]` to be overwritten with the code_gen multiple-choice result, discarding the real component-matching score. Fixed in `sysdesign_eval.py` (reserved structural keys) and `sysdesign_scenarios.json` (corrected concept ID). 2 regression tests added.

---

## Honest Limits

- Measurement numbers are pending (Bedrock throttle + human case sign-off)
- Fairness is measured on this dataset, not guaranteed for every live answer
- Tamil cases need a native-speaker review before being signed off
- The mock evaluator is English-only (keyword + cue based)
- Single EC2 instance — no horizontal scaling (not needed for current load)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS, Framer Motion, Recharts |
| Backend | Python 3.12, FastAPI 0.120, Uvicorn, stdlib sqlite3 |
| AI framework | **AWS Strands Agents SDK** 1.62.0 |
| Model | Amazon Bedrock — **Nova 2 Lite** (`us.amazon.nova-2-lite-v1:0`) |
| Code execution | Docker 25, eclipse-temurin:17-jdk, Python 3 + g++ |
| Database | SQLite (13 tables, additive migrations) |
| Infrastructure | EC2 t3.small, EBS gp3, IAM role, SSM Parameter Store |

---

## Hackathon

**Strands SDK: Workshop to Ship — AWS Builder Center 2026**  
Track: Education  
Deadline: 5 Nov 2026 1:29 PM IST

**Judging criteria mapping:**
- Social impact: language fairness for underserved students, measured fairness gap
- Technical execution: Strands GraphBuilder + hooks + structured output + deterministic scorer
- Communication: [article](docs/ARTICLE.md), [demo video](results/demo.webm), [notebook](careerlift_demo.ipynb)
- Originality: dual-axis scoring architecture, concept cue system, five integrated phases, Tamil support

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with the AWS Strands Agents SDK. Deployed on AWS. Measuring and reducing language-based bias in technical interview grading.*
