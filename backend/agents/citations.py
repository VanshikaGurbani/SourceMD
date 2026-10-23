"""Check that a cited quote is literally present in the passage it cites."""
from __future__ import annotations

import re
import unicodedata

from backend.agents.state import RetrievedPassage

_WS_HYPHEN = re.compile(r"[\s\-‐-—­]+")
_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


def _compact(text: str) -> str:
    """Case/quote/whitespace/hyphen-insensitive form used for literal matching.

    PDF extraction breaks lines mid-word, so spacing and hyphenation are ignored;
    wording and numbers must still match exactly.
    """
    return _WS_HYPHEN.sub("", unicodedata.normalize("NFKC", text).translate(_QUOTES).lower())


def quote_in(quote: str, text: str) -> bool:
    """True if ``quote`` literally appears in ``text`` (ignoring spacing/hyphenation)."""
    q = _compact(quote)
    return bool(q) and q in _compact(text)


def verify_citation(
    quote: str, cited_passage: int | None, passages: list[RetrievedPassage]
) -> bool:
    """True if ``cited_passage`` (1-based) exists and contains ``quote`` literally."""
    if cited_passage is None or not 1 <= cited_passage <= len(passages):
        return False
    return quote_in(quote, passages[cited_passage - 1]["text"])
