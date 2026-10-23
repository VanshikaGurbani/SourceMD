"""Text normalisation shared by the quote validator and the citation checks."""
from __future__ import annotations

import re
import unicodedata

from backend.agents import citations

_WS = re.compile(r"\s+")
_TRANSLATE = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        " ": " ",
        "­": "",  # soft hyphen
    }
)


def normalize(text: str) -> str:
    """Lowercase, unify quotes/dashes and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text).translate(_TRANSLATE)
    return _WS.sub(" ", text).strip().lower()


quote_in = citations.quote_in  # one definition of "literally appears" for eval and product


def token_coverage(quote: str, text: str) -> float:
    """Fraction of the quote's word tokens that occur in ``text`` (0-1)."""
    tokens = re.findall(r"[a-z0-9]+", normalize(quote))
    if not tokens:
        return 0.0
    have = set(re.findall(r"[a-z0-9]+", normalize(text)))
    return sum(1 for t in tokens if t in have) / len(tokens)
