"""CareerLift AI — LOCAL MOCK MODEL (no Bedrock, no AWS, no network).

Purpose: exercise the ENTIRE interview + FairScore workflow offline. The mock plays ONLY the model's
role — it extracts technical claims and communication observations from the student's answer. It NEVER
computes a band or a score: the existing deterministic logic in agent/fairscore.py does that, unchanged.

This is deterministic text analysis, not a hardcoded result:
  - claims are derived by matching the answer against the curated concept reference (aliases / key points
    from agent/data/concepts.json) and the misconception 'signature' phrases;
  - evidence spans are REAL substrings copied from the student's answer, so fairscore's grounding check
    passes exactly as it would for the real model;
  - observations are derived from simple structural signals of the answer text.

Selected only when CAREERLIFT_MODEL_MODE=mock. The real Bedrock path is untouched and still the default.
"""
from __future__ import annotations

import re

from . import fairscore
from .models import Claim, CommObservations, TechnicalClaims

# Public marker so the API/UI can label results as a local demo (never passed off as a real AI eval).
MOCK_LABEL = "LOCAL DEMO / MOCK EVALUATION"

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9()+]+")


class _Result:
    """Mimics the shape the code reads from a Strands agent call: result.structured_output."""

    def __init__(self, structured_output):
        self.structured_output = structured_output


def _sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]
    return parts or ([text.strip()] if text and text.strip() else [])


def _find_span_for_terms(answer: str, terms: set[str]) -> str | None:
    """Return the first sentence of the answer that mentions any of the given terms (verbatim substring)."""
    low_terms = {t.lower() for t in terms if len(t) > 2}
    for sent in _sentences(answer):
        low = sent.lower()
        if any(t in low for t in low_terms):
            return sent
    return None


def _concept_terms(concept_id: str) -> set[str]:
    c = fairscore.concept_by_id().get(concept_id, {})
    terms: set[str] = set()
    for alias in c.get("aliases", []):
        terms.add(alias.lower())
        terms |= {w for w in _WORD.findall(alias.lower()) if len(w) > 2}
    for kp in c.get("key_points", []):
        terms |= {w for w in _WORD.findall(kp.lower()) if len(w) > 2}
    stop = {"the", "and", "all", "are", "can", "use", "uses", "with", "over", "each", "once", "lower",
            "upper", "across", "value", "values", "time", "space", "where", "than", "that", "they", "its"}
    return {t for t in terms if t not in stop}


def _concept_cues(concept_id: str) -> list[str]:
    """Curated PLAIN-LANGUAGE phrases that show the concept was ADDRESSED without textbook vocabulary.

    Language fairness (DESIGN.md sections 2 & 7): a correct answer in plain English must be recognised,
    not silently dropped to 'absent' just because it avoided jargon. A cue match means 'touched this
    concept', never 'answered it correctly' — the caller caps a cue-only match at 'partial'.
    """
    c = fairscore.concept_by_id().get(concept_id, {})
    return [cue.lower() for cue in c.get("cues", []) if cue and cue.strip()]


def _find_span_for_cues(answer: str, cues: list[str]) -> str | None:
    """Return the first sentence of the answer that contains a curated cue phrase (verbatim substring)."""
    for sent in _sentences(answer):
        low = sent.lower()
        if any(cue in low for cue in cues):
            return sent
    return None


def _incorrect_signature_hit(concept_id: str, answer: str) -> str | None:
    """If the answer verbatim contains a misconception signature phrase for this concept, return the
    grounded sentence that contains it (so fairscore can match + ground it)."""
    low = answer.lower()
    for m in fairscore.concepts().get("misconceptions", []):
        if m.get("about") != concept_id:
            continue
        for sig in m.get("signature", []):
            sig_l = sig.lower()
            if sig_l in low:
                # return the real sentence containing the signature, as the grounded evidence span
                for sent in _sentences(answer):
                    if sig_l in sent.lower():
                        return sent
                return answer.strip()
    return None


