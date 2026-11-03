# CareerLift AI — AWS Architecture & Connectivity Plan

Status: **PLAN ONLY — nothing deployed, no AWS resources created, no billable calls, no source changed.**
This is the deliverable of a repository inspection. Await review/approval before any implementation.

Scope guardrails honored: no deploy, no provisioning, no IAM/key creation, no dependency installs, no
source edits, no Strands-Ship recipes.

---

## 1. Existing application architecture (inspected, not assumed)

### 1.1 Frontend
- React 18 + Vite 5 SPA (`frontend/`). Build: `npm run build` → static assets in `frontend/dist/`.
- Deps: react-router-dom, framer-motion, recharts, lucide-react, tailwind. No SSR; pure static output.
- API access: `frontend/src/api/client.js` → `API_BASE = import.meta.env.VITE_API_BASE || '/api'`. In dev,
  `vite.config.js` proxies `/api` → `http://127.0.0.1:8000` (strips `/api`). **In a production static build
  there is no dev proxy** — the browser must reach the backend via same-origin reverse proxy or an
  absolute `VITE_API_BASE` with backend CORS.
- Auth is a bearer token in `localStorage` (`careerlift.session`), sent as `Authorization: Bearer <t>`.

### 1.2 Backend
- Python 3.12 FastAPI (`api/`), served by uvicorn. `api/main.py` builds the app, runs `db.init_db()` on
  lifespan startup, configures CORS from `CAREERLIFT_CORS_ORIGINS`, and registers routers:
  learning, dashboard, studio (P1), coding (P2), assessment (P3), sysdesign (P4) + root `/health`,
  `/register`, `/interviews`, `/score`, `/students/{id}/...`.
- Run command (observed): `uvicorn api.main:app --host 0.0.0.0 --port 8000` with env vars.
- Deps (`requirements.txt`): fastapi, uvicorn, strands-agents (+ tools/evals/harness/shell), boto3,
  pydantic, httpx, pytest, playwright. Python stdlib `sqlite3` (no DB driver dep).

### 1.3 Database (SQLite — actual implementation)
- `agent/db.py`: single SQLite file at `CAREERLIFT_DB` (default `./careerlift.db`). One `SCHEMA` string of
  `CREATE TABLE IF NOT EXISTS` + idempotent `_migrate()` (ALTER ADD COLUMN). `PRAGMA foreign_keys=ON`.
- Tables: student, interview, answer, misconception, auth_token, skill_signal, learner_concept,
  activity_event, studio_session/question/answer, coding_submission, assessment_attempt,
  sysdesign_attempt. All per-student, small rows, JSON blobs for structured fields.
- Access pattern: short-lived connections per call (`connect()` context manager), low write concurrency
  (one student acting at a time). No connection pool; no ORM.

### 1.4 Authentication & security
- `api/auth.py`: server-generated `student_id` + opaque bearer token; only SHA-256(token + pepper) stored
  (`auth_token` table). Pepper from `CAREERLIFT_AUTH_PEPPER` (random per-process fallback → must be set in
  prod for tokens to survive restarts). `current_student` dependency resolves token→student (401);
  `require_owner`/row checks enforce per-student ownership (403). No passwords, no PII stored by design;
  an input gate (`agent/gates.py`) blocks PII before any model call.

### 1.5 File upload & storage
- **No file uploads exist.** No `UploadFile`/multipart/file-write endpoints anywhere in `api/` or `agent/`.
- The only local writes are: the SQLite DB file, and `agent/session.py` Strands `FileSessionManager` →
  `CAREERLIFT_SESSIONS` (default `results/sessions`). Phase 2 compiles/runs student code inside **Docker
  containers** with a per-run host temp dir that is deleted after each run (`agent/coding_exec.py`).
- Implication: **S3 is NOT required by current functionality.** It is only justified later if/when uploads
  (e.g. resume PDFs, diagram exports) are added. Flagged as optional/future, not a present need.

