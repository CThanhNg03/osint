"""Domain service for parsing and summarizing documents."""

from pathlib import Path
from apps.backend.src.infrastructure.external import llm_client


def parse_pdf(path: str) -> str:
    """Return extracted text for the provided PDF path (stubbed)."""
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(errors="ignore")


def summarize_document(text: str) -> str:
    """Summarize document text using the LLM client."""
    return llm_client.summarize(text)
