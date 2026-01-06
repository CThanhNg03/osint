"""Wrapper around LLM provider APIs."""

from typing import Any
import httpx
from apps.backend.src.infrastructure.settings import settings


def summarize(text: str) -> str:
    """Call the configured LLM to summarize text (stubbed)."""
    if not settings.openai_api_key:
        return text[:200]
    # Placeholder for real call
    with httpx.Client() as client:
        _ = client  # avoid unused variable in stub
    return f"Summary of: {text[:100]}"