### 1.6 AI integration points
- The ONLY Bedrock-touching path is `/score` → `agent/app.py run()` → Strands graph → `BedrockModel`.
  Model: `SHIP_MODEL` (default `us.amazon.nova-2-lite-v1:0`), region `AWS_REGION` (default `us-east-1`),
  temperature 0.1. Credentials resolved via `boto3.Session()`; missing creds → clean 503.
- `CAREERLIFT_MODEL_MODE` (`bedrock` | `mock`, default `bedrock`) switches between the real Bedrock path
  and a deterministic offline mock (`agent/mockmodel.py`).
- **Phases 1–4 (studio, coding, assessment, sysdesign) are fully DETERMINISTIC** — they do not call
  Bedrock. Interview Studio uses the FairScore provider which *could* use Bedrock, but today runs mock.
  → Bedrock cost is driven almost entirely by `/score` (and optionally studio) volume, not by P2–P4.

### 1.7 Strands SDK compatibility
- Strands is **already integrated** (not a future task): `agent/app.py` uses `strands.Agent`,
  `strands.models.BedrockModel`, `strands.multiagent.GraphBuilder`, plus an input-gate hook. `session.py`
  uses `strands.session.FileSessionManager`. So "Strands integration" on AWS = giving the running backend
  Bedrock access + a writable session dir, not new code.

### 1.8 Environment variables (the real configuration surface)
`CAREERLIFT_MODEL_MODE`, `SHIP_MODEL`, `AWS_REGION`, `CAREERLIFT_AUTH_PEPPER`, `CAREERLIFT_DB`,
`CAREERLIFT_CORS_ORIGINS`, `CAREERLIFT_SESSIONS`, and (frontend build-time) `VITE_API_BASE` /
`CAREERLIFT_API_TARGET`. A Decider key (`DECIDER_API_KEY`) is referenced only in requirements comments; not
used by the app.

### 1.9 Docker configuration
- Only `docker/coding-sandbox.Dockerfile` (Phase 2 execution sandbox: python3 + g++ + JDK, non-root). There
  is **no app Dockerfile / docker-compose** for the API or frontend.
- **Decisive constraint:** the Coding Arena requires a reachable **Docker daemon on the backend host**
  (`agent/coding_exec.py` shells out to `docker run` with `--network none`, cpu/mem/pids limits, read-only
  rootfs). This requires a host where we control the Docker engine — i.e. a VM (EC2). It is incompatible
  with Lambda and awkward on fully-managed container runtimes (needs privileged docker-in-docker).

### 1.10 Dev vs prod server requirements
- Dev: `uvicorn --reload` on 8000 + `vite` dev server on 5173 with the `/api` proxy.
- Prod: a built static bundle served by a web server/reverse proxy, uvicorn (optionally behind gunicorn
  workers) for the API, Docker engine present for Phase 2, persistent disk for SQLite + sessions, and the
  auth pepper + model mode set via environment/secrets.

---

## 2. Proposed AWS architecture (diagram)

A single right-sized EC2 instance runs Nginx (static site + reverse proxy) + uvicorn + the Docker engine,
with an attached persistent EBS volume for SQLite/sessions, reaching Bedrock/Translate over the AWS
network via an IAM instance role. This is the simplest architecture that satisfies every real constraint
(Docker sandbox, SQLite file, low traffic) and fits a ~$120 credit budget.

```
                         Internet
                            │  HTTPS (443)
                            ▼
                 ┌───────────────────────┐
                 │  Amazon EC2 (1x)      │  t3.small (or t3.medium if sandbox load grows)
                 │  Amazon Linux 2023    │  Security Group: inbound 443 (+ 22 from your IP)
                 │ ┌───────────────────┐ │
    user ──443──▶│ │ Nginx             │ │  serves frontend/dist  +  proxies /api → 127.0.0.1:8000
                 │ └─────────┬─────────┘ │
                 │           ▼           │
                 │ ┌───────────────────┐ │
                 │ │ uvicorn (FastAPI) │ │  CAREERLIFT_MODEL_MODE=bedrock
                 │ │  api.main:app     │ │  boto3 via INSTANCE ROLE (no static keys)
                 │ └───┬───────────┬───┘ │
                 │     │           │     │
                 │     ▼           ▼     │
                 │ ┌────────┐ ┌─────────┐│
                 │ │ Docker │ │ SQLite  ││  careerlift.db + results/sessions
                 │ │ engine │ │ on EBS  ││  on a persistent EBS volume
                 │ └────────┘ └─────────┘│
                 └───────┬───────────────┘
                         │ AWS SDK (boto3), HTTPS, same region (us-east-1)
          ┌──────────────┼───────────────────────────┐
          ▼              ▼                             ▼
   Amazon Bedrock   Amazon Translate            Amazon CloudWatch
   (Nova 2 Lite)    (en→ta, optional/future)    (logs + basic alarms)

   AWS IAM: one EC2 instance role with least-privilege Bedrock(InvokeModel on the Nova inference
            profile) + Translate(TranslateText) + CloudWatch Logs. No access keys issued.
   Secrets: CAREERLIFT_AUTH_PEPPER in AWS SSM Parameter Store (SecureString), read at boot.
```

Optional later evolution (not day one): put Amazon CloudFront + S3 in front for the static frontend if
global latency matters; migrate SQLite → RDS only if multi-instance scaling becomes real (see §6).

---

## 3. Service-by-service justification

| Service | Use here | Verdict |
|---|---|---|
| **Amazon EC2** | Runs Nginx + FastAPI + **the Docker engine the Coding Arena requires** + the SQLite file | **Required.** The Docker-sandbox dependency and the single-file SQLite make one small VM the natural fit. |
| **Amazon Bedrock** | `/score` FairScore model calls (Nova 2 Lite) via Strands | **Required for `bedrock` mode.** Already coded; just needs IAM + model access enabled. |
| **Amazon Translate** | en→ta translation of feedback (planned) | **Optional / future.** Not wired in code today. Include IAM permission so it's ready; add the call later (see §9, §17). |
| **AWS IAM** | One EC2 instance role granting Bedrock/Translate/Logs; no static keys | **Required.** Instance role is the secure way `boto3.Session()` gets credentials on EC2. |
| **Amazon S3** | User file storage | **Not required now** (no uploads exist). Optional future: static-site hosting and/or resume/diagram storage. |
| **Amazon RDS** | Managed relational DB | **Not justified now** (see §6). Single-writer SQLite on EBS meets current needs; RDS only if we scale to >1 backend instance. |
| **Amazon CloudWatch** | Logs + a couple of alarms (CPU, status check, estimated charges) | **Recommended, cheap.** Main guardrail against runaway cost. |
| **AWS SSM Parameter Store** | Store `CAREERLIFT_AUTH_PEPPER` (SecureString) | **Recommended (free tier).** Keeps the pepper out of source and the AMI. |
| **Elastic IP** | Stable address for the instance/DNS | Optional; one EIP attached to a running instance is free. |

---

## 4. Frontend deployment architecture

Day-one (cheapest, simplest): build `frontend/dist/` and serve it as static files from **Nginx on the
same EC2 instance** that runs the API. Nginx also reverse-proxies `/api/ → http://127.0.0.1:8000/`
(stripping `/api`, mirroring the dev proxy). Because the browser then talks same-origin, **no CORS and no
`VITE_API_BASE` absolute URL are needed** — the simplest, most robust setup.

Build-time: `VITE_API_BASE` left unset so the client defaults to the same-origin `/api` prefix.

