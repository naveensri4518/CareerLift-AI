# CareerLift AI — Deployment Checklist (EC2 single-instance)

Status: **PREPARATION ONLY. Nothing provisioned.** This is the step-by-step runbook to execute once you
approve provisioning. Target: one EC2 instance running Nginx + FastAPI/uvicorn + Docker engine, with a
persistent EBS volume, reaching Bedrock via an IAM instance role. Region us-east-1, tag `Project=CareerLift`.

Legend: [admin] = privileged/one-time · [dev] = the career-lift developer identity · [verify] = check step.

## 0. Pre-flight (before any resource)
- [ ] Bedrock Nova 2 Lite daily-token throttle has cleared (one controlled connectivity test succeeds). **PENDING**
- [x] IAM instance role `CareerLiftEC2RuntimeRole` + instance profile **CREATED & VERIFIED**
  (`arn:aws:iam::074095960941:role/CareerLiftEC2RuntimeRole` + matching instance profile; inline policy
  `CareerLiftRuntimeInline`, least-privilege, `Project=CareerLift` tag).
- [x] SSM SecureString `/careerlift/auth_pepper` **CREATED & VERIFIED** (version 1, Standard, 64-char value,
  decrypts via the default `aws/ssm` KMS key — value never printed/committed).
- [x] Budget `CareerLift-Monthly-25` active with $15/$20/$25 email notifications. **DONE & VERIFIED**
- [ ] Decide: enable "Receive Billing Alerts" in Billing console if a CloudWatch billing alarm is wanted. [admin]

## 1. EC2 instance
- [ ] AMI: **Amazon Linux 2023** (x86_64), latest. [dev]
- [ ] Type: **t3.small** (2 vCPU / 2 GB) to start; upgrade to t3.medium only if sandbox memory/concurrency needs it.
- [ ] Attach IAM instance profile `CareerLiftEC2RuntimeRole` (NO static keys).
- [ ] Root EBS: gp3 ~16 GB (OS + image). Tag `Project=CareerLift`.
- [ ] Key pair for SSH (store the private key locally; never commit).

## 2. Persistent storage (EBS)
- [ ] Create a **separate gp3 EBS volume** (~20 GB) for durable app data; tag `Project=CareerLift`.
- [ ] Attach + mount at `/data`; add to `/etc/fstab` (mount on boot).
- [ ] This holds: `CAREERLIFT_DB=/data/careerlift.db` and `CAREERLIFT_SESSIONS=/data/sessions` (Strands FileSessionManager).
- [ ] [verify] A stop/start of the instance preserves `/data`.

## 3. Docker engine (Phase 2 coding sandbox)
- [ ] `sudo dnf install -y docker && sudo systemctl enable --now docker`.
- [ ] Add the app user to the `docker` group.
- [ ] Build the sandbox image once: `bash scripts/build-sandbox.sh` (→ `careerlift-coding-sandbox:latest`).
- [ ] [verify] `python scripts/verify_sandbox.py` → 11/11 isolation checks pass (network off, read-only rootfs, non-root, mem/pids/time limits).

## 4. Backend (FastAPI / uvicorn)
- [ ] Python 3.12 venv; `pip install -r requirements.txt`.
- [ ] `systemd` unit `careerlift-api.service`: runs `uvicorn api.main:app --host 127.0.0.1 --port 8000` (bound to loopback — only Nginx is public). 1 worker initially (SQLite single-writer).
- [ ] Env (from systemd `Environment=` / EnvironmentFile; pepper pulled from SSM at start):
  `CAREERLIFT_MODEL_MODE=bedrock` (or `mock` until Bedrock verified), `AWS_REGION=us-east-1`,
  `SHIP_MODEL=us.amazon.nova-2-lite-v1:0`, `CAREERLIFT_DB=/data/careerlift.db`,
  `CAREERLIFT_SESSIONS=/data/sessions`, `CAREERLIFT_AUTH_PEPPER=<from SSM>`,
  `CAREERLIFT_CORS_ORIGINS` (only if cross-origin; same-origin Nginx needs none).
- [ ] `systemctl enable --now careerlift-api`; [verify] `curl 127.0.0.1:8000/health` → ok.

