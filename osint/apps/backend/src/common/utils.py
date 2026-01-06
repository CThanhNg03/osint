"""Small shared utility functions."""

from typing import Iterable, Set


def to_unique(items: Iterable[str]) -> Set[str]:
    """Return a set of unique strings while ignoring falsy values."""
    return {item for item in items if item}
