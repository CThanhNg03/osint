import os
from typing import List

from openai import OpenAI

# Self-hosted or OpenAI-compatible embedding endpoint (works with Ollama's /v1 API)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL") or os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
EMBEDDING_API_KEY = (
    os.getenv("EMBEDDING_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or os.getenv("GROQ_API_KEY")
    or "ollama"
)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not EMBEDDING_API_KEY:
            raise RuntimeError("No embedding API key set (EMBEDDING_API_KEY / OPENAI_API_KEY / GROQ_API_KEY).")
        _client = OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)
    return _client


def generate_embedding(text: str) -> List[float]:
    """Generate a vector embedding against the configured OpenAI-compatible endpoint."""
    if not text or not text.strip():
        return []
    client = _get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding
