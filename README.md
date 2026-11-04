# CareerLift AI

**Fair, explainable interview preparation for students who are technically strong but linguistically plain.**

CareerLift AI runs realistic technical interviews and scores answers on **two independent axes** — Technical and Communication — so a student who explains a concept in simple English is never penalised for vocabulary they haven't practised. Code owns the verdict; the model supplies evidence, not scores.

## The problem

Students who think clearly but write plainly are systematically under-rated by naive AI graders, which reward fluency as a proxy for ability. For a first-generation or rural student, a prep tool that penalises simple English is not neutral: it reinforces the exact disadvantage they came to overcome. CareerLift measures and reduces this specific, named bias gap.

## Who it helps

Students preparing for software engineering interviews — especially those from rural colleges, underserved backgrounds, or non-English-first households who can code but are penalised for the way they explain their code.

## Architecture

```
Student answer
    │
    ▼
[Input gate — PII check before any model call]
    │
    ▼
Strands graph (GraphBuilder)
    │
    ├─▶ Technical Evaluator (BedrockModel, structured output) ─▶ Verifier (deterministic Python)
    └─▶ Communication Coach (BedrockModel, structured output)
    │
    ▼
Deterministic scoring in Python (fairscore.py)
    │   Bands: Weak / Partial / Solid / Strong
    │   Code decides the band — model never returns a number
    ▼
ScoreResult {technical_band, communication_band, evidence, misconception_tags}
    │
    ▼
Phase 0 Learning Intelligence (SkillSignals → LearnerModel → Recommendations)
```

**Strands blocks used:** `GraphBuilder` (evaluate → re-extract loop → verifier), structured output, `BeforeModelCallEvent` hook (PII gate), `FileSessionManager`.

**AWS:** EC2 t3.small (Amazon Linux 2023), EBS persistent storage, IAM instance role, SSM SecureString (auth pepper), Bedrock Nova 2 Lite (`us.amazon.nova-2-lite-v1:0`, us-east-1).

**Five product modules:** Learning Intelligence (Phase 0), Interview Studio (Phase 1), Secure Coding Arena — Docker-isolated sandbox (Phase 2), Technical Assessment Engine — 120 MCQ questions across 12 CS topics (Phase 3), System Design Academy — rubric-graded structured design challenges (Phase 4).

## How to run locally

```bash
# Requirements: Python 3.12, Node 20, Docker Engine

# Backend (mock mode, no AWS needed)
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
CAREERLIFT_MODEL_MODE=mock CAREERLIFT_DB=./careerlift.db CAREERLIFT_AUTH_PEPPER=local-dev \
  .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev     # → http://localhost:5173

# Bedrock mode (needs AWS credentials with bedrock:InvokeModel on Nova 2 Lite)
CAREERLIFT_MODEL_MODE=bedrock AWS_REGION=us-east-1 ...
```

## Evaluation results

> Measurement (ss measure) requires signed evaluation cases and successful Bedrock inference.
> The pipeline runs end-to-end in mock mode: 35 cases, 0 errors, 0 unsafe events.
> Numbers will be filled in from `results/MEASURE.md` once measurement completes.

| Metric | Agent | Baseline |
|---|---|---|
| Fairness gap (mean) | _pending_ | _pending_ |
| Technical accuracy | _pending_ | _pending_ |
| Unsafe answers | _pending_ | _pending_ |
| Abstain rate | _pending_ | _pending_ |

## Limits (stated honestly)

- Evaluation cases are labelled by the developer as drafts; ground truth requires human sign-off.
- Fairness is a property of the scorer measured on a dataset, not a guarantee for every live answer.
- Tamil cases need a native-speaker review; the mock evaluator is English-only.
- The daily Bedrock token quota on a new account may delay measurement.

## Tests

```bash
# 186 backend tests
python -m pytest -q

# Frontend build
cd frontend && npm run build
```

## Live demo

https://3-235-53-227.nip.io (stop the instance after judging to conserve credits)

## Licence

MIT — see `LICENSE`.