Optional upgrade (only if global latency matters): host `dist/` in an **S3 bucket + CloudFront**
distribution; then the API needs either CloudFront path-routing to the EC2 origin or backend CORS for the
CloudFront domain. Adds a moving part and a little cost; defer unless needed.

---

## 5. Backend deployment architecture

- **Process:** uvicorn running `api.main:app` on 127.0.0.1:8000 (not public; Nginx is the only public
  listener). Optionally `gunicorn -k uvicorn.workers.UvicornWorker` with 1–2 workers — **note the SQLite
  single-writer caveat**: multiple workers writing the same SQLite file can hit `database is locked`.
  Given low concurrency, **1 uvicorn worker is safest** initially; scale workers only with WAL mode +
  testing, or when moving to RDS.
- **Process supervision:** a `systemd` unit (restart on failure, start on boot) with the env vars set
  (`CAREERLIFT_MODEL_MODE=bedrock`, `AWS_REGION=us-east-1`, `CAREERLIFT_DB=/data/careerlift.db`,
  `CAREERLIFT_SESSIONS=/data/sessions`, pepper pulled from SSM at start).
- **Docker engine:** installed on the instance; the Phase 2 sandbox image built once
  (`scripts/build-sandbox.sh`). The instance role does NOT need Docker Hub creds (base images are public).
- **Persistent data:** a dedicated EBS volume mounted at `/data` holding the SQLite DB and sessions, so an
  instance replacement/AMI update does not lose student data.

---

## 6. Database architecture — can SQLite stay, or is RDS justified?

**Keep SQLite on persistent EBS for now. RDS is not justified yet.** Reasoning:
- Workload is single-instance, per-student, low write-concurrency, small rows. SQLite handles this well.
- The code uses stdlib `sqlite3` with short connections and `foreign_keys=ON`; moving to RDS means a new
  driver, a connection pool, SQL dialect review, and a migration — real work for no current benefit.
- **Durability** is the only real SQLite risk, solved by putting the file on a persistent EBS volume
  (survives instance stop/replace) plus periodic snapshots/backups.
- **Enable WAL mode** (`PRAGMA journal_mode=WAL`) to improve read/write concurrency — a small, isolated,
  separately-approved code change if we add uvicorn workers.

**RDS becomes justified only when:** we need >1 backend instance (horizontal scale / HA), or managed
backups/failover/point-in-time recovery become a requirement. At that point migrate to **RDS for
PostgreSQL** (db.t4g.micro). Until then RDS would add ~$12–15+/mo for no functional gain — a poor use of
limited credits.

---

## 7. Bedrock integration design

- Code is already in place (`agent/app.py _model()` → `BedrockModel`). AWS-side work is **config, not code**:
  1. In the target account/region (us-east-1), **enable model access** for Amazon Nova 2 Lite
     (`amazon.nova-2-lite-v1:0`) and use the **cross-region inference profile** id the code already
     defaults to (`us.amazon.nova-2-lite-v1:0`).
  2. Attach an IAM instance role allowing `bedrock:InvokeModel` (and `InvokeModelWithResponseStream` if
     used) scoped to the Nova model/inference-profile ARNs.
  3. Set `CAREERLIFT_MODEL_MODE=bedrock` and `AWS_REGION=us-east-1` in the systemd env.
- `boto3.Session()` on EC2 automatically picks up the instance role — **no static keys**. If the role is
  missing, the app already fails gracefully to a 503 (and can run `mock` as a fallback).
- Cost control: `/score` is the only hot Bedrock path; Nova 2 Lite is low cost-per-call; keep temperature
  and max tokens bounded (already temperature 0.1). Consider a simple per-student rate limit before
  enabling Bedrock publicly (noted as a risk, §16).

## 8. Strands SDK integration design

- Already integrated in code. On AWS it needs: (a) the Python deps from `requirements.txt` installed in the
  backend venv, (b) Bedrock access via the instance role (above), (c) a writable `CAREERLIFT_SESSIONS`
  directory on the EBS volume for `FileSessionManager`. No Strands-Ship recipe is run in production; the
  SDK is used as a library by `agent/app.py`. Nothing new to build.

