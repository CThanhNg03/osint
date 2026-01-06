"""Schemas for live monitoring endpoints."""

from pydantic import BaseModel


class LiveState(BaseModel):
    enabled: bool
