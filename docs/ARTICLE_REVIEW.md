# CareerLift AI — Article Review Checklist

## Hackathon judging criteria coverage (25% each)

| Criterion | Section(s) in ARTICLE.md | Status |
|---|---|---|
| **Social impact** | "Social impact — who it helps and how we measured it" | ✅ Present. Measurement table marked pending honestly. |
| **Technical execution** | "Technical implementation — Strands SDK and agent architecture" + all phase sections | ✅ Present. Strands blocks named and explained. |
| **Communication quality** | Introduction, real-world use cases, failures, what I learned | ✅ Present. Plain language. Vivid concrete examples. |
| **Originality** | Implicit throughout; specifically: verifier, comm rubric, Docker sandbox, 5-phase scope | ✅ Present. Goes beyond workshop lessons, documented. |

## Mandatory hackathon requirements coverage

| Requirement | Status | Where |
|---|---|---|
| Agent addresses real social-good challenge | ✅ | Introduction + Social impact section |
| Education / health / climate focus | ✅ | Education — interview prep equity |
| Measurable improvement for underserved populations | ✅ (pending full numbers) | Social impact section, table with pending |
| Strands Agents SDK usage explained | ✅ | Technical implementation section |
| Problem statement | ✅ | Introduction + Social impact |
| Who it helps | ✅ | Social impact + real-world use cases |
| What I learned | ✅ | "What I learned" section |
| Results table | ✅ (pending) | Social impact — clearly marked pending, not fabricated |
| Public GitHub repo link | ✅ | Footer section |
| Live application link | ✅ | Footer section |
| Demo video link | ⚠️ MISSING — video recorded, not yet uploaded | Footer — `[VIDEO URL]` placeholder |
| Failures documented | ✅ | "Technical challenges and solutions" + FAILURES.md |
| Limitations disclosed | ✅ | "Limitations and honest observations" section |

## Diagram accuracy check

| Diagram | Technical accuracy | No fictional components |
|---|---|---|
| 01-system-architecture.svg | ✅ All components match actual code | ✅ |
| 02-fairscore-pipeline.svg | ✅ Graph topology matches app.py | ✅ |
| 03-coding-arena.svg | ✅ All Docker flags match coding_exec.py + verified | ✅ |
| 04-aws-deployment.svg | ✅ All resources created and verified | ✅ |
| 05-five-phases.svg | ✅ All phases implemented and tested | ✅ |
| 06-fairness-concept.svg | ✅ Illustrates the problem; no fabricated numbers | ✅ |

## Secret/credential check

| Check | Status |
|---|---|
| AWS access keys in article | ✅ None |
| SSM pepper value | ✅ Not present |
| SSH key content | ✅ Not present |
| Kironomics API key | ✅ Not present (replaced with placeholder in committed file) |
| Bearer tokens | ✅ None |

## Placeholders that MUST be filled before publishing

| Placeholder | Location | What to do |
|---|---|---|
| `[VIDEO URL]` | Footer of ARTICLE.md | Upload `results/demo.webm` to YouTube/Vimeo, paste the URL |
| Results table numbers | Social impact table | Run `ss measure` after human case sign-off + Bedrock quota clears; copy from `results/FACTS.md` |
| `REVIEWER NAME` in evaluation note | Social impact section | Add the name of whoever reviews and signs the Tamil cases |

## Steps to publish on Builder Center

1. Fill in the 3 placeholders above.
2. Copy the full content of `docs/ARTICLE.md`.
3. Paste into the Builder Center article editor.
4. Embed images by uploading the SVGs from `docs/article/images/` and the screenshots from `frontend/screenshots/` to the Builder Center media library, then replace the image references with the Builder Center URLs.
5. Publish.

## Overall readiness

| Area | Status |
|---|---|
| Article text | ✅ Complete |
| Diagrams | ✅ 6 SVGs created |
| Screenshots | ✅ Available in frontend/screenshots/ |
| Video | ✅ Recorded (34s, WebM) — needs upload |
| GitHub repo | ✅ Public at https://github.com/naveensri4518/CareerLift-AI |
| Live demo | ✅ https://3-235-53-227.nip.io |
| Evaluation numbers | ⚠️ Pending Bedrock quota + human sign-off |
| ss ship gate | ⚠️ 1 FAIL (measurement gate) |
| Submission deadline | 5 Nov 2026 1:29 PM IST |
