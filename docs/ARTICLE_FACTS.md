# CareerLift AI — Verified Project Facts

All numbers below come from actual code, test output, or AWS CLI calls — not estimates or claims.
Section "pending" entries are honest: the measurement has not been run yet.

## Codebase

| Fact | Value | Source |
|---|---|---|
| Backend test count | 186 passed, 1 warning | `python -m pytest -p no:cacheprovider` — exit 0 |
| Test files | 16 | `ls tests/test_*.py` |
| Frontend build | Clean, exit 0 | `npm run build` in frontend/ |
| Frontend bundle size | ~810 KB (minified, pre-gzip) | Vite build output |
| Backend API endpoints | 40+ across 6 routers | `api/main.py` + routers/ |
| Phase 2 sandbox isolation checks | 11/11 PASS | `scripts/verify_sandbox.py` on production server |
| Public E2E tests | 13/13 PASS | `scripts/_e2e_public.sh` against live URL |

## Question bank (Phase 3)

| Fact | Value | Source |
|---|---|---|
| Total questions | 120 | `ss cases check` style count on assessment_questions.json |
| Categories | 12 (DSA, Java, Python, C, C++, DBMS, SQL, OS, Networks, OOP, Architecture, SE) | assessment_questions.json |
| Difficulty levels | 3 (beginner, intermediate, advanced) per category | assessment_questions.json |
| Question types | 3 (single-choice, multiple-select, true/false) | assessment_questions.json |

## Coding problem bank (Phase 2)

| Fact | Value | Source |
|---|---|---|
| Problems | 6 | coding_problems.json |
| Difficulties | Beginner (3), Intermediate (2), Advanced (1) | coding_problems.json |
| Supported languages | 3 (Python 3, C++17, Java 17) | coding_languages.py |
| Time limit | 2000–3000 ms per problem | coding_problems.json.limits |
| Memory limit | 256 MB | coding_problems.json.limits |

## System Design scenarios (Phase 4)

| Fact | Value | Source |
|---|---|---|
| Scenarios | 5 | sysdesign_scenarios.json |
| Difficulties | Beginner (1: URL Shortener), Intermediate (2: Rate Limiter, Image Upload), Advanced (2: News Feed, Chat) | sysdesign_scenarios.json |
| Component catalog | 14 components | sysdesign_scenarios.json.component_catalog |

## Evaluation dataset

| Fact | Value | Source |
|---|---|---|
| Total cases | 35 | `ss cases check` |
| Emergency/abstain cases | 8 | `ss cases check` |
| Tamil-language cases | 10 | `ss cases check` |
| English cases | 25 | `ss cases check` |
| Paraphrase pairs | 20 cases (10 pairs) | pair_id field in cases.jsonl |
| Unique personas | 4 | job field |
| Unsigned | 35 (all) | `ss cases check` — human sign-off required |
| Pipeline dry run | 35/35 scored, 0 errors, 0 unsafe | `scripts/_verify_score_fix.sh` (mock mode) |

## AWS infrastructure

| Fact | Value | Source |
|---|---|---|
| EC2 instance | i-07ae636b8cda949bc, t3.small, us-east-1a | AWS CLI describe-instances |
| AMI | ami-0c230065b91270bc6 (Amazon Linux 2023) | run-instances parameters |
| Root EBS | 16 GB gp3, delete-on-terminate | run-instances block-device-mapping |
| Data EBS | vol-0288c05bc070ca08d, 20 GB gp3, /data | create-volume + describe-volumes |
| EBS snapshot | snap-04152cf4eb55efe93 | create-snapshot (pre-demo) |
| Security group | sg-01b6c4bb7fc76f829 | describe-security-groups |
| SSH rule | 157.50.11.15/32 (WSL) + 1.51.57.41/32 (Windows) | describe-security-groups |
| IAM role | arn:aws:iam::074095960941:role/CareerLiftEC2RuntimeRole | create-role |
| SSM parameter | /careerlift/auth_pepper, SecureString, version 1 | describe-parameters |
| Budget | CareerLift-Monthly-25, $25/month gross, 3 email notifications | describe-budgets |
| HTTPS | Let's Encrypt cert for 3-235-53-227.nip.io, auto-renew | certbot |
| Month-to-date spend | $0 (instance provisioned recently) | ce get-cost-and-usage |

## Bedrock

| Fact | Value | Source |
|---|---|---|
| Model | amazon.nova-2-lite-v1:0 | bedrock get-foundation-model |
| Model status | ACTIVE | bedrock get-foundation-model |
| Inference profile | us.amazon.nova-2-lite-v1:0 (US Nova 2 Lite) | bedrock get-inference-profile |
| Profile status | ACTIVE | bedrock get-inference-profile |
| Last connectivity test | FAILURE — ThrottlingException: Too many tokens per day | 5 throttle events in CloudWatch |
| Inference gate | new-account daily token quota (not adjustable via Service Quotas) | service-quotas list-service-quotas |
| Default RPM quota | L-D5F39C2F, applied 0 but AWS default floor 2000 | service-quotas |

## PENDING (honest — not fabricated)

| Metric | Reason pending |
|---|---|
| Fairness gap (mean, CareerLift vs baseline) | Bedrock daily token quota + human case sign-off required |
| Technical accuracy vs labels | Same as above |
| Communication accuracy | Same as above |
| Unsupported-claim rate (agent vs baseline) | Same as above |
