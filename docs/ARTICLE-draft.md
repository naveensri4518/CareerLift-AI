# CareerLift AI — Builder Center article (DRAFT STRUCTURE, not for publication yet)

Rules: every number must be copied from `results/FACTS.md` after `ss measure`. Anything in [BRACKETS] is for the
builder to supply. Nothing below is a measured result.

## Social impact
- Who: [BUILDER: who you built this for, and what you saw or heard. Do not invent interviews.]
- The problem: technically capable students are rated down by interview tools and graders because their English is plain.
  IDEA.md labels the personas as design personas, not research findings. Keep that distinction.
- What changed: technical and communication are scored on two independent axes. Code, not the model, decides the band.
- Measured: [FROM FACTS.md: fairness gap on paraphrase pairs, technical accuracy vs labels, abstain behaviour, agent vs baseline].
  If measurement did not complete, say so plainly.

## Technical execution
- Strands blocks actually used: graph (evaluate with a bounded re-extract loop), structured output, a `BeforeModelCallEvent`
  input-gate hook, `FileSessionManager`, Strands Evals. Source: DESIGN.md and `docs/phase-aws-agent-design.md`.
- Deterministic core: FairScore bands, verifier, abstain rule, fairness check are plain Python (`agent/fairscore.py`).
- Five product modules around it: Learning Intelligence, Interview Studio, Secure Coding Arena (Docker isolation),
  Technical Assessment (120 questions), System Design Academy. 186 backend tests pass.
- Baseline comparison: [FROM FACTS.md].
- AWS: EC2 t3.small, EBS, IAM instance role, SSM SecureString, Bedrock Nova 2 Lite, CloudWatch budget guardrails.

## What we learned
- [FROM FAILURES.md: at least one real failure with before and after numbers.]
- Real examples that already exist in the project history (use only if you agree they are worth telling):
  the Bedrock inference hold and then daily-token throttle on a new account; t3.small not available in us-east-1e;
  a root-owned env file the service user could not read.

## Originality
- A measured fairness gap on a dual-axis scorer, not a blended chat score.
- Beyond a plain swarm: code-owned verdicts, a fail-closed verifier, a PII gate before any model call,
  and a sandbox that never runs student code in the API process.

## Limits (state these)
- Scenarios and labelled cases, not field outcomes. Labels were drafted by an assistant and signed by [REVIEWER NAME].
- Tamil cases reviewed by [NAME or "not reviewed by a native speaker"].
- Small dataset (35 cases, 7 reference concepts).

## Links
- Repo: [PUBLIC URL] · Video: [PUBLIC URL] · Live demo: https://3-235-53-227.nip.io (stop the instance after judging to save credits)
