"""Mastery state machine (PHASE_0_IMPLEMENTATION_SPEC §6.3). Pure, deterministic. No model/AWS."""
import random

from agent.skills import learner_model as lm


def _sig(i, outcome, key, created_at="2026-01-01T00:00:00"):
    return {"id": i, "outcome": outcome, "independent_key": key, "created_at": created_at}


def test_ladder_floors():
    # 3 distinct independent successes -> Proficient; 5 -> Strong
    sigs = [_sig(i, "mastered", f"k{i}") for i in range(1, 4)]
    assert lm.replay(sigs)["label"] == "Proficient"
    sigs = [_sig(i, "mastered", f"k{i}") for i in range(1, 6)]
    assert lm.replay(sigs)["label"] == "Strong"
    assert lm.replay([_sig(1, "mastered", "k1")])["label"] == "Emerging"
    assert lm.replay([_sig(1, "mastered", "k1"), _sig(2, "mastered", "k2")])["label"] == "Developing"


def test_duplicate_independent_key_does_not_advance():
    sigs = [_sig(1, "mastered", "same"), _sig(2, "mastered", "same"), _sig(3, "mastered", "same")]
    r = lm.replay(sigs)
    assert r["independent_success_count"] == 1
    assert r["label"] == "Emerging"            # only one real independent success


def test_partial_never_exceeds_emerging():
    r = lm.replay([_sig(1, "partial", "k1"), _sig(2, "partial", "k2")])
    assert r["label"] == "Emerging"


def test_mastery_reversal_misconception_caps_without_erasing():
    # reach Proficient, then a misconception caps to Developing (successes not erased)
    sigs = [_sig(i, "mastered", f"k{i}") for i in range(1, 4)]
    sigs.append(_sig(99, "misconception", "m"))
    r = lm.replay(sigs)
    assert r["open_misconception"] is True
    assert r["label"] == "Developing"
    assert r["independent_success_count"] == 3   # not erased


def test_misconception_open_resolve_reopen():
    sigs = [
        _sig(1, "misconception", "m1"),                      # open
        _sig(2, "mastered", "a"),                            # resolve streak 1
        _sig(3, "mastered", "b"),                            # resolve streak 2 -> RESOLVE_N -> resolved
        _sig(4, "misconception", "m2"),                      # reopen
    ]
    r = lm.replay(sigs)
    assert r["open_misconception"] is True                    # reopened
    kinds = [e[0] for e in r["events"]]
    assert kinds == ["misconception_opened", "misconception_resolved", "misconception_opened"]


def test_intervening_partial_resets_resolve_streak():
    sigs = [
        _sig(1, "misconception", "m1"),
        _sig(2, "mastered", "a"),       # streak 1
        _sig(3, "partial", "p"),        # reset streak
        _sig(4, "mastered", "b"),       # streak 1 again (not 2) -> NOT resolved
    ]
    r = lm.replay(sigs)
    assert r["open_misconception"] is True
    assert [e[0] for e in r["events"]] == ["misconception_opened"]   # never resolved


def test_two_misconceptions_while_open_record_two_events():
    sigs = [_sig(1, "misconception", "m1"), _sig(2, "misconception", "m2")]
    r = lm.replay(sigs)
    opened = [e for e in r["events"] if e[0] == "misconception_opened"]
    assert len(opened) == 2
    assert {e[1] for e in opened} == {1, 2}      # keyed by distinct signal ids


def test_equal_timestamps_deterministic_and_rebuild_equivalence():
    base = [_sig(i, "mastered", f"k{i}", created_at="2026-01-01T00:00:00") for i in range(1, 4)]
    base.append(_sig(4, "misconception", "m", created_at="2026-01-01T00:00:00"))
    # the replay function consumes rows in given order; the DB layer sorts by (created_at, id).
    # Simulate that ordering guarantee: sorting by id must give a stable result regardless of shuffle.
    for _ in range(5):
        shuffled = base[:]
        random.shuffle(shuffled)
        ordered = sorted(shuffled, key=lambda s: (s["created_at"], s["id"]))
        assert lm.replay(ordered)["label"] == "Developing"