def extract_claims(answer: str, expected_concepts: list[str]) -> TechnicalClaims:
    """Deterministically decide, per expected concept, whether the answer supports / partially addresses /
    contradicts / omits it. Evidence spans are real quotes from the answer."""
    claims: list[Claim] = []
    for cid in expected_concepts:
        # 1) explicit WRONG assertion wins (grounded signature phrase)
        bad_span = _incorrect_signature_hit(cid, answer)
        if bad_span:
            claims.append(Claim(concept_id=cid, status="incorrect", evidence_span=bad_span))
            continue
        # 2) does the answer mention the concept's textbook vocabulary?
        terms = _concept_terms(cid)
        span = _find_span_for_terms(answer, terms)
        if span:
            # supported vs partial: a fuller sentence (more matching terms) reads as supported
            hits = sum(1 for t in terms if t in span.lower())
            status = "supported" if hits >= 2 else "partial"
            claims.append(Claim(concept_id=cid, status=status, evidence_span=span))
            continue
        # 3) LANGUAGE-FAIR fallback: a correct answer in plain English may use none of the curated
        #    vocabulary. Curated cue phrases recognise that the concept was ADDRESSED. A cue match is
        #    capped at 'partial' — it shows the student engaged the concept, NOT that it is correct
        #    (correctness is only ever established against human labels offline; DESIGN.md section 6).
        cue_span = _find_span_for_cues(answer, _concept_cues(cid))
        if cue_span:
            claims.append(Claim(concept_id=cid, status="partial", evidence_span=cue_span))
            continue
        # 4) nothing recognised -> genuinely absent (missing knowledge). Empty/short answers land here.
        claims.append(Claim(concept_id=cid, status="absent", evidence_span=""))
    return TechnicalClaims(claims=claims)


def observe(answer: str) -> CommObservations:
    """Deterministic communication observations from structural signals ONLY.
    Never judges grammar, vocabulary, accent, or length-as-penalty (DESIGN.md section 7)."""
    sents = _sentences(answer)
    words = _WORD.findall((answer or "").lower())
    n_words = len(words)

    # clarity: is there any substantive content at all? very short/empty -> partial/absent
    if n_words == 0:
        clarity = "absent"
    elif n_words < 4:
        clarity = "partial"
    else:
        clarity = "present"

    # structure: more than one sentence, or a connective, suggests ordered reasoning
    connectives = ("because", "so", "then", "first", "second", "therefore", "but", "however", "while", "if")
    has_connective = any(c in (answer or "").lower() for c in connectives)
    structure = "present" if (len(sents) >= 2 or has_connective) else ("partial" if n_words >= 4 else "absent")

    # relevance: assume on-topic if there is real content (topic match is judged on the technical axis);
    # a near-empty answer is not relevant.
    relevance = "present" if n_words >= 4 else ("partial" if n_words >= 1 else "absent")

    # organisation: multi-sentence answers read as organised; single short ones partial
    organisation = "present" if len(sents) >= 2 else ("partial" if n_words >= 4 else "absent")

    # evidence: quote the first one or two real sentences (verbatim), so grounding passes
    evidence = sents[:2]

    note = "Local demo observation derived from answer structure (not grammar or vocabulary)."
    return CommObservations(
        clarity=clarity, structure=structure, relevance=relevance, organisation=organisation,
        evidence=evidence, notes=note,
    )


# ---- Mock "agents" that stand in for Strands agents (same call shape: agent(message).structured_output) ----

class MockEvaluatorAgent:
    """Stands in for evaluate.agent(model, expected_concepts). The answer is parsed from the task message."""

    def __init__(self, expected_concepts: list[str]):
        self.expected_concepts = list(expected_concepts)

    def __call__(self, message: str) -> _Result:
        answer = _answer_from_task(message)
        return _Result(extract_claims(answer, self.expected_concepts))

    # Strands agents expose .name; some code reads it. Provide a harmless attribute.
    name = "evaluate"


class MockCoachAgent:
    """Stands in for coach.agent(model). It is called directly with the answer text."""

    name = "coach"

    def __call__(self, message: str) -> _Result:
        return _Result(observe(message))


# The Technical Evaluator is run inside a Strands GraphBuilder in app.py, which needs a real Strands
# node. In mock mode we bypass the graph entirely (see app.py), so these agents are called directly.

_TASK_ANSWER_RE = re.compile(r'"""\s*(.*?)\s*"""', re.S)


def _answer_from_task(message: str) -> str:
    """Recover the student's answer from the evaluator task string built in app._task()."""
    m = _TASK_ANSWER_RE.search(message or "")
    if m:
        return m.group(1).strip()
    return (message or "").strip()
