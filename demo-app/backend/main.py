import asyncio
import os
import hashlib
from datetime import datetime
from io import BytesIO

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from chat_handler import answer_question
from database import Base, engine, get_db
from ingestion_queue import IngestionQueue
from kg_worker import KGWorker
from openai import OpenAI
import httpx
import feedparser
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
kg_worker = KGWorker()
try:
    neo4j_client = Neo4jClient.from_env()
    try:
        neo4j_client.ensure_constraints()
        print("Neo4j constraints ensured.")
    except Exception as exc:
        print(f"Neo4j constraint setup skipped: {exc}")
        neo4j_client.close()
        neo4j_client = None
    if neo4j_client:
        print("Neo4j client initialized.")
except Exception as exc:
    neo4j_client = None
    print(f"Neo4j client not available: {exc}")

ingestion_queue = IngestionQueue.from_env()


class ChatRequest(BaseModel):
    question: str

class CrawlRequest(BaseModel):
    keyword: str
    limit: int = 5
    source_type: str = "news"  # news | social | both
    country: str | None = None  # optional ISO country filter for newsdata/newsapi
    source_id: str | None = None  # optional specific source filter

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


def _get_audio_client():
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
    )


def _background_upsert_crawled_news(articles, search_terms=None):
    """Push crawled articles into Neo4j after response returns."""
    if not neo4j_client:
        return
    search_terms = [t.strip() for t in (search_terms or []) if (t or "").strip()]

    def _news_id_from_item(item: dict) -> int:
        base_str = (
            item.get("source")
            or item.get("url")
            or item.get("title")
            or str(datetime.now().timestamp())
        )
        # Clamp to signed 63-bit to satisfy Neo4j integer range
        raw = hashlib.md5(base_str.encode("utf-8")).digest()[:8]
        hashed = int.from_bytes(raw, byteorder="big", signed=False) % (2**63 - 1)
        return hashed or 1

    for item in articles:
        news_hash = _news_id_from_item(item)
        try:
            neo4j_client.upsert_kg_item(
                news_id=news_hash,
                kg_data={"entities": [], "events": [], "relations": []},
                source=item.get("source") or "NewsAPI",
                summary=item.get("title") or item.get("description") or "",
                timestamp=item.get("published_at"),
                keywords=search_terms,
            )
        except Exception as exc:
            # Include identifying info for easier debugging
            print(
                "Neo4j upsert error for crawled news",
                {
                    "error": str(exc),
                    "news_id": news_hash,
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                },
    )


DEFAULT_RSS_FEEDS = [
    "https://kohsantepheapdaily.com.kh/feed",
    "https://www.kampucheathmey.com/feed",
    "https://cen.com.kh/feed",
]


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


async def _consume_ingestion_queue():
    if not ingestion_queue:
        print("Ingestion queue not configured; skipping consumer.")
        return
    print("Starting ingestion queue consumer...")
    while not _stop_event.is_set():
        try:
            # Blocking pop with timeout to allow clean shutdown
            item = await asyncio.to_thread(ingestion_queue.pop, 5)
            if not item:
                continue
            await process_callback(item)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            print(f"[Queue consumer] Error: {exc}")
            await asyncio.sleep(1)
    print("Ingestion queue consumer stopped.")


# Global tasks
consumer_task: asyncio.Task | None = None
kg_worker_task: asyncio.Task | None = None
processing_enabled = True
_stop_event = asyncio.Event()


@app.on_event("startup")
async def startup_event():
    global consumer_task, kg_worker_task
    print("Starting Media Monitor Backend...")
    if processing_enabled and ingestion_queue:
        consumer_task = asyncio.create_task(_consume_ingestion_queue())
    print("Starting KG worker...")
    kg_worker_task = asyncio.create_task(kg_worker.run())


