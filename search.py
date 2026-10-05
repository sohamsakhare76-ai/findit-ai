"""Tiny, robust query parser: finds which supported object a sentence is about."""
import re

from detector import ALIASES, SUPPORTED

STOPWORDS = set("""
where is my the a an did i keep kept put leave left place placed find locate show me last
seen was are were do you know can please of to in on at it mine look for looking whereabouts
lost misplaced have has had we our your could would tell what s
""".split())


def _build_terms():
    terms = {c: c for c in SUPPORTED}
    terms.update(ALIASES)
    return sorted(terms.items(), key=lambda kv: -len(kv[0]))  # longest phrase first


TERMS = _build_terms()


def extract_object(query):
    """
    Returns one of:
      {"status": "empty"}
      {"status": "ok", "object": "<canonical class name>"}
      {"status": "unsupported", "term": "<what the user asked for>"}
    """
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (query or "").lower())
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return {"status": "empty"}

    padded = f" {cleaned} "
    for term, canonical in TERMS:
        if f" {term} " in padded or f" {term}s " in padded:
            return {"status": "ok", "object": canonical}
        if term.endswith("s") and f" {term[:-1]} " in padded:
            return {"status": "ok", "object": canonical}

    leftovers = [w for w in cleaned.split() if w not in STOPWORDS]
    return {"status": "unsupported", "term": " ".join(leftovers) or cleaned}
