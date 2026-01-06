"""Schemas for document endpoints."""

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: int
    filename: str
    summary: str | None = None


class DocumentListItem(BaseModel):
    id: int
    filename: str
