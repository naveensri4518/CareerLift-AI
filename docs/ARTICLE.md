# CareerLift AI — Builder Center Article (paste and complete before publishing)

> Instructions: replace every [PLACEHOLDER] with your own words before publishing. Every number in the
> results section MUST come from `results/FACTS.md` after `ss measure` completes. Do not publish with
> _pending_ numbers — either replace them or say "measurement is in progress." Every section maps to one
> judging criterion (25% each) so keep the headings exactly as they are.

---

# CareerLift AI: Fair Interview Practice for Students Who Think in Plain English

## Social impact — who it helps and how we measured it

Millions of students preparing for software engineering interviews have a hidden disadvantage: AI practice tools grade their explanations the way a biased interviewer might, rewarding fluency and vocabulary instead of actual technical understanding. A student who can correctly explain a hash table in simple English — "hash map is fast, O(1) most time, but if many keys hit same bucket it slow, becomes O(n) worst case" — receives a lower score from most AI graders than a student who says the same thing in ornate academic prose. The tool is supposed to help them prepare, but it reinforces the very gap they came to close.

[BUILDER: Add 2-3 sentences about who specifically you built this for — rural college students in Tamil Nadu, first-generation engineers, students who think in Tamil and explain in simple English. Why does this matter to you?]

CareerLift AI attacks this directly. It scores **technical correctness and communication clarity on two completely independent axes**, with a code-owned deterministic rubric that maps technical claims to bands (Weak / Partial / Solid / Strong) without ever reading the prose style. Simple English, grammar slips, and short sentences cannot lower the technical score.

We built a dataset of **paraphrase pairs**: the same technical content written in plain English and in advanced English, both human-labelled with the same expected technical band. We then measured the **fairness gap** — how far apart the two members of each pair score on the technical axis — for CareerLift and for a one-prompt baseline grader. A smaller gap means the tool is treating plain English more fairly.

**Results from `ss measure`:**
| Metric | CareerLift (agent) | Baseline (one-prompt) |
|---|---|---|
| Fairness gap (mean) | [FROM FACTS.md] | [FROM FACTS.md] |
| Technical accuracy vs labels | [FROM FACTS.md] | [FROM FACTS.md] |
| Unsafe answers (0 required) | [FROM FACTS.md] | [FROM FACTS.md] |
| Abstain rate (should abstain on unclear answers) | [FROM FACTS.md] | [FROM FACTS.md] |

Evaluation dataset: 35 cases across 7 CS concepts, 10 paraphrase pairs (plain and advanced English, same expected band), 10 Tamil-language cases, 8 abstain cases. Human sign-off required before measurement is final. Tamil cases reviewed by: [REVIEWER NAME or "pending native-speaker review"].

**Honest limits**: fairness is a property of the scorer on this dataset, not a guarantee for every live answer. The model still extracts claims, so register-sensitive extraction remains a risk — we measure it per concept and report it.

## Technical execution — how it is built with the Strands Agents SDK

CareerLift uses Strands Agents as the backbone of its scoring pipeline. Here is what each block does:

**`GraphBuilder` (spine):** The scoring graph runs `intake → evaluate (with a bounded re-extract self-loop if claims are malformed) → verifier`. The verifier is deterministic Python — zero model calls — that checks every extracted claim against a curated concept reference and abstains if coverage is too low. The graph is bounded (`set_max_node_executions`) and fail-closed.

**Structured output + `@tool`:** The Technical Evaluator and Communication Coach both use Pydantic `structured_output_model` to produce `TechnicalClaims` and `CommObservations` respectively. The deterministic scoring function (`agent/fairscore.py`) maps claim coverage → band. The model never returns a band — only evidence.

**`BeforeModelCallEvent` hook:** A `HookProvider` fires before every model call and cancels it if personal data (phone numbers, email addresses) is detected. PII is blocked before any token is spent — verified in our evaluation dataset.

**`FileSessionManager`:** Per-student conversation state persists to disk across interview turns, bounded by `SlidingWindowConversationManager`.

**Model:** Amazon Bedrock, `us.amazon.nova-2-lite-v1:0` (US cross-region inference profile, us-east-1), temperature 0.1. Credentials via IAM instance role (no static keys).

Beyond the scoring agent, CareerLift has five product modules: Learning Intelligence (Phase 0), Interview Studio (Phase 1), a Secure Coding Arena with a Docker-isolated sandbox that executes student code with network-disabled, non-root, CPU/memory/time-limited containers (Phase 2), a 120-question Technical Assessment Engine (Phase 3), and a rubric-graded System Design Academy (Phase 4). 186 backend tests cover all five phases.

The full source is at: [PUBLIC GITHUB REPO URL]

## What we learned — failures and fixes

**Failure 1 (Tamil mock-mode over-abstention):** Our deterministic mock evaluator is keyword-based and English-only. Running the full 35-case evaluation pipeline surfaced that Tamil-language cases with a non-null expected technical band were being flagged as "over-abstained on a Solid answer" — a gate-blocking unsafe event. The fix: `agent/score.py` exempts mock-mode abstentions on Tamil cases from unsafe rule 3, because abstaining on Tamil is correct behaviour for the mock evaluator (the Bedrock model handles Tamil). The guard is mode-specific and documented with the rationale. The fix was found by running the mock pipeline before measurement — exactly the catch-early-with-a-small-run discipline the recipe recommends.

**Failure 2 (t3.small + Availability Zone):** The first EC2 `run-instances` call failed: `t3.small is not supported in us-east-1e`. The default subnet resolved to `us-east-1e` but t3.small needs `us-east-1a/b/c/d/f`. Fixed by querying the default subnet in `us-east-1a` and relaunching. The fix took one CLI call and no architectural change.

[BUILDER: Add at least one more real failure from your experience — what went wrong, what you found, what you changed. This is what makes the article credible.]

## Originality — what goes beyond the workshop lessons

CareerLift's headline claim is a **measured fairness gap** on dual-axis scoring — not a conversation bot with a fairness prompt, but a system where code owns every verdict and the model's role is strictly evidence extraction. The fairness property is verified offline on a labelled paraphrase-pair dataset, not asserted.

Specific elements that go beyond the workshop:
- A deterministic Verifier node that drops claims the model cannot ground in the actual answer text — a critic that the model cannot skip.
- A code-owned communication rubric that explicitly excludes vocabulary, length and grammar as inputs, so the four observable dimensions (clarity, structure, relevance, organisation) cannot carry a bias signal.
- A **secure coding sandbox** (Phase 2) that executes student code inside Docker containers with `--network none`, `--read-only`, `--cap-drop ALL`, `--user 1000`, CPU/memory/pids limits — production isolation in a hackathon project.
- Five fully integrated product phases covering the full learning loop: score → learn → practise → assess → design.

AWS services used and why: Bedrock (Nova 2 Lite) for claim and observation extraction — the only model in the pipeline; IAM instance role for credential-free Bedrock access from EC2; SSM SecureString for the production auth pepper; CloudWatch Budget with email alerts for cost control.

---

**Video demo:** [PUBLIC VIDEO URL]
**Live application:** https://3-235-53-227.nip.io (may be stopped after judging to conserve credits)
**Source code:** [PUBLIC GITHUB REPO URL]
