# CareerLift AI

*Rethinking interview preparation through student empathy and multi-agent intelligence.*

> Status: brainstorm output (Recipe 1). No code, no AWS calls, no starter files modified.
> Next step requires approval: "design my agent".

---

## 0. Honesty notes you should read first

Three things are stated plainly so nothing downstream is misleading:

1. **The personas below are design personas, not research findings.** They describe students we are designing *for*. We have not interviewed anyone. No statistic in this document is a measured result. Every "we will measure X" is a *proposed* experiment, separated clearly from results (there are none yet).
2. **The measurable core does not depend on recruiting users.** CareerLift's headline claim — language fairness in technical scoring — is tested on a **human-labelled, paraphrase-paired dataset we build and sign off ourselves**. This is what makes the social-impact evidence honest and achievable in the hackathon window. Real students would strengthen it and are listed as a stretch, not a dependency.
3. **We do not claim to eliminate bias.** We claim to *measure and reduce a specific, named bias gap* against a one-prompt baseline, and to show the number.

---

## 1. Executive summary

CareerLift AI is an adaptive, multi-agent interview-preparation platform for students who can code but lack access to coaching and who are penalised — by humans and by naive AI graders alike — for speaking plain or non-native English.

Its central innovation is the **FairScore Engine**: technical competence and communication are scored on two independent axes, and a code-owned **language-fairness invariant** ensures that the same technical content, expressed in simple English or in advanced English, earns the same *technical* score. The band thresholds, the rubric, and the fairness tolerance live in plain Python; the model supplies evidence, not the verdict.

The honest, judge-facing metric is the **fairness gap**: for paraphrase-paired answers (same technical content, different English register), how far apart are the technical scores? A one-prompt baseline grader shows a large gap (fluent English scores higher). FairScore's purpose is to shrink that gap toward zero while staying accurate on technical correctness. `ss measure` reports both numbers, agent vs baseline, on signed cases.

Everything runs locally against Amazon Bedrock (Nova 2 Lite) with tight call budgets. SQLite for state. No standing AWS infrastructure.

---

## 2. Student personas (design personas — not measured)

**A. Rural college student.** Knows Java fundamentals; no placement coaching; can't afford paid prep; nervous speaking to interviewers. Needs: structured practice that explains *why* an answer is weak, free, offline-friendly.

**B. Technically capable, communication-struggling student.** Solves problems, knows SQL and data structures, but struggles to *explain* solutions in fluent English and starts doubting their own technical ability when they see fluent peers. Needs: to be told clearly "your technical content is correct; here is how to say it more clearly" — with the two judgments kept separate.

**C. Complete beginner.** First interview; doesn't know what to practise, what interviewers expect, why answers are wrong, or what to fix next. Needs: a system that tracks progress and points to the next thing, not a random question dispenser.

**D. Underserved-background student.** Ambition, limited resources; competing against peers with paid mentors and networks. Needs: an affordable, accessible preparation environment that doesn't assume prior polish.

The thread connecting all four: **the cost of conflating "can't say it in fancy English" with "doesn't know it."** That conflation is the problem CareerLift attacks, and it is the one existing tools and naive LLM graders most often get wrong.

---

## 3. Problem statement

Students who are technically competent but linguistically plain are systematically under-rated in interviews and by AI practice tools. Naive LLM graders reward fluency, vocabulary, and length — proxies that correlate with privilege, not with engineering ability. For an underserved student, a prep tool that penalises simple English is not neutral; it reinforces the exact disadvantage they came to overcome.

The decision that **must never be wrong**: a technically correct explanation must not be scored as technically weak because of its English. Getting this wrong harms precisely the students CareerLift exists to help.

---

## 4. Social impact

