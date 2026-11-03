"""CareerLift AI — Phase 1: Advanced Interview Studio (session logic + evaluation provider abstraction).

Deterministic, local, mock-mode only here. This module does NOT reimplement scoring: it WRAPS the existing
FairScore pipeline (agent.app.run) per answer and aggregates results into a session evaluation. It adds
multi-question sessions, categories, and a clean provider seam so a real AI provider can slot in later.

FairScore philosophy preserved:
  - technical correctness and communication clarity stay SEPARATE (two bands, never blended);
  - simple English / grammar / accent / length never lower the technical read;
  - bands come from agent/fairscore.py (code-owned), never invented here.

Honesty: in mock mode every evaluation is tagged mockmodel.MOCK_LABEL — never presented as live AI.
"""
from __future__ import annotations

import random

from . import config, fairscore, interview, mockmodel

# ---- Categories ----
CATEGORIES = ["technical", "hr", "behavioral", "project", "mixed"]
DIFFICULTIES = ["beginner", "intermediate", "advanced"]

# Technical questions reuse the existing concept-bound bank (so FairScore + Phase 0 signals apply).
# Non-technical questions carry NO expected_concepts: they are scored on the communication axis only,
# which is exactly how FairScore treats answers with nothing to verify technically.
_HR_QUESTIONS = [
    "Tell me about yourself and what draws you to this role.",
    "Why do you want to work here, and what are you looking for in your next team?",
    "Describe a time you received difficult feedback. How did you respond?",
    "Where do you see your skills growing over the next year?",
    "What does a good work environment look like for you?",
]
_BEHAVIORAL_QUESTIONS = [
    "Describe a challenging problem you solved. What was your approach? (Situation, Task, Action, Result)",
    "Tell me about a time you disagreed with a teammate. How did you resolve it?",
    "Describe a time you failed or missed a deadline. What did you learn?",
    "Tell me about a time you had to learn something quickly to finish a task.",
    "Describe a time you took initiative without being asked.",
]
_PROJECT_QUESTIONS = [
    "Walk me through a project you are proud of. What problem did it solve?",
    "In your project, what was the hardest technical decision and how did you make it?",
    "How did you test and validate your project's correctness?",
    "If you rebuilt that project today, what would you change and why?",
    "How did you divide work and track progress in your project?",
]


def _technical_pool() -> list[dict]:
    """Reuse the existing concept-bound question bank."""
    return [
        {"category": "technical", "text": q["text"], "topic": q["topic"],
         "expected_concepts": list(q["concepts"])}
        for q in interview.QUESTION_BANK
    ]


def _nontech_pool(category: str, questions: list[str]) -> list[dict]:
    return [{"category": category, "text": t, "topic": category, "expected_concepts": []} for t in questions]


def _pool_for(category: str) -> list[dict]:
    if category == "technical":
        return _technical_pool()
    if category == "hr":
        return _nontech_pool("hr", _HR_QUESTIONS)
    if category == "behavioral":
        return _nontech_pool("behavioral", _BEHAVIORAL_QUESTIONS)
    if category == "project":
        return _nontech_pool("project", _PROJECT_QUESTIONS)
    if category == "mixed":
        pool = _technical_pool() + _nontech_pool("hr", _HR_QUESTIONS) \
            + _nontech_pool("behavioral", _BEHAVIORAL_QUESTIONS) + _nontech_pool("project", _PROJECT_QUESTIONS)
        return pool
    raise ValueError(f"unknown category {category!r}; choose one of {CATEGORIES}")


