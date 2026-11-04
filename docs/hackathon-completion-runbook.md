# CareerLift AI — Hackathon Completion Runbook

Status: preparation only. No evaluation numbers exist yet and none are claimed here.
Deadline (from `.kiro/steering/hackathon-rules.md`): **4 Nov 2026 11:59 PM PST = 5 Nov 2026 1:29 PM IST.**

## Order of operations (each step gates the next)

| # | Step | Who | Gate to proceed |
|---|------|-----|-----------------|
| 1 | Re-authenticate SSO (`aws sso login --profile career-lift --use-device-code`) | You (browser) | `sts get-caller-identity` works |
| 2 | ONE controlled Nova 2 Lite call, retries disabled (`AWS_MAX_ATTEMPTS=1`) | Kiro | A real structured response is returned |
| 3 | Human review and signing of the 35 cases | **A named person** | `ss cases check` shows 0 unsigned |
| 4 | `ss measure --limit 6`, then full `ss measure` | Kiro | Step 2 and Step 3 both done |
| 5 | Flip the server to `bedrock` mode | Kiro | Step 2 succeeded (measure is not required for the flip) |
| 6 | `ss video` | Kiro, then you watch it | `results/measure.json` exists |
| 7 | `ss ship`, README, ARTICLE, LICENSE | Kiro drafts, you supply story and licence choice | All FAIL rows cleared |
| 8 | Public repo, public video, Builder Center article, submit | **You only** | Before the deadline |

If the daily Bedrock throttle has not cleared by step 2, the fallback is to submit with the deterministic app, the
mock-labelled demo, and honest "measurement pending" wording. Do not publish any number that was not produced by `ss measure`.

## Human review workflow (step 3)
1. `cd` to the project in WSL and run `~/.strands-ship/bin/ss cases show`.
2. For each case confirm: expected technical band (content only), expected communication band, escalation
   (`emergency` means "should abstain"), and that both members of every paraphrase pair carry the same technical band.
3. Fix any label you disagree with directly in `cases.jsonl` (reviewer's call, not Kiro's), then re-run `ss cases check`.
4. Sign only what you read: `ss cases approve --by "Your Full Name"` (or `--ids id1,id2`).
5. Tamil cases should be read by a Tamil speaker. If that is not you, say so in the README limitations.
Kiro will not run `ss cases approve`.

## Measure runbook (step 4)
- `ss measure --limit 6` first. A partial run never passes the gate; it only catches crashes (about 12 Bedrock calls).
- Full `ss measure` is about 120 Bedrock calls on Nova 2 Lite. Run it once, only after steps 2 and 3.
- Never edit `results/`. If an unsafe plan appears, read the raw output, fix the cause, re-run, and log it in `FAILURES.md`
  with before and after numbers.
- Caveat to state honestly: the ship gate was written for the HeatSafe example. `agent/score.py` maps CareerLift's
  fairness and abstain meaning onto the harness keys. Report the gate result exactly as printed.

## Video workflow (step 6)
- `video.json` now holds three scenes: plain-English correct answer, the same ideas in advanced English, and a PII answer
  blocked by the input gate. The scene commands call `agent.app` live, so they use whatever `CAREERLIFT_MODEL_MODE` is set
  in the recording shell. Record in `bedrock` mode only after step 2 passes. Otherwise the on-screen output carries the
  "LOCAL DEMO / MOCK EVALUATION" label, which is acceptable only if the video says so.
- Must be under 180 s. Check: every scene exited 0, Tamil renders, no AWS account number or key on screen.
- Optional second recording (screen capture of https://3-235-53-227.nip.io): register, Dashboard, Coding Arena submission,
  Technical Assessment result, System Design result. Record this manually; `ss video` films only the agent scenes.
- You upload it publicly (no copyrighted music).

## Submission materials (step 7)
- `ss ship` produces `results/FACTS.md` and `SUBMISSION.md`. Every number in the article is copied from FACTS.md.
- README: what it does, architecture in five lines, how to run, results table, honest limits.
- LICENSE: **needs your choice** (Apache-2.0 or MIT). Kiro will not pick one for you.
- ARTICLE: structure drafted in `docs/ARTICLE-draft.md` with placeholders for the story only you can tell.
- Before the repo goes public: `git log -p | grep -E "AKIA|BEGIN .*PRIVATE KEY"` must print nothing.
  The project repo contains no keys (verified at each checkpoint), but the repo has never been scanned with that exact command.

## Automated EBS snapshots (review only; nothing created)
Current state: no snapshots exist for `vol-0288c05bc070ca08d` and no Data Lifecycle Manager policy is confirmed (the read-only
check failed on the expired SSO token and must be re-run after login).
Proposal if you approve it:
- One DLM policy, daily at 03:00 UTC, retain 3, target tag `Project=CareerLift` on volumes.
- DLM needs the service role `AWSDataLifecycleManagerDefaultRole` (one IAM role, no cost). It may already exist.
- Cost: snapshots are incremental. The volume holds roughly 0.2 GB of data, so expect well under $1/month even at full
  retention. That is inside the $25 budget and adds nothing to the target ~$19-21/month estimate worth noting.
- Cheaper alternative if you prefer no new resources: take one manual snapshot before the demo and one after.
Restore drill (to be run once, then documented): create a volume from the snapshot, attach it to a scratch instance or to
the same instance as `/dev/sdg`, mount read-only, confirm `careerlift.db` opens.