@app.on_event("shutdown")
async def shutdown_event():
    global consumer_task, kg_worker_task
    print("Shutting down ingestion consumer...")
    _stop_event.set()
    if consumer_task:
        consumer_task.cancel()
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
async def crawl_news(request: CrawlRequest, background_tasks: BackgroundTasks):
    """Fetch recent items from news and/or social (X) for a given keyword."""

    keyword = (request.keyword or "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")

    source_type = (request.source_type or "news").lower()
    do_news = source_type in ("news", "both")
    do_social = source_type in ("social", "both")

    news_items: list[dict] = []
    social_items: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        if do_news:
            news_data_api_key = os.getenv("NEWS_DATA_API_KEY") or os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_IO_API_KEY")
            if news_data_api_key:
                params = {
                    "apikey": news_data_api_key,
                    "q": keyword,
                    "language": "en",
                    "size": min(max(request.limit, 1), 20),
                }
                if request.country:
                    params["country"] = request.country.lower()
                if request.source_id:
                    params["source_id"] = request.source_id
                url = "https://newsdata.io/api/1/latest"
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                payload = resp.json()
                articles = payload.get("results") or []
                news_items = [
                    {
                        "title": a.get("title"),
                        "description": a.get("description"),
                        "url": a.get("link"),
                        "source": a.get("source_id"),
                        "published_at": a.get("pubDate"),
                        "type": "news",
                    }
                    for a in articles
                ]
            else:
                api_key = os.getenv("NEWSAPI_KEY") or os.getenv("NEWSAPI_API_KEY")
                if not api_key:
                    raise HTTPException(status_code=500, detail="NEWSAPI_KEY or NEWS_DATA_API_KEY not configured")
                params = {
                    "q": keyword,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": min(max(request.limit, 1), 20),
                    "apiKey": api_key,
                }
                if request.country:
                    params["country"] = request.country.lower()
                if request.source_id:
                    params["sources"] = request.source_id
                url = "https://newsapi.org/v2/everything"
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                payload = resp.json()
                articles = payload.get("articles", [])
                news_items = [
                    {
                        "title": a.get("title"),
                        "description": a.get("description"),
                        "url": a.get("url"),
                        "source": (a.get("source") or {}).get("name"),
                        "published_at": a.get("publishedAt"),
                        "type": "news",
                    }
                    for a in articles
                ]

        # Fixed RSS crawl
        rss_items: list[dict] = []
        rss_urls = DEFAULT_RSS_FEEDS
        for rss_url in rss_urls:
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries[: max(1, min(request.limit, 20))]:
                    rss_items.append(
                        {
                            "title": entry.get("title"),
                            "description": entry.get("summary"),
                            "url": entry.get("link"),
                            "source": feed.feed.get("title") if hasattr(feed, "feed") else "RSS",
                            "published_at": entry.get("published"),
                            "type": "rss",
                        }
                    )
            except Exception as exc:
                print(f"[RSS] Failed to parse {rss_url}: {exc}")

        if do_social:
            token = os.getenv("X_BEARER_TOKEN")
            if not token:
                raise HTTPException(status_code=500, detail="X_BEARER_TOKEN not configured")
            params = {
                "query": keyword,
                "max_results": min(max(request.limit * 3, 10), 100),
                "tweet.fields": "created_at,lang,public_metrics,text",
            }
            url = "https://api.twitter.com/2/tweets/search/recent"
            resp = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            payload = resp.json()
            tweets = payload.get("data", []) or []
            social_items = [
                {
                    "title": (t.get("text") or "")[:120],
                    "description": t.get("text"),
                    "url": f"https://x.com/i/web/status/{t.get('id')}",
                    "source": "X",
                    "published_at": t.get("created_at"),
                    "type": "social",
                }
                for t in tweets
            ]

    # Combine rss with news and upsert into Neo4j in the background
    if rss_items:
        if news_items:
            news_items.extend(rss_items)
        else:
            news_items = rss_items

    if neo4j_client and news_items:
        terms = [t.strip() for t in request.keyword.split(",")] if request.keyword else []
        background_tasks.add_task(_background_upsert_crawled_news, news_items, terms)

    return {
        "source_type": source_type,
        "news": {"count": len(news_items), "items": news_items},
        "social": {"count": len(social_items), "items": social_items},
        "rss": {"count": len(rss_items), "items": rss_items},
    }


