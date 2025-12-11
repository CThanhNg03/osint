import asyncio
import os
from datetime import datetime, timezone, timedelta

from openai import OpenAI
from sqlalchemy import and_, or_

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
        self._neo4j_backoff_until: datetime | None = None

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
        if not self.client:
            # Skip work if LLM client is not configured; keep loop alive.
            return

        now = datetime.now(timezone.utc)
        retry_cutoff = now - timedelta(minutes=30)
        neo4j_available = self._neo4j_client and (not self._neo4j_backoff_until or now >= self._neo4j_backoff_until)

        db = SessionLocal()
        try:
            pending_logs = (
                db.query(AnalysisLog)
                .filter(
                    or_(
                        AnalysisLog.kg_status == None,  # noqa: E711
                        AnalysisLog.kg_status == "pending",
                        and_(
                            AnalysisLog.kg_status == "failed",
                            or_(
                                AnalysisLog.kg_processed_at == None,  # noqa: E711
                                AnalysisLog.kg_processed_at <= retry_cutoff,
                            ),
                        ),
                    )
                )
                .order_by(AnalysisLog.timestamp.asc())
                .limit(self.batch_size)
                .all()
            )

            for log in pending_logs:
                attempted_at = datetime.now(timezone.utc)

                if not neo4j_available:
                    log.kg_status = "failed"
                    log.kg_processed_at = attempted_at
                    db.add(log)
                    db.commit()
                    continue

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
                    log.kg_processed_at = attempted_at
                except Exception as exc:
                    log.kg_status = "failed"
                    log.kg_processed_at = attempted_at
                    # Back off Neo4j writes for 30m to avoid noisy retries when the DB is down
                    self._neo4j_backoff_until = attempted_at + timedelta(minutes=30)
                    neo4j_available = False
                    print(
                        f"[KGWorker] Failed to process log {log.id}: {exc}. "
                        f"Will retry after {self._neo4j_backoff_until.isoformat()}."
                    )
                finally:
                    db.add(log)
                    db.commit()
        finally:
            db.close()

    async def stop(self):
        self._stop_event.set()
        if self._neo4j_client:
            self._neo4j_client.close()
