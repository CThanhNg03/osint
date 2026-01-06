"""Domain entity representing an analysis log."""

from dataclasses import dataclass


@dataclass
class AnalysisLog:
    id: int | None
    title: str
    summary: str | None = None
