"""Diagnostic: measure mock-mode FairScore behaviour across the 8 answer types the user reported.

NOT a test and NOT part of the product. It prints the real pipeline output so we can see exactly when
technical correctness comes back as 'Not assessed' and why. Run from repo root:

    CAREERLIFT_MODEL_MODE=mock python -m scripts.diag_studio
"""
from __future__ import annotations

import os

os.environ.setdefault("CAREERLIFT_MODEL_MODE", "mock")

from agent import fairscore
from agent.app import run
from agent.mockmodel import extract_claims

# Hashing question: expected concept C-HASH-AVG (average O(1), worst O(n)).
CID = ["C-HASH-AVG"]

CASES = {
    "1 correct (textbook vocab)":
        "A hash table lookup is O(1) on average with a good hash function and a sensible load factor, "
        "but the worst case is O(n) when many keys collide into the same bucket.",
    "2 incorrect (grounded misconception)":
        "A hash map is always O(1), it is never O(n) no matter what.",
    "3 partial":
        "A hash map is usually O(1) for lookups.",
    "4 empty":
        "",
    "5 very short":
        "O(1).",
    "6 correct in PLAIN English (no jargon)":
        "When I store things by a key, looking one up is basically instant most of the time, but if lots "
        "of them land in the same spot it slows down and has to walk through all of them.",
    "7 correct in ADVANCED English (fancy words, right idea)":
        "Amortised constant-time retrieval is the expected behaviour provided the hashing distribution is "
        "uniform and the load factor is bounded; pathological collision clustering degrades this to linear.",
    "8 misconception-style wrong (plain)":
        "Hash maps are always constant time, so you never have to worry about it being slow.",
}


def main() -> int:
    print(f"model_mode = {fairscore.__name__ and os.environ['CAREERLIFT_MODEL_MODE']}\n")
    for label, ans in CASES.items():
        claims = extract_claims(ans, CID)
        v = fairscore.verify_claims([c.model_dump() for c in claims.claims], CID, ans)
        out = run({"text": ans, "expected_concepts": CID})
        p = out["plan"]
        raw = [(c.concept_id, c.status, (c.evidence_span or "")[:40]) for c in claims.claims]
        print(f"=== {label}")
        print(f"    mock claims      : {raw}")
        print(f"    coverage={v['coverage']:.2f} abstain={v['abstain']} best={v['best_status']}")
        print(f"    technical_band   : {p['technical_band']}  (abstained={p['abstained_technical']})")
        print(f"    communication    : {p['communication_band']}  (abstained={p['abstained_communication']})")
        print(f"    misconceptions   : {p['misconception_tags']}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
