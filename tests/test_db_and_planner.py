"""SQLite persistence, interview generation, and the deterministic Learning Planner. No model, no AWS."""
import pytest

from agent import db, interview, planner


def test_interview_generation_valid_concepts():
    q = interview.generate_question(topic="hashing")
    assert q["expected_concepts"] == ["C-HASH-AVG"]
    assert q["topic"] == "hashing"
    # every bank question targets only real concept ids
    from agent import fairscore
    ids = fairscore.concept_ids()
    for item in interview.QUESTION_BANK:
        assert all(c in ids for c in item["concepts"]), item


def test_interview_generation_unknown_topic():
    with pytest.raises(ValueError):
        interview.generate_question(topic="does-not-exist")


def test_db_roundtrip(temp_db):
    iid = db.start_interview("stu-1", "sde", "beginner", "hashing")
    assert iid > 0
    plan = {"technical_band": "Partial", "communication_band": "Solid",
            "abstained_technical": False, "abstained_communication": False,
            "misconception_tags": ["M-HASH-ALWAYS-O1"]}
    db.record_answer(iid, "q?", ["C-HASH-AVG"], "ans", plan)
    db.bump_misconceptions("stu-1", [("M-HASH-ALWAYS-O1", "C-HASH-AVG")])
    db.bump_misconceptions("stu-1", [("M-HASH-ALWAYS-O1", "C-HASH-AVG")])
    tally = db.misconception_tally("stu-1")
    assert tally and tally[0]["tag"] == "M-HASH-ALWAYS-O1" and tally[0]["count"] == 2
    hist = db.interview_history("stu-1")
    assert len(hist) == 1 and hist[0]["technical_band"] == "Partial"


def test_planner_general_when_no_misconceptions(temp_db):
    db.ensure_student("stu-2")
    nx = planner.next_exercise("stu-2")
    assert "question" in nx and nx["question"]["expected_concepts"]
    assert "No recurring gaps" in nx["reason"]


def test_planner_targets_top_misconception(temp_db):
    db.ensure_student("stu-3")
    db.bump_misconceptions("stu-3", [("M-BINSEARCH-UNSORTED", "C-BINSEARCH")])
    db.bump_misconceptions("stu-3", [("M-BINSEARCH-UNSORTED", "C-BINSEARCH")])
    db.bump_misconceptions("stu-3", [("M-HASH-ALWAYS-O1", "C-HASH-AVG")])
    nx = planner.next_exercise("stu-3")
    assert nx["concept_id"] == "C-BINSEARCH"       # highest count
    assert nx["question"]["expected_concepts"] == ["C-BINSEARCH"]
