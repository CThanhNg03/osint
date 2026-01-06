"""Schemas for people endpoints."""

from pydantic import BaseModel
from typing import List


class PersonResult(BaseModel):
    name: str
    aliases: List[str] = []
    bio: str | None = None


class PeopleResponse(BaseModel):
    people: List[PersonResult]
