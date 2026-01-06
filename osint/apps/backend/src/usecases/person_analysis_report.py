"""Use case for generating a person analysis report."""

from apps.backend.src.domain.policies import keywords
from apps.backend.src.domain.services import translation_service


def execute(name: str, bio: str) -> dict:
    """Summarize a person's information with keywords."""
    extracted = keywords.extract_keywords(bio)
    vi_bio = translation_service.to_vietnamese(bio)
    return {"name": name, "keywords": extracted, "bio_vi": vi_bio}
