"""Shared helpers. Read-only. CareerLift's curated source is agent/data/concepts.json (see fairscore.py)."""
import re

TAMIL = re.compile(r"[\u0B80-\u0BFF]")


def language_of(text):
    return "ta" if TAMIL.search(text or "") else "en"


def has_tamil(text):
    return bool(TAMIL.search(text or ""))
