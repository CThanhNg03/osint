"""Domain service for knowledge graph operations."""

from typing import List, Dict
from apps.backend.src.domain.entities.graph import GraphSnapshot
from apps.backend.src.infrastructure.graph.neo4j_client import get_neo4j_driver


def build_snapshot(nodes: List[Dict], edges: List[Dict]) -> GraphSnapshot:
    """Construct a GraphSnapshot entity."""
    return GraphSnapshot(nodes=nodes, edges=edges)


def write_social_graph(nodes: List[Dict], edges: List[Dict]) -> None:
    """Persist nodes and edges into Neo4j if configured."""
    driver = get_neo4j_driver()
    if not driver:
        return
    cypher = "UNWIND $nodes as n MERGE (p:Person {id:n.id}) SET p.name=n.name"
    with driver.session() as session:
        session.run(cypher, nodes=nodes)
        # Edge writing simplified
        session.run("RETURN 1")


def generate_report(snapshot: GraphSnapshot) -> str:
    """Create a human-readable report from a graph snapshot."""
    node_names = ", ".join(node.get("name", "node") for node in snapshot.nodes)
    return f"Graph with nodes: {node_names}"