## 9. Translate integration design (planned / future)

- Not wired today. When added: call `boto3.client("translate").translate_text(Text=..., SourceLanguageCode="en",
  TargetLanguageCode="ta")` from a small, isolated helper (e.g. `agent/translate.py`), invoked after a
  feedback string is produced, behind a feature flag/env (so it degrades to English if unavailable). The
  instance role includes `translate:TranslateText` so it's ready. Keep it out of the deterministic grading
  path (translation is presentation, not scoring) to preserve determinism and limit cost.

## 10. IAM & security architecture

- **One EC2 instance role** (no users, no access keys) with least privilege:
  - `bedrock:InvokeModel` (+ stream) on the Nova model/inference-profile ARNs only.
  - `translate:TranslateText` (for the future feature).
  - `ssm:GetParameter` on `/careerlift/*` (to read the auth pepper SecureString) + `kms:Decrypt` on the
    SSM key.
  - `logs:CreateLogStream` + `logs:PutLogEvents` on the app log group (CloudWatch).
  - Nothing else (no S3/RDS/EC2 management).
- **Secrets:** `CAREERLIFT_AUTH_PEPPER` in SSM Parameter Store (SecureString), fetched at service start;
  never baked into the AMI, source, or env files committed to the repo. No Bedrock/AWS keys anywhere (role
  only).
- **App security (already present, preserved):** bearer-token auth, hashed tokens + pepper, per-student
  ownership checks, PII input gate, Phase 2 container isolation (network-off, non-root, read-only rootfs,
  cpu/mem/pids caps). HTTPS terminated at Nginx (via a free certificate, e.g. Let's Encrypt/ACM-on-ALB if
  an ALB is later added).

## 11. Networking architecture

- Single VPC, one public subnet, the EC2 instance with a Security Group:
  - Inbound: 443 (HTTPS) from the internet; 22 (SSH) from your IP only; (80 only to redirect to 443).
  - Outbound: 443 to AWS service endpoints (Bedrock/Translate/SSM/CloudWatch) + general egress for package
    installs. Bedrock/Translate reached over the public AWS network by default; **VPC interface endpoints**
    for Bedrock/SSM are an optional hardening step (keeps traffic off the public internet) but add hourly
    endpoint cost — defer on a tight budget.
- The backend (uvicorn:8000) and Docker daemon are **not** exposed to the internet — only Nginx:443 is.
- An Elastic IP for a stable address; DNS (Route 53 or external) optional.

## 12. Estimated monthly cost scenarios (us-east-1, on-demand, approximate)

These are planning estimates, not quotes. Confirm against the AWS Pricing Calculator before committing.

| Component | Low (dev/demo) | Moderate | Notes |
|---|---|---|---|
| EC2 t3.small (2 vCPU/2 GB) | ~$15/mo (24×7) | — | Enough for API + light sandbox + SQLite |
| EC2 t3.medium (2 vCPU/4 GB) | — | ~$30/mo (24×7) | If coding-sandbox memory/concurrency grows |
| EBS (gp3, ~20–30 GB) | ~$2–3/mo | ~$3/mo | Persistent DB + sessions + sandbox image |
| Bedrock Nova 2 Lite | a few $ at low volume | $10–30+ | Scales with `/score` calls; low cost-per-call model |
| Amazon Translate | ~$0 | a few $ | $15 / million chars; first 2M chars/mo free for 12 months |
| CloudWatch logs/alarms | ~$0–1 | ~$1–3 | A few alarms + modest log volume |
| SSM Parameter Store | $0 | $0 | Standard params are free |
| Elastic IP (attached) | $0 | $0 | Free while attached to a running instance |
| **Rough total** | **~$20–25/mo** | **~$45–65/mo** | Dominated by EC2 uptime + Bedrock volume |

