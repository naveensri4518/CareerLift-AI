"""Phase 3 — deterministic assessment grading + analytics. NO model / AWS.

Grading rules (transparent, exact):
  single : full marks iff the one selected option equals the one correct option, else 0.
  multi  : full marks iff the selected set EXACTLY equals the correct set (no missing, no extra), else 0.
  tf     : full marks iff the selected boolean equals the correct boolean, else 0.
  unanswered: 0 marks, counted separately (not "incorrect").

All analytics (per-category, per-difficulty, accuracy, grade) are computed from the actual graded
questions only — nothing is fabricated.
"""
from __future__ import annotations

from . import assessment_bank


def _answer_is_correct(question: dict, answer: dict | None) -> bool:
    """answer shape (client, validated upstream):
         single/multi -> {"selected": ["a","c", ...]}
         tf           -> {"bool": true|false}
       None / empty selection => unanswered => not correct.
    """
    if not answer:
        return False
    qtype = question["type"]
    if qtype == "tf":
        if "bool" not in answer or answer["bool"] is None:
            return False
        return bool(answer["bool"]) == bool(question["correct_bool"])
    selected = answer.get("selected")
    if not selected:
        return False
    sel = set(selected)
    correct = set(question["correct_options"])
    if qtype == "single":
        # exactly one selection, equal to the single correct option
        return len(sel) == 1 and sel == correct
    # multi: EXACT set match — partial or extra selections score zero
    return sel == correct


def _is_answered(question: dict, answer: dict | None) -> bool:
    if not answer:
        return False
    if question["type"] == "tf":
        return answer.get("bool") is not None
    return bool(answer.get("selected"))


def grade_attempt(question_ids: list[str], answers: dict[str, dict]) -> dict:
    """Grade an attempt deterministically.

    question_ids : ordered ids that make up this attempt (server-owned).
    answers       : {question_id: answer_dict} (may omit unanswered questions).
    Returns a result payload with totals, per-category and per-difficulty breakdowns, and a per-question
    correctness map (no answer keys — the router adds review projections separately).
    """
    total_score = 0
    max_score = 0
    correct = incorrect = unanswered = 0
    by_category: dict[str, dict] = {}
    by_difficulty: dict[str, dict] = {}
    per_question: dict[str, dict] = {}

    for qid in question_ids:
        q = assessment_bank.get_question(qid)
        if q is None:
            continue  # defensive: skip ids no longer in the bank
        marks = assessment_bank.marks_for(q)
        max_score += marks
        cat = q["category"]
        diff = q["difficulty"]
        by_category.setdefault(cat, {"correct": 0, "total": 0, "score": 0, "max": 0})
        by_difficulty.setdefault(diff, {"correct": 0, "total": 0, "score": 0, "max": 0})
        by_category[cat]["total"] += 1
        by_category[cat]["max"] += marks
        by_difficulty[diff]["total"] += 1
        by_difficulty[diff]["max"] += marks

        ans = answers.get(qid)
        answered = _is_answered(q, ans)
        is_correct = _answer_is_correct(q, ans) if answered else False

        if not answered:
            unanswered += 1
            status = "unanswered"
        elif is_correct:
            correct += 1
            total_score += marks
            by_category[cat]["correct"] += 1
            by_category[cat]["score"] += marks
            by_difficulty[diff]["correct"] += 1
            by_difficulty[diff]["score"] += marks
            status = "correct"
        else:
            incorrect += 1
            status = "incorrect"

        per_question[qid] = {"status": status, "awarded": marks if is_correct else 0, "marks": marks}

    answered_count = correct + incorrect
    total_q = len(question_ids)
    percentage = round((total_score / max_score) * 100, 1) if max_score else 0.0
    accuracy = round((correct / answered_count) * 100, 1) if answered_count else 0.0

    return {
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "total_questions": total_q,
        "correct": correct,
        "incorrect": incorrect,
        "unanswered": unanswered,
        "accuracy": accuracy,
        "grade": grade_for(percentage),
        "by_category": by_category,
        "by_difficulty": by_difficulty,
        "per_question": per_question,
    }


def grade_for(percentage: float) -> str:
    """Transparent letter grade bands from the real percentage."""
    if percentage >= 90:
        return "A"
    if percentage >= 75:
        return "B"
    if percentage >= 60:
        return "C"
    if percentage >= 40:
        return "D"
    return "F"


def strengths_and_weaknesses(by_category: dict) -> dict:
    """Derive strength/weak areas from REAL per-category accuracy. A category needs >=1 question to count.
    Strong: >=75% of marks. Weak: <50% of marks. Everything else is 'developing'."""
    strengths, weaknesses = [], []
    for cat, d in by_category.items():
        if d["max"] <= 0:
            continue
        pct = (d["score"] / d["max"]) * 100
        if pct >= 75:
            strengths.append({"category": cat, "percentage": round(pct, 1)})
        elif pct < 50:
            weaknesses.append({"category": cat, "percentage": round(pct, 1)})
    strengths.sort(key=lambda x: x["percentage"], reverse=True)
    weaknesses.sort(key=lambda x: x["percentage"])
    return {"strengths": strengths, "weaknesses": weaknesses}