@app.post("/whisper/transcribe")
async def whisper_transcribe(file: UploadFile = File(...)):
    """Transcribe uploaded audio (mic recording) with Whisper and normalize as a news item."""
    client = _get_audio_client()
    if not client:
        raise HTTPException(
            status_code=500,
            detail="Missing GROQ_API_KEY/OPENAI_API_KEY for Whisper transcription",
        )

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    audio_file = BytesIO(audio_bytes)
    audio_file.name = file.filename or "audio.webm"
    model_name = os.getenv("WHISPER_MODEL", "whisper-large-v3")

    try:
        transcription = client.audio.transcriptions.create(
            model=model_name,
            file=audio_file,
            response_format="verbose_json",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Whisper transcription failed: {exc}") from exc

    payload = (
        transcription.model_dump()
        if hasattr(transcription, "model_dump")
        else transcription
        if isinstance(transcription, dict)
        else {}
    )

    text = payload.get("text") or getattr(transcription, "text", "")
    language = payload.get("language") or getattr(transcription, "language", None)
    duration = payload.get("duration") or getattr(transcription, "duration", None)

    segments = []
    for seg in payload.get("segments") or []:
        if hasattr(seg, "model_dump"):
            seg = seg.model_dump()
        if isinstance(seg, dict):
            segments.append(
                {
                    "id": seg.get("id"),
                    "start": seg.get("start"),
                    "end": seg.get("end"),
                    "text": seg.get("text"),
                    "avg_logprob": seg.get("avg_logprob"),
                }
            )

    now_ts = datetime.now().isoformat()
    news_item = {
        "id": f"whisper-{int(datetime.now().timestamp())}",
        "source": "Mic Recording",
        "title": text[:120] or "Recorded audio",
        "ocr_text": text,
        "english_summary": text,
        "vietnamese_translation": "",
        "timestamp": now_ts,
        "sentiment": "Neutral",
        "keywords": [],
        "summary": text,
    }

    return {
        "text": text,
        "language": language,
        "duration": duration,
        "segments": segments,
        "news_item": news_item if text else None,
    }


@app.get("/news/sources")
async def news_sources(country: str = "kh"):
    """List news sources (default Cambodia) from NewsData.io."""
    api_key = os.getenv("NEWS_DATA_API_KEY") or os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_IO_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="NEWS_DATA_API_KEY is required for sources lookup")
    url = "https://newsdata.io/api/1/sources"
    params = {"apikey": api_key, "country": country.lower()}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        payload = resp.json()
    return payload.get("results") or []


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
    global processing_enabled, consumer_task
    if req.enabled == processing_enabled:
        return {"enabled": processing_enabled}

    if not req.enabled:
        # Turn off
        processing_enabled = False
        _stop_event.set()
        if consumer_task:
            consumer_task.cancel()
            consumer_task = None
        return {"enabled": False}

    # Turn on: start stream_task if not running
    processing_enabled = True
    _stop_event.clear()
    if ingestion_queue:
        consumer_task = asyncio.create_task(_consume_ingestion_queue())
    return {"enabled": True}


@app.get("/asr/status")
async def asr_status():
    if not ingestion_queue:
        raise HTTPException(status_code=503, detail="Ingestion queue not configured")
    cfg = ingestion_queue.load_config()
    defaults = {
        "sources": [s.strip() for s in (os.getenv("WHISPER_SOURCES") or "").split(",") if s.strip()],
        "capture_seconds": int(os.getenv("WHISPER_CAPTURE_SECONDS", "45")),
        "break_seconds": int(os.getenv("WHISPER_BREAK_SECONDS", "15")),
        "capture_rate": int(os.getenv("WHISPER_CAPTURE_RATE", "1")),
    }
    merged = {**defaults, **{k: v for k, v in cfg.items() if v is not None}}
    merged["running"] = processing_enabled
    return merged


@app.post("/asr/config")
async def asr_config(cfg: dict):
    if not ingestion_queue:
        raise HTTPException(status_code=503, detail="Ingestion queue not configured")
    allowed_keys = {"sources", "capture_seconds", "break_seconds", "capture_rate"}
    clean = {k: v for k, v in cfg.items() if k in allowed_keys}
    ingestion_queue.save_config(clean)
    updated = ingestion_queue.load_config()
    updated["running"] = processing_enabled
    return updated
