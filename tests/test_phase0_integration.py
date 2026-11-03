"""Phase 0 end-to-end over the real DB layer: emission -> mastery -> activity -> recommend -> backfill.
No model/AWS."""
from agent import activity, db
from agent.skills import backfill, learner_model, recommend, signals


def _seed_answer(student_id, interview_id, tags, expected, concept_status=None):
    """Create an answer row and return the dict shape signals expect."""
    return {
        "id": interview_id, "student_id": student_id,
        "misconception_tags": tags, "expected_concepts": expected,
        "concept_status": concept_status or {}, "created_at": "2026-01-01T00:00:00",
    }


def test_emit_updates_mastery_and_activity(temp_db):
    db.ensure_student("s1")
    # grounded incorrect -> misconception signal -> open misconception + opened event
    ans = _seed_answer("s1", 1, ["M-HASH-ALWAYS-O1"], ["C-HASH-AVG"])
    signals.emit_from_answer("s1", ans)
    activity.record_interview_scored("s1", 1)

    concepts = {c["concept_id"]: c for c in db.learner_concepts_for_student("s1")}
    assert concepts["C-HASH-AVG"]["open_misconception"] is True
    assert concepts["C-HASH-AVG"]["label"] in ("Developing", "Not enough evidence", "Emerging")

    events = db.activity_events_for_student("s1")
    kinds = sorted(e["kind"] for e in events)
    assert "interview_scored" in kinds
    assert "misconception_opened" in kinds


def test_activity_interview_scored_idempotent(temp_db):
    db.ensure_student("s2")
    assert activity.record_interview_scored("s2", 7) is True
    assert activity.record_interview_scored("s2", 7) is False   # duplicate no-op
    events = [e for e in db.activity_events_for_student("s2") if e["kind"] == "interview_scored"]
    assert len(events) == 1


def test_recommendations_empty_without_evidence(temp_db):
    db.ensure_student("s3")
    assert recommend.rank("s3") == []
    assert recommend.top("s3") is None


def test_recommendations_prioritise_misconception(temp_db):
    db.ensure_student("s4")
    signals.emit_from_answer("s4", _seed_answer("s4", 1, ["M-HASH-ALWAYS-O1"], ["C-HASH-AVG"]))
    # misconception tally also drives recommend's count; bump it as the /score flow would
    db.bump_misconceptions("s4", [("M-HASH-ALWAYS-O1", "C-HASH-AVG")])
    recs = recommend.rank("s4")
    assert recs and recs[0]["priority"] == "misconception"
    assert recs[0]["reason"]                         # non-empty explanation
    assert "misconception_count" in recs[0]["evidence_summary"]


def test_update_equals_rebuild(temp_db):
    db.ensure_student("s5")
    # a sequence producing an open->resolve->reopen lifecycle across answers
    db.insert_skill_signal(_raw("s5", "C-HASH-AVG", "misconception", "iv:answer:1:C-HASH-AVG", 1))
    db.insert_skill_signal(_raw("s5", "C-HASH-AVG", "mastered", "iv:answer:2:C-HASH-AVG", 2))
    db.insert_skill_signal(_raw("s5", "C-HASH-AVG", "mastered", "iv:answer:3:C-HASH-AVG", 3))
    db.insert_skill_signal(_raw("s5", "C-HASH-AVG", "misconception", "iv:answer:4:C-HASH-AVG", 4))
    # incremental updates
    for _ in range(3):
        learner_model.update("s5", "C-HASH-AVG")
    inc = {c["concept_id"]: c for c in db.learner_concepts_for_student("s5")}["C-HASH-AVG"]
    # full rebuild
    learner_model.rebuild("s5")
    reb = {c["concept_id"]: c for c in db.learner_concepts_for_student("s5")}["C-HASH-AVG"]
    assert inc == reb


def test_backfill_idempotent(temp_db):
    # seed a real student + interview + answer via the DB layer, then backfill twice
    db.ensure_student("s6")
    iid = db.start_interview("s6", "sde", "beginner", "hashing",
                             question="q", expected_concepts=["C-HASH-AVG"])
    db.record_answer(iid, "q", ["C-HASH-AVG"], "ans",
                     {"technical_band": "Solid", "communication_band": "Solid",
                      "misconception_tags": ["M-HASH-ALWAYS-O1"]})
    r1 = backfill.backfill_student("s6")
    r2 = backfill.backfill_student("s6")
    assert r1["signals_created"] >= 1
    assert r2["signals_created"] == 0            # idempotent second run
    rows = db.signals_for_concept("s6", "C-HASH-AVG")
    assert len(rows) == 1


def _raw(student_id, concept_id, outcome, independent_key, sid):
    import hashlib
    dedup = hashlib.sha256(f"{student_id}|interview|answer:{sid}|{concept_id}|{outcome}".encode()).hexdigest()
    return {"student_id": student_id, "concept_id": concept_id, "source_module": "interview",
            "outcome": outcome, "strength": "strong" if outcome == "misconception" else "medium",
            "confidence": 0.0, "evidence_ref": f"answer:{sid}",
            "independent_key": independent_key, "dedup_key": dedup,
            "created_at": f"2026-01-0{sid}T00:00:00"}
