"""Domain entity for knowledge graph snapshots."""

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class GraphSnapshot:
    nodes: List[Dict]
    edges: List[Dict]