## 5. Frontend (React production build)
- [ ] `cd frontend && npm ci && npm run build` → `frontend/dist/`.
- [ ] `VITE_API_BASE` left UNSET (same-origin `/api` via Nginx) — simplest, no CORS.
- [ ] Copy `dist/` to the Nginx web root (e.g. `/var/www/careerlift`).

## 6. Nginx (static site + reverse proxy + HTTPS)
- [ ] `sudo dnf install -y nginx`.
- [ ] Server block: serve `/var/www/careerlift` (SPA fallback to `index.html`); proxy `location /api/ { proxy_pass http://127.0.0.1:8000/; }` (strip `/api`).
- [ ] HTTPS on 443: certificate via Let's Encrypt (certbot) or an ACM cert if an ALB is later added; redirect 80→443.
- [ ] [verify] `https://<host>/` loads the SPA; `https://<host>/api/health` → ok.

## 7. Networking / Security Group
- [ ] SG inbound: **443** from the internet; **22** from the developer's public IP only; **80** only to redirect→443.
- [ ] SG outbound: 443 to AWS endpoints (Bedrock/SSM/CloudWatch) + package mirrors.
- [ ] uvicorn:8000 and Docker are NOT internet-exposed (loopback only). [verify] port scan shows only 443 (+22 from your IP).
- [ ] Optional Elastic IP for a stable address (free while attached).

## 8. IAM runtime role + Bedrock permissions
- [ ] Instance role grants least-privilege: `bedrock:InvokeModel`/`InvokeModelWithResponseStream` on the Nova
  model + `us.amazon.nova-2-lite-v1:0` inference-profile ARNs; `translate:TranslateText` (future);
  `ssm:GetParameter` on `/careerlift/*`; `logs:*` on the app log group; scoped `cloudwatch:PutMetricData`.
  (Full JSON in `docs/aws-iam-policy-changes.md` Part B.)
- [ ] [verify] On the instance, `aws sts get-caller-identity` shows the role; one controlled Bedrock test succeeds.

## 9. Secrets (SSM Parameter Store)
- [ ] `/careerlift/auth_pepper` = a strong random value (SecureString). Never in git, env files, or the AMI.
- [ ] systemd start script fetches it via `aws ssm get-parameter --with-decryption`.
- [ ] [verify] Tokens persist across an API restart (pepper is stable).

## 10. CloudWatch monitoring
- [ ] CloudWatch agent ships `careerlift-api` logs to log group `/careerlift/api` (retention e.g. 14–30 days).
- [ ] Alarms: instance StatusCheckFailed; CPUUtilization high; (optional) billing alarm IF "Receive Billing Alerts" enabled.
- [ ] [verify] Logs appear in the console; a forced high-CPU triggers the alarm state.

## 11. HTTPS
- [ ] Covered in §6. [verify] valid cert, auto-renew configured (certbot timer), HSTS optional.

## 12. Backup & recovery
- [ ] Scheduled EBS snapshot of the `/data` volume (daily + before any change).
- [ ] [verify] Restore drill: create a volume from a snapshot, attach to a fresh instance, app sees the data.
- [ ] Keep the previous release dir + a release symlink for fast app rollback.

## 13. Shutdown & cleanup procedure
- [ ] Cost pause: `aws ec2 stop-instances` (halts compute cost; `/data` + EIP persist). Start again to resume.
- [ ] Model kill-switch: set `CAREERLIFT_MODEL_MODE=mock` + restart → instantly stop all Bedrock calls, app stays fully functional.
- [ ] Full teardown: terminate instance → delete the `/data` EBS volume (after a final snapshot) → release the Elastic IP → delete the log group. [verify] Cost Explorer returns to ~$0.

## 14. Post-deploy verification (public)
- [ ] Register + login works. [ ] Dashboard/Progress load. [ ] Interview Studio, Coding Arena (run+submit), Technical Assessment, System Design Academy all work. [ ] Data persists across an instance restart. [ ] No internal model/provider names leak in the UI.

## Notes
- SQLite stays (single instance); migrate to RDS only if multi-instance scaling becomes real.
- Keep `CAREERLIFT_MODEL_MODE=mock` until the Bedrock daily throttle clears and one controlled test passes;
  then flip to `bedrock`. Phases 2–4 are deterministic and never call Bedrock regardless of mode.
