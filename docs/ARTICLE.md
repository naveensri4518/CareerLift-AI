# CareerLift AI: Building a Language-Fair Interview Coach for Students Who Think in Plain English

*A Strands Agents SDK project by Naveensri — Strands SDK: Workshop to Ship Hackathon 2026*

---

## Introduction

Every year, thousands of engineering students walk out of a technical interview knowing they understood the problem — but still fail. Not because they lacked the knowledge, but because the grader (human or AI) conflated the way they said it with what they actually knew.

A student from a rural college in Tamil Nadu who says *"binary search need sorted array, it cut half each time"* is demonstrating the same algorithmic understanding as a student from a well-funded institution who writes *"binary search operates on a pre-sorted array, halving the candidate search space on each iteration."* Yet most AI practice tools give the first student a lower score. The tool meant to help them prepare is reinforcing the exact disadvantage they came to overcome.

CareerLift AI was built to change that.

![System Architecture](images/01-system-architecture.svg)

---

## Social impact — who it helps and how we measured it

### The problem

Students preparing for software engineering interviews — especially those from rural colleges, first-generation households, or Tamil-first environments — face a hidden penalty from AI graders. Most graders treat vocabulary sophistication, sentence complexity, and grammar polish as proxies for technical understanding. These are proxies for privilege, not for engineering ability.

The consequence is real: a student who can explain a hash table correctly, but does it in short, plain sentences, receives lower scores than a student who says the identical thing in ornate prose. The feedback they receive tells them their *technical* understanding is weak — which is false. They then invest their preparation time on the wrong thing.

This is the specific, named harm that CareerLift AI addresses.

### The mechanism of benefit

CareerLift AI scores student answers on **two completely independent axes**:

- **Technical score** — based entirely on the concepts the student correctly addressed, regardless of phrasing
- **Communication score** — based on clarity, structure, relevance, and organisation — explicitly *not* vocabulary, grammar, or length

Code owns every band (Weak / Partial / Solid / Strong). The AI model is only allowed to extract evidence from the student's words — it is never allowed to return a score. This is not a prompt-engineering trick; it is a structural decision enforced at the architecture level. Simple English, grammar mistakes, and short sentences cannot reach the technical score pipeline.

![Fairness Concept](images/06-fairness-concept.svg)

### How we measured it

We built a dataset of **paraphrase pairs**: the same technical content written in plain English and in advanced English, both labelled by hand with the same expected technical band (because the technical content is identical).

We then measured the **fairness gap** — the difference in technical bands between the plain-English and advanced-English members of each pair — for CareerLift and for a one-prompt baseline grader. A smaller gap means the tool is treating plain English more fairly on that dataset.

**Evaluation dataset:**
- 35 cases across 7 CS concepts (hash tables, binary search, recursion, complexity, SQL joins, database indexes, Python pitfalls)
- 10 paraphrase pairs (plain and advanced English, same expected technical band)
- 10 Tamil-language cases
- 8 abstain cases (deliberately unclear or PII-containing answers the scorer should refuse to score)
- 4 student personas: rural college student, communication-struggling student, complete beginner, underserved-background student

**Evaluation status:** Live measurement via `ss measure` requires (1) human reviewer sign-off of the 35 cases and (2) successful Amazon Bedrock inference. The pipeline runs end-to-end in mock mode: 35/35 cases scored, 0 errors, 0 unsafe events. Live Bedrock results will be added to this table once the daily token quota on the new AWS account clears (new-account Bedrock throttle, not a code issue).

| Metric | CareerLift (agent) | Baseline (one-prompt) |
|---|---|---|
| Fairness gap (mean) | *pending Bedrock measurement* | *pending Bedrock measurement* |
| Technical accuracy vs labels | *pending* | *pending* |
| Unsafe answers (0 required) | 0 (mock mode verified) | *pending* |
| Abstain rate | correct on 8/8 in mock mode | *pending* |