**Biggest cost levers:** (1) EC2 running 24×7 — stop/schedule it when idle to stretch credits; (2) Bedrock
call volume — keep `mock` mode for P1–P4 and gate `/score`. If the instance is stopped when not demoing,
monthly spend can drop well under $15.

## 13. AWS credit utilization strategy (~$120)

- **Eligible (covered by standard AWS promotional credits):** EC2, EBS, Bedrock, Translate, CloudWatch,
  SSM, data transfer, S3/CloudFront if later used. These are standard billed services credits apply to.
- **Do not assume covered:** Marketplace AMIs/software, some third-party/hosted add-ons, and the separate
  "AWS Social Impact" credit program are distinct — nothing here should depend on them. The hosted Decider
  key referenced in requirements is NOT an AWS service and is out of scope.
- **Stretching $120:**
  1. Keep P1–P4 in deterministic `mock` mode; only `/score` (and optionally studio) uses Bedrock.
  2. Run the smallest instance that holds the sandbox (start at t3.small); **stop the instance when not in
     use** (biggest saver).
  3. Set a **CloudWatch billing alarm** (e.g. at $20, $50, $90) and a Budgets alert — the single most
     important cost guardrail.
  4. Prefer public AWS endpoints over paid VPC interface endpoints initially.
  5. Use Translate's 12-month free tier (2M chars/mo) for the planned feature.
- With disciplined stop/start + mock-by-default, $120 comfortably covers a multi-month demo/dev runway.

## 14. Deployment sequence (when approved — not executed now)

1. Enable Bedrock **Nova 2 Lite model access** in the target account (us-east-1).
2. Create the IAM instance role (least-privilege, §10) and an SSM SecureString for the auth pepper.
3. Launch one EC2 instance (Amazon Linux 2023, t3.small), attach the role, attach/mount a `/data` EBS
   volume, open SG 443 + 22(your-IP).
4. Install runtime: Python 3.12 venv + `requirements.txt`, Docker engine, Nginx, the Node toolchain.
5. Build the frontend (`npm run build`) and the Phase 2 sandbox image (`scripts/build-sandbox.sh`).
6. Configure Nginx (serve `dist/`, proxy `/api`), and a `systemd` unit for uvicorn with env vars.
7. Set `CAREERLIFT_MODEL_MODE=bedrock`; smoke-test `/health`, then `/score` (confirm a real Bedrock call),
   then one flow per phase.
8. Add HTTPS (certificate), CloudWatch log shipping, and billing/budget alarms.
9. Snapshot the EBS volume (first backup) and document the run/stop procedure.

## 15. Rollback & recovery strategy

- **Model rollback:** flip `CAREERLIFT_MODEL_MODE=mock` (one env var + service restart) to instantly stop
  all Bedrock calls while keeping the app fully functional (P1–P4 are deterministic; `/score` degrades to
  the offline evaluator). This is the fastest cost/outage kill-switch.
- **App rollback:** keep the previous release directory; `systemctl` points at a symlink → revert the
  symlink + restart. Frontend rollback = re-deploy the previous `dist/`.
- **Data recovery:** EBS snapshots (daily + pre-change) for `/data`; SQLite file can also be copied while
  the service is briefly stopped. No destructive migrations are planned.
- **Infra recovery:** the instance is reproducible from the documented sequence (or a golden AMI); the
  durable state lives on the separate `/data` EBS volume, so re-launching and re-attaching restores state.
- **Teardown:** stopping the instance halts compute cost; deleting it + the EBS volume + EIP release stops
  all spend.

## 16. Risks & unresolved decisions

- **SQLite + multiple workers:** concurrent writers can hit `database is locked`. Decision: start with 1
  uvicorn worker; only add workers after enabling WAL + load testing, or move to RDS. (No code change yet.)
