"""Domain entity describing a person record."""

from dataclasses import dataclass
from typing import List


@dataclass
class Person:
    name: str
    aliases: List[str]
    bio: str | None = None