**Honest limits:** fairness is a property of this scorer on this dataset, not a universal guarantee. The AI model still extracts claims from the student's text; if the extractor itself is register-sensitive (more likely to miss correct claims in plain English), bias can re-enter before the deterministic pipeline runs. We measure this per concept and report it. We do not claim to eliminate bias — we claim to measure and reduce a specific, named gap.

Tamil cases require a native-speaker review; the mock evaluator is English-only by design (keyword-based). The Tamil abstention behaviour in mock mode is documented in FAILURES.md as an expected, not a safety failure.

---

## Project overview

CareerLift AI is a full-stack interview preparation platform built on the AWS Strands Agents SDK. It runs realistic technical interviews, scores answers on two independent axes, tracks student mastery across sessions, and provides five integrated learning modules:

| Phase | Module | What it does |
|---|---|---|
| 0 | Learning Intelligence | Tracks concept mastery across all phases via SkillSignals → LearnerModel → Recommendations |
| 1 | Interview Studio | Multi-question mock interviews with FairScore dual-axis scoring |
| 2 | Secure Coding Arena | Code execution in Docker-isolated containers; Python / C++ / Java |
| 3 | Technical Assessment | 120-question timed MCQ assessment across 12 CS categories |
| 4 | System Design Academy | Rubric-graded structured system design challenges |

All five phases share a single learning intelligence backbone: every interaction emits SkillSignals that update the same LearnerModel, so a student's mastery state is always current regardless of which module they use.

**Verified facts:**
- 186 backend tests, 0 failures (all five phases)
- 13/13 public end-to-end tests pass against the live deployed API
- 11/11 Docker sandbox isolation checks pass on the production server
- Frontend builds clean in production
- Live deployment at https://3-235-53-227.nip.io with trusted HTTPS (Let's Encrypt)

---

## Real-world use cases

**Use case 1 — The plain-English student:** Anitha knows that quicksort is O(n log n) on average and O(n²) worst case. She explains it in Tamil-influenced English: "quicksort usually n log n, but if pivot always small element, worst case n squared." A naive grader marks her down for grammar. CareerLift separates the technical claim (correct) from the communication (improvable but separate). She learns what to actually work on.

**Use case 2 — The algorithm learner:** Ravi practises binary search questions in the Coding Arena, writes a correct Python solution, and gets ACCEPTED with real test-case output. His correct submission feeds the Learning Intelligence model, and his binary search mastery label advances from Emerging to Developing. The planner recommends his next concept.

**Use case 3 — The preparation tracker:** A student takes a 20-question Technical Assessment on Data Structures, gets their score and per-category breakdown (Sorting: 80%, Graphs: 40%), sees the correct answers after submission (never before), and gets a System Design challenge to work on next.

---

## System architecture

The architecture has three layers:

1. **Presentation:** React 18 + Vite SPA served by Nginx, proxied to the API via same-origin `/api` routing
2. **Application:** FastAPI with six routers (one per phase), SQLite on persistent EBS, Strands agent for scoring
3. **Intelligence:** Strands GraphBuilder → BedrockModel (Nova 2 Lite) → deterministic Python scorer

![System Architecture Full](images/01-system-architecture.svg)

### Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS, Framer Motion, Recharts |
| Backend | Python 3.12, FastAPI 0.120, Uvicorn, stdlib sqlite3 |
| AI framework | Strands Agents SDK 1.62.0 |
| Model | Amazon Bedrock, us.amazon.nova-2-lite-v1:0 (Nova 2 Lite) |
| Execution | Docker 25, eclipse-temurin:17-jdk base, Python 3 + g++ |
| Database | SQLite (13 tables, additive schema, no ORM) |
| Infrastructure | EC2 t3.small, EBS gp3 (16 GB root + 20 GB data), IAM instance role, SSM |
| HTTPS | Let's Encrypt via nip.io (trusted cert, auto-renew) |
| Monitoring | CloudWatch budget ($25 gross, $15/$20/$25 alerts) |

### Security design

