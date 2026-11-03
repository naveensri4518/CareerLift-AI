"""SkillSignal emission + dedup + precedence (PHASE_0_IMPLEMENTATION_SPEC §6.1, §6.2). No model/AWS."""
from agent import db
from agent.skills import signals


def _answer(answer_id, tags, expected, concept_status=None, created_at="2026-01-01T00:00:00"):
    return {
        "id": answer_id,
        "student_id": "stu_test",
        "misconception_tags": tags,
        "expected_concepts": expected,
        "concept_status": concept_status or {},
        "created_at": created_at,
    }


def test_band_only_answer_produces_no_mastery_signal():
    # No per-concept evidence, no misconception tags -> NO signals at all (band alone is not mastery).
    sigs = signals.signals_from_answer(_answer(1, [], ["C-HASH-AVG", "C-BINSEARCH"]))
    assert sigs == []


def test_misconception_tag_produces_misconception_signal():
    sigs = signals.signals_from_answer(_answer(2, ["M-HASH-ALWAYS-O1"], ["C-HASH-AVG"]))
    assert len(sigs) == 1
    assert sigs[0]["concept_id"] == "C-HASH-AVG" and sigs[0]["outcome"] == "misconception"


def test_multiple_concepts_one_answer_independent_signals():
    sigs = signals.signals_from_answer(_answer(
        3, [], ["C-HASH-AVG", "C-BINSEARCH"],
        concept_status={"C-HASH-AVG": "supported", "C-BINSEARCH": "partial"}))
    by = {s["concept_id"]: s for s in sigs}
    assert by["C-HASH-AVG"]["outcome"] == "mastered"
    assert by["C-BINSEARCH"]["outcome"] == "partial"
    assert by["C-HASH-AVG"]["dedup_key"] != by["C-BINSEARCH"]["dedup_key"]
    assert by["C-HASH-AVG"]["independent_key"].endswith(":C-HASH-AVG")


def test_same_evidence_precedence_misconception_blocks_positive():
    # one answer: supported AND a misconception for the SAME concept -> only the misconception counts
    sigs = signals.signals_from_answer(_answer(
        4, ["M-HASH-ALWAYS-O1"], ["C-HASH-AVG"],
        concept_status={"C-HASH-AVG": "supported"}))
    outcomes = {s["outcome"] for s in sigs}
    assert outcomes == {"misconception"}
    assert all(not (s["outcome"] in ("mastered", "partial")) for s in sigs)


def test_dedup_idempotent_insert(temp_db):
    db.ensure_student("stu_test")
    sigs = signals.signals_from_answer(_answer(5, ["M-HASH-ALWAYS-O1"], ["C-HASH-AVG"]))
    sig = sigs[0]
    first = db.insert_skill_signal(sig)
    second = db.insert_skill_signal(sig)      # same dedup_key
    assert first is not None and second is None
    rows = db.signals_for_concept("stu_test", "C-HASH-AVG")
    assert len(rows) == 1


def test_unknown_concept_tag_is_ignored():
    # a tag whose concept isn't in the taxonomy produces no signal (fail-closed)
    sigs = signals.signals_from_answer(_answer(6, ["M-DOES-NOT-EXIST"], ["C-HASH-AVG"]))
    assert sigs == []
