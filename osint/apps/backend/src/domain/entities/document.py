"""Domain entity for uploaded documents."""

from dataclasses import dataclass


@dataclass
class Document:
    id: int | None
    filename: str
    storage_path: str