- **No static AWS access keys anywhere.** The EC2 instance uses an IAM instance role (`CareerLiftEC2RuntimeRole`) with least-privilege Bedrock invoke permissions. The role is the only credential.
- **Authentication:** server-generated bearer tokens. Only SHA-256(token + SSM pepper) is stored; the plaintext token is shown once and never persisted.
- **Production pepper:** `/careerlift/auth_pepper` — 64-char SecureString in SSM Parameter Store, fetched at service start, never logged or committed.
- **Docker sandbox:** `--network none`, `--read-only`, `--cap-drop ALL`, `--user 1000:1000`, `--memory 256m`, `--pids-limit 128`. Student code never runs in the API process. Every container is destroyed after each test run.
- **Git:** three clean checkpoints confirmed by `git log -p | grep -E "AKIA|BEGIN.*PRIVATE KEY"` — zero results.

---

## Technical implementation — Strands SDK and agent architecture

![FairScore Pipeline](images/02-fairscore-pipeline.svg)

### The FairScore agent

The scoring pipeline uses three Strands building blocks:

**1. GraphBuilder (spine)**

```
intake → evaluate (bounded re-extract loop) → verifier
```

The `GraphBuilder` runs the technical evaluator with a conditional self-loop (`set_max_node_executions(2)`) that re-extracts claims once if the first structured output is malformed or empty. The verifier is deterministic Python with zero model calls — it checks every extracted claim against a curated concept reference, drops unsupported claims, and triggers an abstain if coverage falls below a threshold. The graph is fail-closed: uncertain output → abstain, never guess.

**2. Structured output + deterministic scorer**

Both the Technical Evaluator and Communication Coach use Pydantic `structured_output_model`:
- `TechnicalClaims{ claims: list[Claim{concept_id, status, evidence_span}] }`
- `CommObservations{ clarity, structure, relevance, organisation: present|partial|absent }`

The deterministic `band_from_claims()` and `comm_band()` in `agent/fairscore.py` map these to a band. **The model never returns a score, a band, or a number.** It only returns structured evidence.

**3. BeforeModelCallEvent hook (PII gate)**

A `HookProvider` fires before every model call. If the student's text contains phone numbers, email addresses, or ID numbers, the hook cancels the model call (`event.cancel()`) and the API returns a fixed ABSTAIN text. Zero tokens are spent. This is verified in the evaluation dataset (8 abstain cases include 2 PII cases — both correctly caught in mock mode).

**4. FileSessionManager**

Per-student conversation state persists to `CAREERLIFT_SESSIONS` via `FileSessionManager`. `SlidingWindowConversationManager(window_size=20)` keeps the context bounded.

### Why not a single prompt?

A single-prompt grader returns a band directly, which means:
- Vocabulary and grammar can influence the technical score (no separation)
- There's no explicit coverage check — a confident-sounding wrong answer can score well
- There's no structured, inspectable evidence output — the feedback is opaque

CareerLift's architecture makes each of these an explicit engineering decision rather than an implicit model behaviour.

---

## Detailed explanation of all five phases

![Five Phases](images/05-five-phases.svg)

### Phase 0 — Learning Intelligence

