import asyncio
import os
import hashlib
from datetime import datetime
from io import BytesIO
import urllib.parse

import httpx
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Query,
    BackgroundTasks,
    UploadFile,
    File,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from chat_handler import answer_question
from database import Base, engine, get_db, SessionLocal
from ingestion_queue import IngestionQueue
from kg_worker import KGWorker
from models import AnalysisLog
from neo4j_client import Neo4jClient
from openai import OpenAI
import feedparser

# Optional fixed translator (no-LM) for Khmer -> Vietnamese
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Media Monitor API Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
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
PERSON_SERVICE_URL = os.getenv("PERSON_SERVICE_URL", "http://person-service:8001")

def _write_social_graph_to_neo4j(graph: dict):
    """Persist a simple person->account->post graph into Neo4j."""
    if not neo4j_client or not graph:
        return
    person_name = graph.get("person_name") or graph.get("name")
    person_id = graph.get("person_id") or graph.get("id") or person_name
    accounts = graph.get("accounts") or []
    posts = graph.get("posts") or []
    interactions = graph.get("interactions") or []
    edges = graph.get("edges") or []
    primary_account_id = graph.get("primary_account_id") or (accounts[0]["id"] if accounts else None)
    # If interactions missing but edges provided, map mock edges (commented_on) to interactions
    if not interactions and edges:
        post_ids = {p.get("id") for p in posts}
        acc_lookup = {a.get("id"): a for a in accounts}
        for e in edges:
            if (e.get("type") or "").lower() != "commented_on":
                continue
            src = e.get("source")
            tgt = e.get("target")
            if src in (None, "person"):
                continue
            if tgt not in post_ids:
                continue
            acc = acc_lookup.get(src) or {}
            interactions.append(
                {
                    "account_id": src,
                    "post_id": tgt,
                    "type": "comment",
                    "handle": acc.get("handle"),
                    "display_name": acc.get("display_name"),
                }
            )
    # If interactions are missing, synthesize commenters (non-primary accounts) on posts
    if not interactions and posts:
        commenter_accounts = [a for a in accounts if a.get("id") != primary_account_id] or accounts
        for idx, post in enumerate(posts):
            acc = commenter_accounts[idx % len(commenter_accounts)]
            interactions.append(
                {
                    "account_id": acc.get("id"),
                    "post_id": post.get("id"),
                    "type": "comment",
                    "handle": acc.get("handle"),
                    "display_name": acc.get("display_name"),
                }
            )
    if not person_name:
        return
    cypher = """
    // create person and accounts (no Person->Account edges)
    MERGE (p:Person {person_id: $person_id})
    ON CREATE SET p.name = $person_name
    ON MATCH SET p.name = coalesce(p.name, $person_name)
    // remove legacy HAS_ACCOUNT edges for this person
    WITH p
    OPTIONAL MATCH (p)-[ha:HAS_ACCOUNT]->(:Account)
    DELETE ha
    WITH p, $accounts AS accounts, $posts AS posts
    UNWIND accounts AS acc
      MERGE (a:Account {id: acc.id})
      SET a.handle = acc.handle,
          a.display_name = coalesce(acc.display_name, acc.handle),
          a.name = coalesce(acc.display_name, acc.handle, acc.id)
    WITH p, accounts, posts, $interactions AS interactions
    UNWIND posts AS post
      MERGE (po:Post {id: post.id})
      SET po.text = post.text,
          po.timestamp = post.timestamp,
          po.summary = post.summary,
          po.caption = coalesce(post.caption, 'X Post'),
          po.source = coalesce(post.source, 'X')
      MERGE (p)-[:POSTED]->(po)
    WITH p, interactions
    UNWIND interactions AS inter
      MATCH (po:Post {id: inter.post_id})
      MERGE (c:Account {id: inter.account_id})
      SET c.handle = coalesce(inter.handle, c.handle),
          c.display_name = coalesce(inter.display_name, c.display_name, c.handle),
          c.name = coalesce(c.display_name, c.handle, c.id)
      MERGE (c)-[:COMMENTED_ON {type: coalesce(inter.type, 'comment')}]->(po)
    """
    try:
        with neo4j_client.session() as session:
            session.run(
                cypher,
                person_name=person_name,
                person_id=person_id,
                accounts=accounts,
                posts=posts,
                interactions=interactions,
            )
    except Exception as exc:
        print(f"[KG] Failed to write social graph: {exc}")