def build_question_set(category: str, count: int, topics: list[str] | None = None,
                       seed: int | None = None) -> list[dict]:
    """Deterministically (given seed) select `count` questions for a session. For technical/mixed, an
    optional `topics` filter narrows the technical questions. Returns dicts with ordinal assigned."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}; choose one of {CATEGORIES}")
    count = max(1, min(int(count), 20))
    pool = _pool_for(category)
    if topics:
        tset = set(topics)
        filtered = [q for q in pool if q["category"] != "technical" or q["topic"] in tset]
        pool = filtered or pool  # if the filter removes everything, fall back to the full pool
    rng = random.Random(seed if seed is not None else 0)
    chosen = pool[:] if len(pool) <= count else rng.sample(pool, count)
    # If asked for more than the pool holds, cycle deterministically to reach `count`.
    while len(chosen) < count:
        chosen.append(pool[len(chosen) % len(pool)])
    out = []
    for i, q in enumerate(chosen[:count]):
        out.append({"ordinal": i, "category": q["category"], "topic": q["topic"],
                    "text": q["text"], "expected_concepts": q["expected_concepts"]})
    return out


# ---------------------------------------------------------------------------
# Evaluation provider abstraction (mock now; real provider later)
# ---------------------------------------------------------------------------

class EvaluationProvider:
    """Interface for per-answer evaluation. Implementations MUST keep technical and communication
    separate and must never let prose style lower the technical read."""

    name = "base"
    is_mock = True

    def evaluate_answer(self, answer_text: str, expected_concepts: list[str]) -> dict:
        raise NotImplementedError


class FairScoreProvider(EvaluationProvider):
    """Wraps the existing FairScore pipeline (agent.app.run). Works in whatever model mode is configured:
    in mock mode it is deterministic and offline; a future real provider is the SAME pipeline with
    CAREERLIFT_MODEL_MODE=bedrock. No scoring logic is duplicated here."""

    name = "fairscore"

    def __init__(self):
        self.is_mock = config.is_mock()

    def evaluate_answer(self, answer_text: str, expected_concepts: list[str]) -> dict:
        # Import here so importing this module never triggers the agent/model import chain unnecessarily.
        from .app import run as fairscore_run
        out = fairscore_run({"text": answer_text, "expected_concepts": expected_concepts or []})
        plan, meta = out["plan"], out.get("meta", {})
        return {
            "technical_band": plan.get("technical_band"),
            "communication_band": plan.get("communication_band"),
            "abstained_technical": bool(plan.get("abstained_technical")),
            "abstained_communication": bool(plan.get("abstained_communication")),
            "technical_evidence": plan.get("technical_evidence", []),
            "communication_evidence": plan.get("communication_evidence", []),
            "misconception_tags": plan.get("misconception_tags", []),
            "message": plan.get("message", ""),
            "mock": meta.get("mock", config.is_mock()),
            "mock_label": meta.get("mock_label", mockmodel.MOCK_LABEL),
        }


def get_provider() -> EvaluationProvider:
    """Factory. Today: the FairScore provider (mock or bedrock per config). A future provider can be
    selected here without touching callers."""
    return FairScoreProvider()


# ---------------------------------------------------------------------------
# Session aggregation (deterministic; builds the detailed evaluation from per-answer bands)
# ---------------------------------------------------------------------------

_BAND_ORD = {"Weak": 0, "Partial": 1, "Solid": 2, "Strong": 3}
_BAND_NAMES = ["Weak", "Partial", "Solid", "Strong"]


def _avg_band(bands: list[str]) -> str | None:
    vals = [_BAND_ORD[b] for b in bands if b in _BAND_ORD]
    if not vals:
        return None
    return _BAND_NAMES[round(sum(vals) / len(vals))]


def summarize_session(category: str, graded: list[dict]) -> dict:
    """Aggregate per-answer evaluations into a session-level detailed evaluation.

    `graded` items: {ordinal, category, topic, expected_concepts, answer_text, eval(dict from provider)}.
    Returns separate technical + communication summaries, strengths/weaknesses, suggestions,
    recommended practice topics, and a sample-answer pointer. All real/derived — no invented numbers.
    """
    tech_bands, comm_bands = [], []
    strengths, weaknesses, misconception_tags = [], [], []
    answered = 0
    tech_assessed = 0

    for g in graded:
        ev = g["eval"]
        if (g.get("answer_text") or "").strip():
            answered += 1
        tb, cb = ev.get("technical_band"), ev.get("communication_band")
        if tb and not ev.get("abstained_technical"):
            tech_bands.append(tb)
            tech_assessed += 1
        if cb and not ev.get("abstained_communication"):
            comm_bands.append(cb)
        misconception_tags += ev.get("misconception_tags", [])
        # strengths/weaknesses derived from real bands
        if tb in ("Solid", "Strong"):
            strengths.append(f"Strong technical answer on {g.get('topic')}")
        if cb in ("Solid", "Strong"):
            strengths.append("Clear, well-structured communication")
        if tb == "Weak":
            weaknesses.append(f"Technical gap on {g.get('topic')}")
        if cb == "Weak":
            weaknesses.append("Communication could be clearer or better organised")

    overall_tech = _avg_band(tech_bands)
    overall_comm = _avg_band(comm_bands)

    # Recommended practice: topics of weak/misconception technical answers + concepts behind misconceptions
    rec_topics = sorted({g.get("topic") for g in graded
                         if g["eval"].get("technical_band") == "Weak"
                         or g["eval"].get("misconception_tags")})
    suggestions = []
    if overall_comm in ("Weak", "Partial"):
        suggestions.append("Use a clear structure (point, reason, example) and check you answered the question asked.")
    if overall_tech in ("Weak", "Partial"):
        suggestions.append("Revisit the weak topics below and practise explaining the core idea in your own words.")
    if not suggestions:
        suggestions.append("Keep practising mixed questions to maintain and deepen your strengths.")

    return {
        "category": category,
        "questions_total": len(graded),
        "questions_answered": answered,
        "technical_assessed": tech_assessed,
        "overall_technical_band": overall_tech,
        "overall_communication_band": overall_comm,
        "dimensions": {
            # FairScore keeps these two independent; the sub-dimensions reflect the communication observations
            "technical_correctness": overall_tech,
            "communication_clarity": overall_comm,
        },
        "strengths": sorted(set(strengths))[:6],
        "weaknesses": sorted(set(weaknesses))[:6],
        "suggestions": suggestions,
        "misconception_tags": sorted(set(misconception_tags)),
        "recommended_practice_topics": [t for t in rec_topics if t],
    }


def sample_answer_for(topic: str) -> str | None:
    """A concise, curated 'better sample answer' for a technical topic, built from the concept reference
    key points. Returns None for non-technical categories (no canonical answer). Not model-generated."""
    cmap = {q["topic"]: q["concepts"] for q in interview.QUESTION_BANK}
    concepts = cmap.get(topic)
    if not concepts:
        return None
    parts = []
    by_id = fairscore.concept_by_id()
    for cid in concepts:
        c = by_id.get(cid, {})
        kps = c.get("key_points", [])
        if kps:
            parts.append(f"{c.get('canonical_name', cid)}: " + "; ".join(kps) + ".")
    return " ".join(parts) or None
