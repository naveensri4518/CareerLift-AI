"""Technical Evaluator agent: extracts technical claims. NO score, NO prose judgement.

The band is computed later by fairscore.band_from_claims(). This agent is instructed to judge the
TECHNICAL CONTENT only and to ignore the English register entirely (DESIGN.md sections 3, 6).
"""
from __future__ import annotations

from strands import Agent

from . import fairscore
from .models import TechnicalClaims


def _concept_menu(expected_concepts: list[str]) -> str:
    cmap = {c["id"]: c for c in fairscore.concepts()["concepts"]}
    lines = []
    for cid in expected_concepts:
        c = cmap.get(cid)
        if c:
            lines.append(f"- {cid}: {c['canonical_name']}")
    return "\n".join(lines)


SYSTEM = """You extract the TECHNICAL claims an interview answer makes. You DO NOT give any score or band.

Rules:
1. For EACH expected concept listed in the task, decide the answer's status:
   - supported: the answer clearly and correctly addresses this concept;
   - partial:   the answer touches it but is incomplete, vague, or partly wrong;
   - absent:    the answer does not address it.
2. Judge the TECHNICAL CONTENT ONLY. IGNORE the English completely: simple words, grammar mistakes,
   accent, spelling and short length must NEVER lower a status. A correct idea in plain English is 'supported'.
3. Use ONLY the expected concept_ids given in the task. Never invent a concept_id.
4. For every 'supported' or 'partial' claim, copy a short evidence_span VERBATIM from the student's answer.
   If you cannot quote the answer, the status is 'absent'.
5. Return one claim per expected concept. No commentary."""


def agent(model, expected_concepts: list[str]) -> Agent:
    menu = _concept_menu(expected_concepts)
    return Agent(model=model, name="evaluate", callback_handler=None,
                 structured_output_model=TechnicalClaims,
                 system_prompt=SYSTEM + "\n\nExpected concepts for THIS question:\n" + menu)
