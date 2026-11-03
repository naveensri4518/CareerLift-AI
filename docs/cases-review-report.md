# CareerLift AI — Evaluation Dataset Review Report (`cases.jsonl`)

Status: **35 cases, ALL UNSIGNED. Awaiting a named human reviewer.** No approval was fabricated. These
labels are drafts until a real person reads each one and signs with their own name.

## How to review and approve
1. Read every case: `ss cases show` (from the project root in WSL).
2. Validate structure/minimums: `ss cases check` (currently passes all minimums except signing).
3. For each label, confirm the expected technical/communication band and escalation are correct against
   the concept reference (`agent/data/concepts.json`).
4. Approve ONLY what you personally read, with YOUR real name:
   `~/.strands-ship/bin/ss cases approve --by "Your Full Name"` (or `--ids a,b,c` for a subset).
   A named external reviewer (a CS educator / interview coach) strengthens the evidence for judging.

## Gate status (from `ss cases check`)
```
counts: cases 35, emergency 8, care 0, ta 10, en 25, jobs 4, unsigned 35
minimums: cases 35>=30 OK | emergency 8>=8 OK | ta 10>=10 OK
blocker: UNSIGNED 35  -> needs a real reviewer's sign-off
```

## Composition
- **35 cases** across the four IDEA.md personas (`job`): rural college student, communication-struggling
  student, complete beginner, underserved-background student.
- **Languages:** 25 English, 10 Tamil (natural spoken Tamil, not translated English).
- **8 abstain cases** (`escalation: "emergency"` = "should abstain"): vague/"I don't know", one-sentence,
  off-topic, question-echo, and 2 PII-containing answers (en + ta) the input gate must catch.
- **Paraphrase pairs** (same technical content, plain vs advanced English, SAME expected technical band —
  the FairScore fairness core): bigo-avg, binsearch, recursion, worstcase, sqljoin, index, complexity-def,
  plus Tamil-register variants. These drive the fairness-gap metric.
- **Misconception cases** (expected `Weak`): hash-always-O(1), mutable-default-safe, inner=left join,
  index-has-no-downside, binary-search-on-unsorted.

## What each label asserts (so a reviewer knows what to check)
- `expected.technical_band` — the human-judged technical band (Weak/Partial/Solid/Strong) for the
  *technical content*, independent of English polish. For paraphrase pairs BOTH registers carry the SAME
  band by construction (identical content). Verify this is right for each.
- `expected.communication_band` — the clarity/structure/relevance/organisation band (plain English is NOT
  penalised). Pairs may legitimately differ here if structure differs.
- `expected.escalation` — `none` for scorable answers; `emergency` for answers that SHOULD cause the
  scorer to abstain (too little content, off-topic, or PII present).
- `expected_concepts` — the concept id(s) the answer is graded against (from `agent/data/concepts.json`).

## Reviewer checklist (per case)
- [ ] The technical band matches what a fair human grader would assign to the *content*.
- [ ] Plain-English phrasing did NOT lower the technical band vs its advanced-English pair.
- [ ] Misconception cases are genuinely wrong assertions (expected Weak), not merely terse.
- [ ] Abstain cases truly lack scorable content / contain PII.
- [ ] Tamil cases read as natural spoken Tamil and the labels match the content.
- [ ] No case contains real personal data beyond the deliberate synthetic PII-guard examples
      (`priya@example.com` / fake phone numbers — replace if you prefer different placeholders).

## Honest limitations (state these when the dataset is used)
- Labels are authored by one assistant as DRAFTS; they are not ground truth until a human signs.
- The set is small (35) and topic-concentrated on the 7 reference concepts; it demonstrates the fairness
  method, it is not a comprehensive benchmark.
- `ss measure` cannot run in Bedrock mode yet (account daily-token throttle — see the execution report),
  so no measured numbers exist for this dataset. None will be fabricated.