def _social_graph_for_name(name: str) -> dict:
    """Best-effort account lookup for a name; falls back to a mock account+posts."""
    clean = (name or "").strip()
    token = os.getenv("X_BEARER_TOKEN")
    account = None
    if token and clean:
        try:
            url = f"https://api.twitter.com/2/users/by?usernames={urllib.parse.quote(clean)}"
            req = httpx.Request("GET", url, headers={"Authorization": f"Bearer {token}"})
            with httpx.Client(timeout=5.0) as client:
                resp = client.send(req)
            if resp.status_code == 200:
                data = resp.json().get("data") or []
                if data:
                    u = data[0]
                    account = {
                        "id": u.get("id") or clean,
                        "handle": f"@{u.get('username')}" if u.get("username") else None,
                        "display_name": u.get("name") or u.get("username") or clean,
                    }
        except Exception:
            account = None
    if not account:
        slug = clean.lower().replace(" ", "_") or "unknown"
        account = {"id": f"acct_{slug}", "handle": f"@{slug}", "display_name": clean or slug}
    posts = [
        {"id": f"{account['id']}_p1", "account_id": account["id"], "text": f"Latest update about {clean}", "timestamp": datetime.utcnow().isoformat(), "source": "X", "caption": "X Post"},
        {"id": f"{account['id']}_p2", "account_id": account["id"], "text": f"Another note on {clean}", "timestamp": datetime.utcnow().isoformat(), "source": "X", "caption": "X Post"},
    ]
    # mock interactions from other accounts
    commenter1 = {"id": f"{account['id']}_c1", "handle": f"@friend_of_{account['id']}", "display_name": "Top commenter"}
    commenter2 = {"id": f"{account['id']}_c2", "handle": f"@fan_of_{account['id']}", "display_name": "Fan"}
    interactions = [
        {"account_id": commenter1["id"], "post_id": posts[0]["id"], "type": "comment", "handle": commenter1["handle"], "display_name": commenter1["display_name"]},
        {"account_id": commenter2["id"], "post_id": posts[1]["id"], "type": "comment", "handle": commenter2["handle"], "display_name": commenter2["display_name"]},
    ]
    accounts_extra = [commenter1, commenter2]
    accounts_full = [account] + accounts_extra
    return {
        "source": "x",
        "person_name": clean,
        "person_id": clean,
        "accounts": accounts_full,
        "primary_account_id": account["id"],
        "posts": posts,
        "edges": [],
        "interactions": interactions,
        "mock": True,
    }


def _translate_to_vi(text: str, client: OpenAI | None = None) -> str:
    """Best-effort Vietnamese translation; returns original text on failure."""
    content = (text or "").strip()
    if not content:
        return ""

    def _contains_khmer(val: str) -> bool:
        return any("\u1780" <= ch <= "\u17ff" for ch in val)

    # Prefer fixed translator if Khmer detected and library is available
    if _contains_khmer(content) and GoogleTranslator:
        try:
            fixed = GoogleTranslator(source="km", target="vi").translate(content)
            if fixed:
                return fixed.strip()
        except Exception:
            pass

    if not client:
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ""
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
        )
    prompt = f"Translate to Vietnamese, keep concise, no markdown:\n{content[:1500]}"
    khmer_prompt = f"Translate this Khmer text to Vietnamese. Return Vietnamese only, no markdown:\n{content[:1500]}"
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        result = (resp.choices[0].message.content or "").strip()
        if result:
            return result
        # Retry with explicit Khmer->VI instruction if text contains Khmer script
        if _contains_khmer(content):
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": khmer_prompt}],
                temperature=0.2,
                max_tokens=400,
            )
            fallback = (resp.choices[0].message.content or "").strip()
            if fallback:
                return fallback
        return ""
    except Exception:
        return ""