The backbone of the whole platform. Every interaction from every phase emits a `skill_signal` row with `source_module` (interview/coding/assessment/sysdesign), an `outcome` (mastered/partial/struggled/misconception), and an `independent_key` (unique per concept per interaction, so the same exercise can't count twice). The `learner_model.update()` function replays all of a concept's signals through a deterministic state machine to produce a mastery label:

```
Not enough evidence → Emerging → Developing → Proficient → Strong
```

The state machine uses three calibrated constants: `EVIDENCE_FLOOR=3` (independent successes → Proficient), `STRONG_FLOOR=5` (→ Strong), and `RESOLVE_N=2` (consecutive successes to resolve an open misconception). Recommendations rank open misconceptions first (Tier 1), then low-mastery concepts (Tier 2), then spaced-repetition due ones (Tier 3).

This is entirely deterministic — no model in the mastery or recommendation pipeline.

### Phase 1 — Interview Studio

A multi-question mock interview with full FairScore scoring. Students configure category (Technical/HR/Behavioral/Project-Based/Mixed), difficulty, experience level, number of questions (3–20), and duration. The server generates the question set and freezes it. Students can save drafts and resume. On submit, every answer is scored via the Strands FairScore agent and the results are aggregated. Phase 0 signals are emitted for each technical answer.

The provider abstraction (`interview_studio.py`) routes to either the real Bedrock FairScore path or the deterministic mock evaluator depending on `CAREERLIFT_MODEL_MODE`.

### Phase 2 — Secure Coding Arena

![Coding Arena](images/03-coding-arena.svg)

The most security-critical component. Student code is submitted to `POST /coding/submit`, which calls `agent/coding_eval.py`, which shells out to `docker run` with all isolation flags. Every test case runs in a fresh container that is destroyed after. Hidden test cases are never sent to the client (the response includes counts and public-test diffs only).

**Verified isolation (live on the production server):**
- Network disabled: `NET_BLOCKED` ✓
- Read-only root filesystem: `ROOT_READONLY` ✓
- Non-root execution: `uid=1000` ✓
- Memory limit enforced: OOM-kill on 1 GB allocation, exit 137 ✓
- TLE on infinite loop ✓
- Python, C++, and Java all produce ACCEPTED on correct solutions ✓

### Phase 3 — Technical Assessment Engine

120 curated MCQ questions across 12 CS categories (DSA, Java, Python, C, C++, DBMS, SQL, Operating Systems, Computer Networks, OOP, Computer Architecture, Software Engineering), each with three difficulty levels. Three question types: single-choice, multiple-select (exact set required for marks), and True/False.

The assessment uses server-authoritative timing: `started_at + duration_sec = expires_at` is stored on the server. The client displays a countdown, but the server auto-submits when `expires_at` passes regardless of client state. No client timestamps are trusted. Correct answers and explanations are only revealed in the result page after submission.

### Phase 4 — System Design Academy

Five server-owned system design scenarios (URL Shortener, News Feed, Rate Limiter, Chat System, Image Upload Service), each with a complete rubric: required components, required connections, acceptable database choices, expected decision selections, and canonical trade-off analysis. Grading is deterministic against the rubric — no model call. Students build a structured design (component palette + connection builder + decision prompts) and submit.

---

## AWS integration and deployment

![AWS Deployment](images/04-aws-deployment.svg)

### Infrastructure

A single EC2 t3.small (Amazon Linux 2023, us-east-1a) runs the entire stack:
- Nginx 1.30 (HTTPS termination + static SPA + `/api` reverse proxy)
- FastAPI/Uvicorn (loopback only, systemd service with restart-on-failure)
- Docker engine (coding sandbox)
- SQLite on a persistent 20 GB gp3 EBS volume at `/data`
- Strands `FileSessionManager` sessions also on `/data`

Credentials never exist on disk. The IAM instance role (`CareerLiftEC2RuntimeRole`) provides boto3 with temporary credentials via the instance metadata service (IMDSv2 required). The production auth pepper is fetched from SSM Parameter Store at service start and never logged.

### Why EC2 over serverless?

The Secure Coding Arena requires a Docker daemon on the compute host. This is fundamentally incompatible with Lambda (no docker socket) and awkward on most managed container runtimes (needs privileged docker-in-docker). EC2 is the simplest choice that satisfies all constraints, including SQLite's single-writer model.

### Why SQLite over RDS?

Single writer, low concurrency, small row sizes, no connection pool required. SQLite on EBS is simpler, cheaper (no RDS charges), and fully durable. Migration to RDS is the right choice only if multi-instance horizontal scaling becomes a real requirement — it isn't yet. The additive schema migration design (CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN) means SQLite can be replaced with PostgreSQL later with minimal changes to the data access layer.

### Cost (actual, not estimated)

- Month-to-date spend as of deployment: **$0** (instance was provisioned recently)
- Target: ~$19–21/month running 24×7 (EC2 t3.small ~$15 + EBS gp3 ~$3 + misc ~$2)
- Budget: `CareerLift-Monthly-25` ($25/month gross, email alerts at $15/$20/$25 to naveensri2202@gmail.com)
- AWS promotional credits are active and apply to all services used

---

## Testing and evaluation

### Backend tests
186 tests across 16 test files, covering all five phases. Run with `python -m pytest -q`. Zero failures.

| Test file | Tests | Coverage |
|---|---|---|
| test_api.py | 18 | Registration, auth, /score, /next, history |
| test_mockmode.py | 14 | Mock evaluator, full pipeline |
| test_fairscore.py | 10 | Deterministic scoring, bands, abstain |
| test_phase0_integration.py | 6 | SkillSignals → mastery end-to-end |
| test_studio.py | 13 | Phase 1 session lifecycle |
| test_coding.py | 19 | Phase 2 verdicts, sandbox, auth |
| test_assessment.py | 20 | Phase 3 lifecycle, timer, grading |
| test_sysdesign.py | 20 | Phase 4 lifecycle, rubric grading |
| (others) | 66 | DB, learner model, signals, corrections, migration |

### End-to-end tests (live production)
13/13 public API tests pass against `https://3-235-53-227.nip.io/api`, covering all five phases and authentication isolation.

### Docker sandbox isolation
11/11 isolation checks pass on the production server (the `scripts/verify_sandbox.py` harness).

### Evaluation pipeline
35-case dataset: schema valid, 0 errors in mock-mode dry run, 0 unsafe events after the Tamil mock-mode false-positive fix. Human sign-off pending before `ss measure` can run in Bedrock mode.

---

## Technical challenges and solutions

### Challenge 1: Making fairness measurable, not just claimed

**Problem:** Saying "our tool is fair" is meaningless without evidence. We needed a way to measure the specific bias we claimed to address.

**Solution:** Paraphrase pairs. By constructing pairs where the technical content is identical and only the English register varies, and labelling both with the same expected technical band, the fairness gap becomes a single, honest number. The paired construction also means we can identify *which concepts* have extraction-level sensitivity, not just overall fairness.

### Challenge 2: The verifier — what deterministic Python can and cannot prove

**Problem:** Every Strands claim-extraction call could return confidently-phrased but technically wrong claims.

**Solution:** The Verifier checks three things it *can* prove with plain Python: (1) that every claimed concept ID exists in the curated reference, (2) that every evidence span is an actual substring of the student's answer (grounding — proves the model quoted, not invented), and (3) that the claim set is internally consistent. What it *cannot* prove is that a grounded claim is technically correct — that requires the human-labelled dataset. This honest limitation is stated in the code comments and in this article.

### Challenge 3: Tamil cases in the mock evaluator

**Problem:** The deterministic mock evaluator is keyword-based and English-only. Tamil-language cases correctly abstained in mock mode, but the score.py unsafe rule 3 flagged abstentions on cases with non-null expected technical bands as gate-blocking failures.

**Solution:** Added a `_ta_mock_abstain` guard: in mock mode, Tamil abstentions do not trigger unsafe rule 3. The guard is mode-specific (Bedrock is unaffected) and documented. Found by running the mock pipeline before `ss measure` — exactly the catch-early discipline the recipes recommend.

### Challenge 4: Docker sandbox — compile + run must be one container

**Problem:** The first architecture compiled and ran in separate containers. The compiled binary (`./main`, `Main.class`) was in the first container's ephemeral tmpfs workspace and gone by the time the second container started.

**Solution:** Rewrote `coding_exec.py` to emit a single `/bin/sh -c "compile && run"` command per test case. Compile artifacts persist in the container's writable tmpfs for the duration of that single container's run.

### Challenge 5: EC2 in the wrong Availability Zone

**Problem:** `t3.small is not supported in your requested Availability Zone (us-east-1e)`. The default subnet resolved to `us-east-1e`.

**Solution:** Queried the default subnet in `us-east-1a` and relaunched. One CLI call, no architectural change.

---

## Limitations and honest observations

1. **Measurement is pending.** The fairness gap table above has no live Bedrock numbers. The new AWS account has a daily Bedrock token quota that depletes on the first run. We are not fabricating any number — we are waiting for the quota to reset.

2. **The evaluation dataset is small.** 35 cases across 7 concepts is enough to demonstrate the method, not enough to make strong statistical claims. A larger dataset, more diverse topics, and more reviewers would strengthen the evidence.

3. **Tamil cases need a native speaker.** The Tamil cases were authored by the developer and reviewed against the concept taxonomy, but have not been reviewed by a Tamil-first speaker. The limitation is stated explicitly.

4. **Mock mode vs Bedrock mode.** All demo output (including the recorded video) carries `[LOCAL DEMO / MOCK EVALUATION]` because the Bedrock daily quota was throttled during the recording. The mock evaluator is deterministic and correct, but it is not the Bedrock model. The video will be re-recorded in Bedrock mode once the quota resets.

5. **Single EC2 instance = single point of failure.** The current deployment has no HA, no multi-instance setup, no ALB. This is appropriate for a hackathon demo — not for production at scale.

6. **SQLite single-writer.** Multiple uvicorn workers writing the same SQLite file will hit `database is locked`. The current deployment uses a single worker. WAL mode + connection pool would be needed before adding workers.

---

## What I learned

The biggest lesson was that **fairness is a measurement problem, not a prompt problem.** It is easy to tell an LLM "be fair to plain English." It is hard to actually verify that it is, and harder still to explain precisely what "fair" means in a way that can be measured. The paraphrase-pair approach gave us an operationalizable definition. The verifier-plus-deterministic-scoring architecture gave us a separable measurement surface. Getting both right was the hardest engineering problem in the project.

The second lesson was that **the Docker sandbox is non-trivial**. Making student code execution genuinely isolated — not just safe-by-default but provably so with a test harness — took significantly more thought than the initial estimate. The compile-in-same-container fix, the stdin/Docker flag interaction, and the OOM-kill confirmation were all things that weren't obvious from the documentation alone.

The third lesson is operational: **a new AWS account has Bedrock inference quotas that aren't adjustable through Service Quotas**. Account verification cleared after a few hours, but then a new-account daily token cap kicked in. This is documented, not hidden.

---

## Future improvements

1. **Run `ss measure` with Bedrock** and publish the real fairness-gap numbers. This is the most important next step.
2. **Tamil reviewer sign-off** — engage a Tamil-first CS student to review the 10 Tamil cases.
3. **Expand the paraphrase pair dataset** — 10 pairs across 7 concepts is a start; 50+ pairs across 20 concepts would be meaningful.
4. **Add the explain-again loop** (IDEA.md Innovation 5): when technical is correct but communication is low, invite one re-explanation. Only the communication score can change — the technical read is banked.
5. **Amazon Translate integration** for Tamil feedback (wired in the IAM policy, not yet in the code).
6. **Recommendation target mapping** for System Design concepts (currently `target_ref=null`; a pre-designed, backward-compatible extension is documented in `docs/phase-4-system-design-plan.md §13`).
7. **Multi-instance + RDS** if real user traffic arrives.
8. **CloudWatch billing alarm** once "Receive Billing Alerts" is enabled in the Billing console.

---

## Repository and resources

**Source code:** https://github.com/naveensri4518/CareerLift-AI

**Live application:** https://3-235-53-227.nip.io *(may be stopped after judging to conserve AWS credits — restart via `aws ec2 start-instances --instance-ids i-07ae636b8cda949bc`)*

**Demo video:** [VIDEO URL — upload results/demo.webm to YouTube/Vimeo and add the link here]

**To run locally (mock mode, no AWS needed):**
```bash
git clone https://github.com/naveensri4518/CareerLift-AI
cd CareerLift-AI
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
CAREERLIFT_MODEL_MODE=mock CAREERLIFT_DB=./careerlift.db CAREERLIFT_AUTH_PEPPER=local-dev \
  .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
# In a second terminal:
cd frontend && npm install && npm run dev
```

---

*Built with the Strands Agents SDK. Powered by Amazon Bedrock Nova 2 Lite. Deployed on AWS EC2.*
