"""Schemas for news endpoints."""

from pydantic import BaseModel
from typing import List


class NewsItem(BaseModel):
    title: str | None = None
    url: str | None = None
    source: str | None = None


class NewsResponse(BaseModel):
    items: List[NewsItem]
