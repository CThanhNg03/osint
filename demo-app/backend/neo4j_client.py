import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase, Driver, Session


class Neo4jClient:
    """Thin helper around the official Neo4j driver."""

    def __init__(self, uri: str, user: str, password: str):
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    @classmethod
    def from_env(cls) -> "Neo4jClient":
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        if not uri or not user or not password:
            raise ValueError("Neo4j configuration missing; please set NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD.")
        return cls(uri, user, password)

    @contextmanager
    def session(self) -> Session:
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    def close(self) -> None:
        self._driver.close()

    def ensure_constraints(self) -> None:
        """Create uniqueness constraints to enable idempotent upserts."""
        statements = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NewsItem) REQUIRE n.news_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ev:Event) REQUIRE ev.event_id IS UNIQUE",
        ]
        with self.session() as session:
            for stmt in statements:
                session.execute_write(lambda tx, s=stmt: tx.run(s))

    def upsert_kg_item(
        self,
        news_id: int,
        kg_data: Dict[str, Any],
        source: Optional[str] = None,
        summary: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        """Upsert NewsItem, Entity, Event nodes and their relationships."""
        if not kg_data:
            return

        entities: List[Dict[str, Any]] = kg_data.get("entities") or []
        events: List[Dict[str, Any]] = kg_data.get("events") or []
        relations: List[Dict[str, Any]] = kg_data.get("relations") or []

        with self.session() as session:
            session.execute_write(
                self._write_kg,
                news_id,
                source or "",
                summary or "",
                timestamp,
                entities,
                events,
                relations,
            )

    @staticmethod
    def _write_kg(
        tx,
        news_id: int,
        source: str,
        summary: str,
        timestamp: Optional[str],
        entities: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
    ) -> None:
        tx.run(
            """
            MERGE (n:NewsItem {news_id: $news_id})
            SET n.source = $source,
                n.summary = $summary,
                n.timestamp = coalesce($timestamp, n.timestamp)
            """,
            news_id=news_id,
            source=source,
            summary=summary,
            timestamp=timestamp,
        )

        for entity in entities:
            name = entity.get("name")
            etype = entity.get("type") or "Unknown"
            if not name:
                continue
            tx.run(
                """
                MATCH (n:NewsItem {news_id: $news_id})
                MERGE (e:Entity {name: $name, type: $type})
                MERGE (e)-[:MENTIONED_IN]->(n)
                """,
                news_id=news_id,
                name=name,
                type=etype,
            )

        for idx, event in enumerate(events):
            event_id = event.get("event_id") or event.get("id") or f"event-{news_id}-{idx}"
            ev_type = event.get("type") or "Event"
            ev_time = event.get("time")
            ev_location = event.get("location")
            participants = event.get("participants") or []

            tx.run(
                """
                MATCH (n:NewsItem {news_id: $news_id})
                MERGE (ev:Event {event_id: $event_id})
                SET ev.type = $type,
                    ev.time = coalesce($time, ev.time),
                    ev.location = coalesce($location, ev.location)
                MERGE (ev)-[:REPORTED_IN]->(n)
                """,
                news_id=news_id,
                event_id=event_id,
                type=ev_type,
                time=ev_time,
                location=ev_location,
            )

            for participant in participants:
                if not participant:
                    continue
                tx.run(
                    """
                    MATCH (n:NewsItem {news_id: $news_id})
                    MERGE (e:Entity {name: $participant})
                    ON CREATE SET e.type = "Unknown"
                    MERGE (e)-[:PARTICIPATES_IN]->(ev:Event {event_id: $event_id})
                    MERGE (e)-[:MENTIONED_IN]->(n)
                    """,
                    news_id=news_id,
                    participant=participant,
                    event_id=event_id,
                )

        for relation in relations:
            subject = relation.get("subject")
            predicate = relation.get("predicate")
            obj = relation.get("object")
            if not subject or not predicate or not obj:
                continue

            tx.run(
                """
                MATCH (n:NewsItem {news_id: $news_id})
                MERGE (s:Entity {name: $subject})
                ON CREATE SET s.type = "Unknown"
                MERGE (o:Entity {name: $object})
                ON CREATE SET o.type = "Unknown"
                MERGE (s)-[r:RELATED {predicate: $predicate}]->(o)
                MERGE (s)-[:MENTIONED_IN]->(n)
                MERGE (o)-[:MENTIONED_IN]->(n)
                """,
                news_id=news_id,
                subject=subject,
                predicate=predicate,
                object=obj,
            )
