import asyncio
import os
from datetime import datetime, timezone

from openai import OpenAI
from sqlalchemy import or_

from database import SessionLocal
from kg_extractor import extract_kg_for_log
from models import AnalysisLog
from neo4j_client import Neo4jClient


class KGWorker:
    """Background worker that extracts KG data and writes it to Neo4j."""

    def __init__(self, poll_interval: int = 15, batch_size: int = 20):
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._stop_event = asyncio.Event()

        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
            )
        else:
            self.client = None
            print("[KGWorker] GROQ_API_KEY is missing; KG extraction will be skipped.")

        self._neo4j_client = None
        try:
            self._neo4j_client = Neo4jClient.from_env()
        except Exception as exc:
            print(f"[KGWorker] Neo4j configuration missing or invalid: {exc}")
            self._neo4j_client = None

    async def run(self):
        while not self._stop_event.is_set():
            await self.process_pending_logs()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_interval)
            except asyncio.TimeoutError:
                continue

    async def process_pending_logs(self):
        if not self._neo4j_client or not self.client:
            # Skip work if Neo4j or LLM client is not configured; keep loop alive.
            return

        db = SessionLocal()
        try:
            pending_logs = (
                db.query(AnalysisLog)
                .filter(or_(AnalysisLog.kg_status == None, AnalysisLog.kg_status == "pending"))  # noqa: E711
                .order_by(AnalysisLog.timestamp.asc())
                .limit(self.batch_size)
                .all()
            )

            for log in pending_logs:
                try:
                    kg_data = await extract_kg_for_log(log, self.client)
                    log.kg_raw = kg_data
                    self._neo4j_client.upsert_kg_item(
                        log.id,
                        kg_data,
                        source=log.source,
                        summary=log.summary,
                        timestamp=log.timestamp.isoformat() if log.timestamp else None,
                        keywords=log.trending_keywords or [],
                    )
                    log.kg_status = "processed"
                    log.kg_processed_at = datetime.now(timezone.utc)
                except Exception as exc:
                    log.kg_status = "failed"
                    print(f"[KGWorker] Failed to process log {log.id}: {exc}")
                finally:
                    db.add(log)
                    db.commit()
        finally:
            db.close()

    async def stop(self):
        self._stop_event.set()
        if self._neo4j_client:
            self._neo4j_client.close()