**Who it helps:** first-generation, rural, and underserved students entering software interviews, especially those who think in a regional language (Tamil supported via the kit's Amazon Translate fallback) and speak plain English.

**The mechanism of benefit:** separating technical from communication scoring, and enforcing language fairness on the technical axis, so a student gets an accurate read on what they actually need to improve (concept vs. expression) instead of a demoralising, conflated low score.

**Why this is measurable and honest:** the benefit is a property of the scorer, measurable on a labelled dataset *we* build, independent of recruiting users. See Section 13.

**Focus area:** Education (skills and employment equity).

---

## 5. Proposed solution

A practice loop:

1. Student picks a role, level, and topics.
2. An interviewer surface asks one question at a time and asks follow-ups.
3. The student answers in text (voice optional/stretch).
4. **FairScore** returns two separate scores — Technical and Communication — each with evidence, plus a fairness check.
5. The student sees *why*: which concept was right/wrong (technical) and how to say it more clearly (communication), never mixed.
6. A planner suggests the next focused exercise; progress is tracked across sessions.

The product surface is a polished SaaS app (designed later, Section 11). The judged artifact is the FairScore invariant and its measured gap.

---

## 6. Innovation concepts (five, each argued)

For each: real problem → solution → how it works → why different → how we demo → complexity.

### I1. FairScore language-fairness invariant *(headline)*
- **Problem:** plain-English students are mis-scored as technically weak.
- **Solution:** score Technical and Communication on independent axes; enforce a code-owned invariant that paraphrase-paired technical content scores within a tolerance band regardless of English register.
- **How it works:** the model extracts *technical claims* from an answer (structured output). A deterministic Python rubric maps claims-present → a technical band. A fairness test paraphrases/pairs answers and asserts the technical-score gap is within tolerance; if exceeded, the case is flagged and the scorer abstains from a confident technical verdict (fail-closed).
- **Why different:** most interview AIs produce one blended "score /100". A *measured fairness gap* is rare and memorable.
- **Demo:** show two answers with identical technical content, one plain, one ornate; baseline scores them differently, FairScore scores the technical axis equally.
- **Complexity:** medium. The rubric and invariant are plain Python; the hard part is the paired dataset.

### I2. Technical/Communication decoupling with evidence
- **Problem:** "your answer was bad" tells a student nothing actionable.
- **Solution:** two scores, each backed by extracted evidence spans ("you correctly identified O(n log n); you did not mention the base case").
- **How it works:** structured output lists technical claims and communication observations separately; the UI renders them in two panels.
- **Why different:** actionable, non-judgmental, separates "what you know" from "how you said it."
- **Demo:** side-by-side evidence panels after one answer.
- **Complexity:** low–medium.

### I3. Verification / abstain gate (the check the model cannot skip)
- **Problem:** confident-but-wrong AI feedback is worse than none for a beginner.
- **Solution:** a verifier that checks each technical claim the scorer made against a small curated concept reference; unsupported claims are dropped, and if too many are unsupported the scorer abstains rather than guessing.
- **How it works:** graph critic step with a fail-closed fallback; thresholds in code.
- **Why different:** turns "AI feedback" into *verified* feedback with a visible abstention path.
- **Demo:** force an unsupported claim and show the gate catch it.
- **Complexity:** medium.

### I4. Misconception tagging → knowledge-gap map
- **Problem:** students don't know *what* to study next.
- **Solution:** map wrong/partial answers to a small taxonomy of named misconceptions (e.g., "confuses average vs. worst case"), accumulated across sessions in SQLite.
- **How it works:** the evaluator tags each answer with zero or more taxonomy IDs; the planner reads the running tally.
- **Why different:** progress is modelled as named gaps closing, not a vanity score rising.
- **Demo:** a gap map that shrinks across two sessions.
- **Complexity:** medium.

### I5. Explain-again loop (confidence-aware, non-punitive)
- **Problem:** students freeze and self-doubt; a single failed answer reads as "you don't know this."
- **Solution:** when the technical content is right but communication is low, the system invites one re-explanation with a scaffold, and only the *communication* score can change — the technical read is already banked.
- **How it works:** a controlled second turn gated on `technical_correct && communication_low`; code decides eligibility.
- **Why different:** structurally encodes "you know this, let's just say it clearer" — directly serves Persona B.
- **Demo:** trigger the loop live; show the technical score stay fixed while communication improves.
- **Complexity:** low–medium.

**Selected for MVP:** I1, I2, I3 (these three *are* the originality and the measurable claim). I4 and I5 are secondary — high value, lower demo risk, added if time allows.

---

## 7. FairScore methodology

**Two axes, scored independently.**

- **Technical score** (band: 0–4 or Weak/Partial/Solid/Strong). Inputs: conceptual correctness, logical reasoning, problem-solving approach, correctness of any code, depth of understanding. Produced by: model extracts technical *claims* → deterministic rubric in Python maps claim coverage to a band.
- **Communication score** (separate band). Inputs: clarity, logical structure, relevance, organisation. Explicitly **not** vocabulary sophistication, grammar correctness, or length.

**Language-fairness rules (code-owned, never model-owned):**
- Do not penalise simple English.
- Do not reward ornate vocabulary.
- Do not treat grammar errors as technical ignorance.
- Recognise correct technical content regardless of linguistic polish.

**How fairness is enforced:**
1. The rubric scores the *technical claims extracted*, not the prose. Claim extraction is instructed to ignore register.
2. For evaluation, each case has a **paraphrase pair**: the same technical content in (a) plain/simple English and (b) advanced English. The invariant asserts `abs(tech_score(a) - tech_score(b)) <= FAIR_TOL`, with `FAIR_TOL` a constant in Python.
3. If a pair exceeds tolerance, that is a *fairness failure* — logged, and the scorer abstains from a confident technical verdict for that family (fail-closed).

**How we test the fairness property (honest, no user recruitment required):**
- Build a signed dataset of paraphrase pairs across several technical topics and both registers (and a Tamil subset via Translate fallback).
- Metric 1 — **Fairness gap:** mean and max `abs(tech(plain) - tech(advanced))`. Lower is better; baseline is expected to be high.
- Metric 2 — **Technical accuracy:** agreement of the technical band with the human label (so we don't "achieve fairness" by scoring everything the same).
- Report both for FairScore and for a one-prompt baseline grader via `ss measure`.
- **We do not claim perfect bias elimination.** We report the gap we measured.

---

## 8. Multi-agent architecture

**Decision: not five independent agents.** Five independent agents means five+ model calls per answer — it fights the cost rule, adds latency, and most of the "agents" are really deterministic steps. We use a **small graph with specialists, and push facts into code**:

- **Interviewer (agent / surface):** selects and asks questions, generates follow-ups. Role, level, topic in; question + follow-ups out. One model call per question turn.
- **Technical Evaluator (agent → structured output):** extracts technical claims from the answer. *Does not assign the final score.* Code assigns the band from the claims.
- **Communication Coach (agent → structured output):** observes clarity/structure/relevance/organisation. Separate structured output; never sees or touches the technical band.
- **Verifier (graph critic, fail-closed):** checks extracted technical claims against a curated concept reference; drops unsupported claims; triggers abstain if coverage is too low. This is the check the model cannot skip.
- **Learning Planner (mostly code + light model):** reads the SQLite misconception tally and picks the next exercise. Deterministic selection; model only phrases the suggestion.

**Strands blocks this maps to** (from `ss blocks`): **graph** (evaluator → verifier → conditional back), **tools / structured output** (claim and observation extraction, deterministic rubric as a `@tool`), **hooks** (fairness-fail / abstain gate on a node event), **sessions** (cross-session misconception memory in SQLite), optionally **guardrails** (PII/denied-topic filter) and **voice** (stretch). Swarm is deliberately *not* used — it adds nondeterminism and cost without buying us fairness.

**Facts owned by code (method rule 1):** the technical rubric bands, `FAIR_TOL`, the abstain threshold, and the concept reference. The model proposes claims and evidence; code decides the score and can override/abstain.

**Failure handling:** model returns malformed structured output → retry once, then abstain for that axis; verifier can't support claims → drop them, abstain if below threshold; Bedrock error → cached/last-known rubric path still returns a deterministic partial result and surfaces an error state (never a fabricated score).

---

## 9. User journey

First visit → pick target role → pick experience level → choose topics → start mock interview → answer in text (voice optional) → receive follow-up questions → get **separate** Technical and Communication scores with evidence → understand mistakes (named misconceptions, not vague) → get a personalised next exercise → track improvement across sessions → repeat.

Beginner-comfort details: supportive, non-judgmental tone; the explain-again loop so a frozen answer isn't a dead end; "your technical content was correct" shown prominently when true; empty/loading/error states designed, not afterthoughts; no internal tech names exposed in the UI.

---

## 10. Feature specifications (MVP vs secondary vs future)

**Essential MVP:**
- Role / level / topic selection.
- Single-question interview turn with one follow-up.
- Text answers.
- FairScore dual-axis scoring with evidence (I1 + I2).
- Verifier/abstain gate (I3).
- `ss measure`-backed fairness-gap + technical-accuracy evaluation vs baseline.
- SQLite persistence of a session.

**Secondary (if time allows):**
- Misconception gap map across sessions (I4).
- Explain-again loop (I5).
- Tamil subset via Translate fallback.

**Future:**
- Voice interaction (Nova Sonic, needs mic).
- Spaced-revision scheduling.
- Consented real-student field study to validate perceived fairness and learning gains.

---

## 11. Technical architecture

- **Frontend:** React + Vite + JavaScript + Tailwind + Lucide + Framer Motion. Polished SaaS surface; designed as a first-class deliverable (a visual reference image will be provided at the frontend phase — **not generated now**). No internal model/framework/endpoint names shown to users.
- **Backend:** Python + FastAPI + Strands Agents SDK.
- **AI:** Amazon Bedrock, Nova 2 Lite initially. Call budget enforced (one question-gen call, one claim-extraction, one communication-observation, one verify per turn — capped).
- **Database:** SQLite (MVP).
- **Testing:** Pytest, curated signed evaluation datasets, deterministic validation wherever possible (the rubric and invariant are pure functions, unit-testable without the model).
- Runs locally; no standing AWS infrastructure; Bedrock on-demand only.

---

## 12. Data flow

1. UI sends {role, level, topic} → Interviewer generates question.
2. Student answer → Technical Evaluator extracts claims (structured) **and** Communication Coach extracts observations (structured), independently.
3. Verifier checks technical claims vs concept reference → drops unsupported, may trigger abstain.
4. Deterministic rubric (Python) maps surviving claims → Technical band; maps observations → Communication band; fairness invariant checked.
5. Result {technical_band, communication_band, evidence, misconception_tags, abstained?} persisted to SQLite and returned to UI as two panels.
6. Planner reads misconception tally → next exercise.

No PII leaves the machine beyond the Bedrock request content; no raw model identifiers surface in the UI.

---

## 13. Evaluation methodology (proposed experiments — no results yet)

All of these are *designs*. Results, when produced, live only in `results/` via `ss measure`; numbers are never typed by hand.

- **FairScore consistency (headline):** fairness gap (mean/max technical-score difference on paraphrase pairs), FairScore vs one-prompt baseline. Target direction: FairScore gap materially lower than baseline.
- **Technical-score accuracy:** agreement of technical band with human labels (guards against "fairness by flattening").
- **Weakness/misconception detection accuracy:** tagged misconception vs human-labelled misconception on the dataset.
- **Feedback reliability:** fraction of technical claims that survive the verifier (unsupported-claim rate), FairScore vs baseline.
- **Abstain behaviour:** the scorer abstains (not guesses) on under-supported cases — reported as a safety number, not hidden.
- **Improvement across repeated interviews:** *proposed, stretch* — requires real users; stated as future, not claimed.

Dataset: paraphrase-paired, multi-topic, both English registers, Tamil subset; **human-labelled and signed off** (`ss cases approve --by "<real name>"`). Minimum counts and the signing discipline follow the kit's rules. We do not sign cases on anyone else's behalf.

---

## 14. Hackathon alignment (four quarters, 25% each)

- **Social impact:** names a specific underserved group and a specific, measurable harm (language-conflated mis-scoring) with a dataset-based metric that doesn't require recruiting users to be honest.
- **Technical execution:** Strands graph + structured output + hook + sessions, with facts owned by code and a fail-closed verifier; deterministic, unit-testable core.
- **Communication:** the article and video lead with the two-answers-same-content demo and the fairness-gap number — a single, vivid, honest story.
- **Originality:** a *measured fairness gap* on dual-axis scoring, not a blended interview chatbot; explicitly distinct from the kit's HeatSafe example (different domain, group, and the invariant is a scoring property, not a safety-threshold lookup).

**What makes it memorable:** "same answer, plain English vs fancy English — watch the baseline punish the plain one, and watch FairScore not."
**What judges should see live:** the paired-answer demo, the two separate score panels with evidence, the verifier catching an unsupported claim, and the `ss measure` gap number (agent vs baseline).
**Repo contents:** `agent/` (interviewer, evaluator, coach, verifier, planner, deterministic rubric), concept reference data, `cases.jsonl` (signed paraphrase pairs), `ship_kit/`, `results/` (generated), tests, `requirements.txt`, README, `FAILURES.md`.
**Article:** the problem, the FairScore idea, the architecture, the measured gap, what we learned, limitations.
**Not HeatSafe:** different focus sub-angle, different people, and the "never wrong" decision is a *fairness property*, not an emergency number.

---

## 15. Cost strategy

- Local-first; Bedrock on-demand only; Nova 2 Lite.
- Per-turn call cap (question, claim-extract, comm-observe, verify), with the rubric, fairness check, and planner selection running in pure Python (zero model cost).
- `ss measure` is the main token spend; run with `--limit` while iterating, full set only when gating.
- No Bedrock/Translate during brainstorming or design. No AWS resources without explicit approval.
- $120 promotional credit is a buffer, **not** a licence for unbounded calls; treat spend as real.

---

## 16. MVP scope

Smallest complete product that demonstrates genuine innovation: **a one-topic mock interview that returns dual-axis FairScore with evidence and a verifier gate, plus an `ss measure` fairness-gap result vs baseline on a signed paraphrase-paired dataset.** Everything else (gap map, explain-again, voice, Tamil) is additive and does not block the core demo.

---

## 17. Risks and mitigation

- **"It's just an interview chatbot."** → Lead every artifact with the fairness gap; the chatbot is the surface, the invariant is the product.
- **Fairness-by-flattening** (scoring everything the same to look fair). → The technical-accuracy metric guards against it; both numbers are reported together.
- **Model nondeterminism undermines a "fairness" claim.** → Technical band comes from a deterministic rubric over extracted claims, not from asking the model for a number; low temperature; retries then abstain.
- **Dataset bias authored by one person.** → Diverse topics and registers, explicit labelling rubric, real reviewer sign-off; state the limitation openly.
- **DrvFs `/mnt/c` write failures** (seen during setup) will recur for `results/` and video. → Decide project location (native Linux vs `/mnt/c`) before measuring; documented in setup notes.
- **Scope creep across five innovations.** → MVP is I1–I3 only; the rest are explicitly secondary.
- **Overclaiming impact.** → No fabricated statistics; proposed vs measured kept separate throughout.

---

## 18. Future roadmap

Voice (Nova Sonic) · spaced-revision scheduling · richer misconception taxonomy · multi-language expansion beyond Tamil · consented real-student field study measuring perceived fairness and callback/confidence changes · optional hosted deployment (only with explicit cost approval).

---

## Self-challenge (the five questions)

- **Genuinely useful to students?** Yes — it tells a plain-English student "your technical content is correct," which is the specific reassurance Personas A–D lack.
- **Different from a conventional chatbot?** Yes — the judged artifact is a measured fairness gap on a dual-axis scorer, not a chat transcript.
- **Innovation demonstrable?** Yes, and without recruiting users: paired-answer demo + `ss measure` number.
- **Architecture feasible?** Yes — small graph, facts in code, capped model calls, SQLite, local.
- **Real problem or AI-for-its-own-sake?** Real — language-conflated mis-scoring is exactly the disadvantage underserved students face, and naive LLM graders reproduce it.

---

## Decisions still open (for the design step)

1. **Project location:** native Linux (`~/careerlift-ai`, avoids the `/mnt/c` write failures and is faster) vs. staying on `/mnt/c`. Recommended: relocate.
2. **Scoring granularity:** 4-band vs 0–100 for the technical axis (bands are easier to make fair and to test).
3. **Tamil in MVP or secondary.** Recommended: secondary.

*Next: say "design my agent" to proceed to Recipe 2 (names the Strands blocks and what each does, writes DESIGN.md). No AWS calls will occur in that step either.*
