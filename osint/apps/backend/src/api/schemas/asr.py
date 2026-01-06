"""Schemas for ASR endpoints."""

from pydantic import BaseModel


class TranscriptionResponse(BaseModel):
    text: str
    confidence: float