class ChatRequest(BaseModel):
    question: str


class CrawlRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    keyword: str
    limit: int = 5
    source_type: str = "news"  # news | social | both
    country: str | None = None  # optional ISO country filter for newsdata/newsapi
    source_id: str | None = None  # optional specific source filter
    lang: str | None = Field(default=None, alias="language")
    source: str | None = None  # alias for source_id
    sources: list[str] | None = None  # optional list of source ids


class LiveToggleRequest(BaseModel):
    enabled: bool


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                try:
                    self.active_connections.remove(connection)
                except ValueError:
                    pass


manager = ConnectionManager()
_stop_event = asyncio.Event()
consumer_task: asyncio.Task | None = None
kg_worker_task: asyncio.Task | None = None
processing_enabled = False


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
                translation_vi=item.get("vietnamese_translation") or "",
                timestamp=item.get("published_at"),
                keywords=search_terms,
            )
        except Exception as exc:
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
    """Transform ingestion data for frontend WebSocket"""

    summary_text = (
        data.get("summary")
        or data.get("english_summary")
        or data.get("text")
        or data.get("headline_ocr")
        or ""
    )
    translation_text = (
        data.get("vietnamese_translation")
        or data.get("subtitle_vi")
        or data.get("vi_translation")
        or ""
    )

    sentiment_score = data.get("sentiment_score", 0.0) or 0.0
    if sentiment_score > 0.1:
        sentiment_label = "Positive"
    elif sentiment_score < -0.1:
        sentiment_label = "Negative"
    else:
        sentiment_label = "Neutral"

    def _extract_keywords_fallback(text: str, limit: int = 5):
        words = [
            w.strip(".,;:!?()[]{}\"'").lower()
            for w in (text or "").split()
            if len(w.strip(".,;:!?()[]{}\"'")) > 3
        ]
        uniq = []
        for w in words:
            if w and w not in uniq:
                uniq.append(w)
            if len(uniq) >= limit:
                break
        return uniq

    keywords = data.get("keywords") or _extract_keywords_fallback(summary_text)

    news_item = {
        "id": str(int(datetime.now().timestamp())),
        "source": data.get("source", "Live"),
        "title": data.get("headline_ocr") or summary_text[:120] or "Breaking News",
        "ocr_text": data.get("headline_ocr", "") or summary_text,
        "english_summary": summary_text,
        "vietnamese_translation": translation_text,
        "timestamp": data.get("timestamp"),
        "sentiment": sentiment_label,
        "keywords": keywords,
    }

    analytics = {
        "sentiment_score": sentiment_score,
        "trending_keywords": keywords,
        "active_sources": 1,
        "total_mentions": 1240,
    }

    subtitle = {
        "text": data.get("subtitle_vi", "Dang phan tich..."),
        "lang": "vi",
        "timestamp": data.get("timestamp"),
    }

    await manager.broadcast({"type": "news", "data": news_item})
    await manager.broadcast({"type": "analytics", "data": analytics})
    await manager.broadcast({"type": "subtitle", "data": subtitle})

    print(f"[WebSocket] Broadcasted: {subtitle['text'][:50]}...")

    # Persist to DB so KG worker can pick it up
    async def _write_to_db():
        from database import SessionLocal

        def _persist():
            db = SessionLocal()
            try:
                ts_str = data.get("timestamp")
                ts_val = None
                if ts_str:
                    try:
                        ts_val = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        ts_val = datetime.utcnow()
                if not summary_text or summary_text.strip() == "{":
                    return
                log = AnalysisLog(
                    source=news_item.get("source"),
                    summary=summary_text,
                    vietnamese_translation=translation_text,
                    raw_text=news_item.get("ocr_text", ""),
                    sentiment_score=sentiment_score,
                    trending_keywords=keywords,
                    video_timestamp=news_item.get("timestamp"),
                    timestamp=ts_val,
                )
                db.add(log)
                db.commit()
            except Exception as exc:
                print(f"[Ingestion->DB] Failed to persist log: {exc}")
                db.rollback()
            finally:
                db.close()

        await asyncio.to_thread(_persist)

    await _write_to_db()


