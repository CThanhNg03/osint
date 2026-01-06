"""Schemas for knowledge graph endpoints."""

from pydantic import BaseModel
from typing import List, Dict


class GraphSnapshot(BaseModel):
    nodes: List[Dict]
    edges: List[Dict]


class GraphResponse(BaseModel):
    graph: GraphSnapshot | None
    report: str | None = None
