"""The baseline to beat: ONE agent, ONE prompt, the SAME model. It rates both axes DIRECTLY.

This is the naive grader FairScore must beat on the fairness gap without losing technical accuracy
(DESIGN.md section 12). It has no claim extraction, no verifier, no code-owned bands: the model emits
the bands itself. Same {"plan", "meta"} contract as agent/app.py so score.py reads it identically.
"""
from __future__ import annotations

import time

from pydantic import BaseModel

from strands import Agent

from . import tools
from .app import _model, structured_once_or_retry
from .models import Band, ScoreResult


class BaselineGrade(BaseModel):
    technical_band: Band
    communication_band: Band


SYSTEM = ("You grade a software-interview answer. Give two bands, each one of Weak, Partial, Solid, Strong:\n"
          "- technical_band: how correct and complete the technical content is.\n"
          "- communication_band: how clearly it is communicated.\n"
          "Return only the two bands.")


def run(case: dict) -> dict:
    t0 = time.time()
    answer = case["text"]
    lang = case.get("lang") or tools.language_of(answer)
    a = Agent(model=_model(), callback_handler=None, structured_output_model=BaselineGrade, system_prompt=SYSTEM)
    out = structured_once_or_retry(a, answer, max_calls=2)   # one call, retry once; no accidental double invocation
    if out is None:
        raise RuntimeError("baseline returned no structured grade")
    res = ScoreResult(technical_band=out.technical_band, communication_band=out.communication_band,
                      message=f"Technical: {out.technical_band}. Communication: {out.communication_band}.")
    return {"plan": res.model_dump(), "meta": {"path": "baseline", "lang": lang,
                                               "latency_ms": int((time.time() - t0) * 1000)}}