- **Docker-on-EC2 coupling:** the Coding Arena hard-requires a Docker daemon on the host, which locks us to
  VM-style compute (EC2) and complicates any future move to serverless/managed containers. Accepted for
  now; a future option is isolating code execution to a separate sandbox service.
- **Single instance = single point of failure / no HA.** Acceptable for a demo/credit-budget deployment;
  revisit (ALB + ≥2 instances + RDS) only if uptime SLAs appear.
- **Bedrock abuse/cost:** an open-registration app with a public `/score` could be driven to run up Bedrock
  cost. Mitigation before public exposure: per-student/IP rate limiting + the billing alarm + keeping
  registration/local-only until verified. (Noted; rate-limiting is a separate approved change.)
- **Translate scope:** confirm whether en→ta (or others) is actually wanted before building it; it's
  presentation-only and should stay out of the deterministic path.
- **Region:** code defaults to us-east-1 (best Bedrock/Nova availability). Confirm the credit account's
  region and Nova 2 Lite availability there.
- **Cost estimates are approximate** — verify with the AWS Pricing Calculator for the chosen instance/region
  before provisioning.

---

## 17. Files that WILL need modification during the FUTURE AWS integration

(For planning visibility only — NONE are changed in this task. Each is a small, additive, separately-
approved edit.)

| File | Change | Why |
|---|---|---|
| *(none for Bedrock)* `agent/app.py` | **No change expected.** | It already builds `BedrockModel` and reads `SHIP_MODEL`/`AWS_REGION`; AWS integration is config + IAM, not code. |
| Deployment env (systemd unit / `.env` on the host — **new file, not in repo**) | Set `CAREERLIFT_MODEL_MODE=bedrock`, `AWS_REGION`, `CAREERLIFT_DB=/data/...`, `CAREERLIFT_SESSIONS=/data/...`, pepper from SSM | Wire prod config without editing source. |
| `api/main.py` | Possibly add the production origin to CORS **only if** the frontend is served cross-origin (S3/CloudFront). **No change** if same-origin Nginx is used. | Browser must be an allowed origin when not same-origin. |
| `frontend` build config / `VITE_API_BASE` | Leave unset for same-origin Nginx; set an absolute API URL only for the cross-origin (S3/CloudFront) option. | Point the SPA at the API in prod. |
| `agent/translate.py` (**new, future**) + one call site in the feedback path | Add Translate helper behind a feature flag | Only if the Translate feature is approved (§9). |
| `agent/db.py` | Optional `PRAGMA journal_mode=WAL` | Only if multiple uvicorn workers are introduced (§6/§16). Separate approval. |
| New infra-only files (NOT app source): `Dockerfile`/compose for the API (optional), `nginx.conf`, `systemd` unit, deploy script | Package/run the app on EC2 | Deployment plumbing; does not alter application behavior. |

**Explicitly NOT modified by AWS integration:** Phase 0 `skills/*`, `activity.py`, `fairscore.py`,
`concepts.json`; all Phase 1–4 routers/eval/signals/bank modules; the DB schema; the frontend pages. AWS
integration is overwhelmingly **configuration, IAM, and deployment plumbing — not application code
changes.**

---

## 18. Summary of findings (what the inspection changed vs. the brief's assumptions)

- **S3 is not currently needed** — there are no file uploads in the app. Listed as optional/future only.
- **Translate is not wired** — it's planned, not integrated; IAM will be ready, code comes later.
- **Strands SDK is already integrated** — not a future task; AWS just needs to grant it Bedrock access.
- **The Coding Arena's Docker-daemon requirement is the decisive compute constraint** → EC2 (a VM), not
  Lambda/serverless.
- **SQLite should stay** on persistent EBS for now; RDS is deferred until multi-instance scaling is real.
- **The dominant cost levers are EC2 uptime and Bedrock call volume**; mock-by-default for P1–P4 + stop/start
  + a billing alarm keep a $120 budget comfortable.