async def _consume_ingestion_queue():
    if not ingestion_queue:
        print("Ingestion queue not configured; skipping consumer.")
        return
    print("Starting ingestion queue consumer...")
    while not _stop_event.is_set():
        try:
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


@app.on_event("startup")
async def startup_event():
    global consumer_task, kg_worker_task
    print("Starting Media Monitor API Gateway...")
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
    return {"message": "Media Monitor API Gateway is running"}


@app.post("/chat")
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    result = await answer_question(request.question, db)
    return result


@app.post("/crawl")
async def crawl_news(request: CrawlRequest, background_tasks: BackgroundTasks):
    keyword = (request.keyword or "").strip()
    if not keyword:
        raise HTTPException(status_code=400, detail="Keyword is required")

    source_type = (request.source_type or "news").lower()
    do_news = source_type in ("news", "both")
    do_social = source_type in ("social", "both")
    req_lang = (request.lang or request.language or "en") if hasattr(request, "language") else (request.lang or "en")
    req_source_id = request.source_id or request.source
    req_sources = request.sources or ([] if not req_source_id else [req_source_id])

    news_items: list[dict] = []
    social_items: list[dict] = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        if do_news:
            news_data_api_key = os.getenv("NEWS_DATA_API_KEY") or os.getenv("NEWSDATA_API_KEY") or os.getenv("NEWSDATA_IO_API_KEY")
            if news_data_api_key:
                params = {
                    "apikey": news_data_api_key,
                    "q": keyword,
                    "language": req_lang or "en",
                    "size": min(max(request.limit, 1), 20),
                }
                if request.country:
                    params["country"] = request.country.lower()
                if req_source_id:
                    params["source_id"] = req_source_id
                if req_sources:
                    params["source_id"] = ",".join(req_sources)
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
                    "language": req_lang or "en",
                    "sortBy": "publishedAt",
                    "pageSize": min(max(request.limit, 1), 20),
                    "apiKey": api_key,
                }
                if request.country:
                    params["country"] = request.country.lower()
                if req_sources:
                    params["sources"] = ",".join(req_sources)
                elif req_source_id:
                    params["sources"] = req_source_id
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
                # For demo: always take the first 1-2 posts from each feed, ignore keyword filtering
                for entry in feed.entries[:2]:
                    title = entry.get("title") or ""
                    desc = entry.get("summary") or ""
                    rss_items.append(
                        {
                            "title": title,
                            "description": desc,
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

    # Combine rss with news for return + optional Neo4j upsert
    if rss_items:
        if news_items:
            news_items.extend(rss_items)
        else:
            news_items = rss_items

    # Translate crawled content to Vietnamese (best effort, skipped if no translation API key is configured)
    translation_api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    translation_client = (
        OpenAI(
            api_key=translation_api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1"),
        )
        if translation_api_key
        else None
    )
    if translation_client:
        for item in news_items:
            combined_text = " ".join(
                [
                    str(item.get("title") or "").strip(),
                    str(item.get("description") or "").strip(),
                ]
            ).strip()
            text_for_translation = combined_text or item.get("description") or item.get("title") or ""
            translated = _translate_to_vi(text_for_translation, client=translation_client)
            if translated:
                item["vietnamese_translation"] = translated
        for item in social_items:
            text_for_translation = item.get("description") or item.get("title") or ""
            translated = _translate_to_vi(text_for_translation, client=translation_client)
            if translated:
                item["vietnamese_translation"] = translated

    if neo4j_client and news_items:
        terms = [t.strip() for t in request.keyword.split(",")] if request.keyword else []
        background_tasks.add_task(_background_upsert_crawled_news, news_items, terms)

    # Persist crawled items to AnalysisLog (ignore malformed summaries)
    def _persist_crawl_items(items: list[dict]):
        if not items:
            return
        db = SessionLocal()
        try:
            for item in items:
                summary_text = item.get("title") or item.get("description") or ""
                if not summary_text or summary_text.strip() == "{":
                    continue
                ts_val = None
                ts_str = item.get("published_at")
                if ts_str:
                    try:
                        ts_val = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        ts_val = None
                log = AnalysisLog(
                    source=item.get("source"),
                    summary=summary_text,
                    vietnamese_translation=item.get("vietnamese_translation"),
                    raw_text=item.get("description") or "",
                    sentiment_score=0.0,
                    trending_keywords=[],
                    video_timestamp=None,
                    timestamp=ts_val,
                )
                db.add(log)
            db.commit()
        except Exception as exc:
            print(f"[Crawl->DB] Failed to persist crawled items: {exc}")
            db.rollback()
        finally:
            db.close()

    # Save news + rss + social items (they're already combined for news_items)
    try:
        _persist_crawl_items(news_items + social_items)
    except Exception as exc:
        print(f"[Crawl] Persist error: {exc}")

    return {
        "source_type": source_type,
        "news": {"count": len(news_items), "items": news_items},
        "social": {"count": len(social_items), "items": social_items},
        "rss": {"count": len(rss_items), "items": rss_items},
    }


@app.post("/whisper/transcribe")
async def whisper_transcribe(file: UploadFile = File(...)):
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


# --- Person service proxy helpers ---


async def _proxy_people_search(q: str, limit: int = 5, include_social: bool = False):
    params = {"q": q, "limit": limit, "include_social": include_social}
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{PERSON_SERVICE_URL}/people/search", params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def _proxy_people_search_face(file: UploadFile, limit: int = 5, include_social: bool = False):
    form = {"file": (file.filename or "face.jpg", await file.read(), file.content_type or "image/jpeg")}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{PERSON_SERVICE_URL}/people/search/face",
            params={"limit": limit, "include_social": include_social},
            files=form,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def _proxy_person_social_crawl(person_id: str, confirm: bool = False):
    params = {"confirm": str(bool(confirm)).lower()}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{PERSON_SERVICE_URL}/people/{person_id}/social-crawl", params=params)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


@app.get("/people/search")
async def proxy_people_search(q: str, limit: int = 5, include_social: bool = False):
    """Proxy to person-service search (text)."""
    return await _proxy_people_search(q, limit, include_social)


@app.post("/people/search/face")
async def proxy_people_search_face(file: UploadFile = File(...), limit: int = 5, include_social: bool = False):
    """Proxy to person-service face search."""
    return await _proxy_people_search_face(file, limit, include_social)


@app.get("/people/social/preview")
async def person_social_preview(person_id: str = Query(..., description="Person ID")):
    """Get suggested X account/social graph for a person (no Neo4j writes)."""
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id is required")
    return await _proxy_person_social_crawl(person_id, confirm=False)


@app.post("/people/social/crawl")
async def person_social_crawl(person_id: str = Query(..., description="Person ID")):
    """Confirm and persist social graph into Neo4j, returning KG cypher."""
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id is required")
    data = await _proxy_person_social_crawl(person_id, confirm=True)
    person = data.get("person") or {"id": person_id}
    social_graph = data.get("social_graph") or {}
    if social_graph:
        try:
            _write_social_graph_to_neo4j(social_graph)
        except Exception as exc:
            # Surface Neo4j failures so UI knows crawl did not persist
            raise HTTPException(status_code=503, detail=f"Failed to write social graph: {exc}") from exc
    cypher = None
    if person.get("name"):
        escaped_name = str(person["name"]).replace('"', '\\"')
        cypher = f'''
        MATCH (p:Person)
        WHERE toLower(p.name) = toLower("{escaped_name}")
        OPTIONAL MATCH (p)-[r1:POSTED]->(po:Post)
        OPTIONAL MATCH (po)<-[r2:COMMENTED_ON]-(a:Account)
        RETURN p, po, r1, r2, a
        LIMIT 200
        '''
    return {
        "person": person,
        "social_graph": social_graph,
        "cypher": cypher,
        "status": data.get("status"),
        "primary_account": data.get("primary_account"),
        "message": data.get("message"),
    }


@app.get("/people/crawl-kg")
async def crawl_person_kg(person_id: str = Query(..., description="Person ID"), confirm: bool = False):
    """
    Two-step social crawl:
    - confirm=false: return suggested X account/social graph (no DB write)
    - confirm=true: write social graph to Neo4j and return KG cypher
    """
    if not person_id:
        raise HTTPException(status_code=400, detail="person_id is required")
    data = await _proxy_person_social_crawl(person_id, confirm=confirm)
    person = data.get("person") or {"id": person_id}
    social_graph = data.get("social_graph") or {}
    if confirm and social_graph:
        _write_social_graph_to_neo4j(social_graph)
    cypher = None
    if person.get("name"):
        escaped_name = str(person["name"]).replace('"', '\\"')
        cypher = f'''
        MATCH (n:Person)
        WHERE toLower(n.name) = toLower("{escaped_name}")
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n, r, m
        LIMIT 200
        '''
    return {
        "person": person,
        "social_graph": social_graph,
        "cypher": cypher,
        "status": data.get("status"),
        "primary_account": data.get("primary_account"),
        "message": data.get("message"),
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
        "enabled": True,
    }
    merged = {**defaults, **{k: v for k, v in cfg.items() if v is not None}}
    merged["running"] = processing_enabled
    return merged


@app.post("/asr/config")
async def asr_config(cfg: dict):
    if not ingestion_queue:
        raise HTTPException(status_code=503, detail="Ingestion queue not configured")
    allowed_keys = {"sources", "capture_seconds", "break_seconds", "capture_rate", "enabled"}
    clean = {k: v for k, v in cfg.items() if k in allowed_keys}
    ingestion_queue.save_config(clean)
    updated = ingestion_queue.load_config()
    updated["running"] = processing_enabled
    return updated


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
    global processing_enabled, consumer_task
    if req.enabled == processing_enabled:
        return {"enabled": processing_enabled}

    if not req.enabled:
        processing_enabled = False
        _stop_event.set()
        if consumer_task:
            consumer_task.cancel()
            consumer_task = None
        if ingestion_queue:
            cfg = ingestion_queue.load_config() or {}
            cfg["enabled"] = False
            ingestion_queue.save_config(cfg)
        return {"enabled": False}

    processing_enabled = True
    _stop_event.clear()
    if ingestion_queue:
        cfg = ingestion_queue.load_config() or {}
        cfg["enabled"] = True
        ingestion_queue.save_config(cfg)
        consumer_task = asyncio.create_task(_consume_ingestion_queue())
        # If queue is empty, send last 5 news items immediately to clients
        try:
            if ingestion_queue.length() == 0:
                db = SessionLocal()
                try:
                    recent = (
                        db.query(AnalysisLog)
                        .order_by(AnalysisLog.timestamp.desc())
                        .limit(5)
                        .all()
                    )
                    for log in reversed(recent):
                        msg = {
                            "type": "news",
                            "data": {
                                "id": str(log.id),
                                "source": log.source or "Live",
                                "title": log.summary or "",
                                "ocr_text": log.raw_text or "",
                                "english_summary": log.summary or "",
                                "vietnamese_translation": log.vietnamese_translation or "",
                                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                                "sentiment": "Neutral",
                                "keywords": log.trending_keywords or [],
                            },
                        }
                        await manager.broadcast(msg)
                finally:
                    db.close()
        except Exception as exc:
            print(f"[LiveToggle] Failed to send recent news: {exc}")
    return {"enabled": True}


@app.get("/live/state")
async def live_state():
    """Return current live-processing state and ingestion config."""
    cfg = ingestion_queue.load_config() if ingestion_queue else {}
    return {
        "enabled": bool(processing_enabled),
        "ingestion_enabled": bool(cfg.get("enabled")) if cfg else bool(processing_enabled),
        "config": cfg or {},
    }
