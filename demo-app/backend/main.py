import asyncio
import os
import hashlib
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from chat_handler import answer_question
from database import Base, engine, get_db
from kg_worker import KGWorker
import httpx
from stream_processor import StreamProcessor
from neo4j_client import Neo4jClient

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Media Monitor Demo API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize processors
YOUTUBE_URL = "https://www.youtube.com/watch?v=pykpO5kQJ98"
processor = StreamProcessor(YOUTUBE_URL)
kg_worker = KGWorker()
try:
    neo4j_client = Neo4jClient.from_env()
    try:
        neo4j_client.ensure_constraints()
        print("Neo4j constraints ensured.")
    except Exception as exc:
        print(f"Neo4j constraint setup skipped: {exc}")
    print("Neo4j client initialized.")
except Exception as exc:
    neo4j_client = None
    print(f"Neo4j client not available: {exc}")


class ChatRequest(BaseModel):
    question: str

class CrawlRequest(BaseModel):
    keyword: str
    limit: int = 5

class LiveToggleRequest(BaseModel):
    enabled: bool


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                # Drop broken connections silently
                try:
                    self.active_connections.remove(connection)
                except ValueError:
                    pass


manager = ConnectionManager()


async def process_callback(data):
    """Transform Gemini analysis data for frontend WebSocket"""

    news_item = {
        "id": str(int(datetime.now().timestamp())),
        "source": data["source"],
        "title": data.get("headline_ocr", "Breaking News"),
        "ocr_text": data.get("headline_ocr", ""),
        "english_summary": data.get("summary", ""),
        "vietnamese_translation": data.get("vietnamese_translation", ""),
        "timestamp": data["timestamp"],
        "sentiment": "Positive" if data.get("sentiment_score", 0) > 0 else "Negative",
        "keywords": data.get("keywords", []),
    }

    analytics = {
        "sentiment_score": data.get("sentiment_score", 0),
        "trending_keywords": data.get("keywords", []),
        "active_sources": 1,
        "total_mentions": 1240,
    }

    subtitle = {
        "text": data.get("subtitle_vi", "Dang phan tich..."),
        "lang": "vi",
        "timestamp": data["timestamp"],
    }

    await manager.broadcast({"type": "news", "data": news_item})
    await manager.broadcast({"type": "analytics", "data": analytics})
    await manager.broadcast({"type": "subtitle", "data": subtitle})

    print(f"[WebSocket] Broadcasted: {subtitle['text'][:50]}...")


# Global tasks
stream_task: asyncio.Task | None = None
kg_worker_task: asyncio.Task | None = None
processing_enabled = True


@app.on_event("startup")
async def startup_event():
    global stream_task, kg_worker_task
    print("Starting Media Monitor Backend...")
    if processing_enabled:
        stream_task = asyncio.create_task(processor.process_stream(process_callback))
    print("Starting KG worker...")
    kg_worker_task = asyncio.create_task(kg_worker.run())


@app.on_event("shutdown")
async def shutdown_event():
    global stream_task, kg_worker_task
    print("Shutting down stream processor...")
    processor.stop()
    if stream_task:
        stream_task.cancel()
    print("Stopping KG worker...")
    await kg_worker.stop()
    if kg_worker_task:
        kg_worker_task.cancel()


@app.get("/")
async def root():
    return {"message": "Media Monitor Backend is running"}


@app.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Endpoint cho chat voi Groq tu du lieu da thu thap."""
    result = await answer_question(request.question, db)
    return result


@app.post("/crawl")
async def crawl_news(request: CrawlRequest):
    """Fetch recent news articles from NewsAPI for a given keyword."""
    api_key = os.getenv("NEWSAPI_KEY") or os.getenv("NEWSAPI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="NEWSAPI_KEY not configured")

    params = {
        "q": request.keyword,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(max(request.limit, 1), 20),
        "apiKey": api_key,
    }

    url = "https://newsapi.org/v2/everything"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        payload = resp.json()
        articles = payload.get("articles", [])

    # Normalize minimal fields for frontend
    normalized = [
        {
          "title": a.get("title"),
          "description": a.get("description"),
          "url": a.get("url"),
          "source": (a.get("source") or {}).get("name"),
          "published_at": a.get("publishedAt"),
        }
        for a in articles
    ]

    # Optionally upsert into Neo4j as NewsItem nodes for later exploration
    if neo4j_client:
        for item in normalized:
            # Merge by source when available, otherwise by URL/title
            base_str = item.get("source") or item.get("url") or item.get("title") or str(datetime.now().timestamp())
            news_hash = int(hashlib.md5(base_str.encode("utf-8")).hexdigest()[:16], 16)
            try:
                neo4j_client.upsert_kg_item(
                    news_id=news_hash,
                    kg_data={"entities": [], "events": [], "relations": []},
                    source=item.get("source") or "NewsAPI",
                    summary=item.get("title") or item.get("description") or "",
                    timestamp=item.get("published_at"),
                )
            except Exception as exc:
                print(f"Neo4j upsert error for crawled news: {exc}")

    return {"count": len(normalized), "articles": normalized}


@app.get("/kg/search")
async def kg_search(keyword: str = Query(""), limit: int = Query(50, le=100)):
    """Return nodes/edges around entities matching keyword."""
    if not neo4j_client:
        raise HTTPException(status_code=503, detail="Neo4j not configured")
    cypher = """
    MATCH p=(n:Entity)-[r]-(m)
    WHERE toLower(n.name) CONTAINS toLower($keyword)
    RETURN DISTINCT elementId(n) as nid, labels(n) as nlabels, n.name as nname, n.type as ntype,
                    elementId(m) as mid, labels(m) as mlabels, m.name as mname, m.type as mtype,
                    elementId(r) as rid, type(r) as rtype, elementId(startNode(r)) as sid, elementId(endNode(r)) as eid
    LIMIT $limit
    """
    with neo4j_client.session() as session:
        records = session.run(cypher, keyword=keyword, limit=limit).data()

    nodes = {}
    edges = {}
    for rec in records:
        nodes[rec["nid"]] = {
            "id": rec["nid"],
            "name": rec.get("nname") or rec["nid"],
            "type": rec.get("ntype") or "Entity",
            "labels": rec.get("nlabels") or [],
        }
        nodes[rec["mid"]] = {
            "id": rec["mid"],
            "name": rec.get("mname") or rec["mid"],
            "type": rec.get("mtype") or "Entity",
            "labels": rec.get("mlabels") or [],
        }
        rid = rec["rid"]
        if rid not in edges:
            edges[rid] = {
                "id": rid,
                "source": rec["sid"],
                "target": rec["eid"],
                "type": rec.get("rtype") or "",
            }

    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


@app.websocket("/ws/monitor")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/live/toggle")
async def live_toggle(req: LiveToggleRequest):
    """Toggle backend live processing (stream)."""
    global processing_enabled, stream_task
    if req.enabled == processing_enabled:
        return {"enabled": processing_enabled}

    if not req.enabled:
        # Turn off
        processing_enabled = False
        processor.stop()
        if stream_task:
            stream_task.cancel()
            stream_task = None
        return {"enabled": False}

    # Turn on: start stream_task if not running
    processing_enabled = True
    stream_task = asyncio.create_task(processor.process_stream(process_callback))
    return {"enabled": True}
