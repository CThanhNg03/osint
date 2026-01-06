"""Keyword extraction and formatting helpers."""

from typing import List


def extract_keywords(text: str) -> List[str]:
    """Return a naive keyword list by splitting on spaces."""
    return [token.strip(",. ") for token in text.split() if token.strip(",. ")]


def bulletize(lines: List[str]) -> str:
    """Format a list of strings as bullet points."""
    return "\n".join(f"- {line}" for line in lines)
