# OSINT Toolkit

This repository now hosts the complete Media Monitor stack: the FastAPI backend (migrated from `demo-app/backend`) and the React/Vite frontend (migrated from `demo-app/frontend`). The backend streams ASR events, proxies person-dataset operations, enriches data with Neo4j, and exposes the REST/WebSocket APIs the dashboard expects.

## Project layout
- `apps/backend` – FastAPI gateway, auxiliary workers (`ingestor_service.py`, `kg_worker.py`), and the standalone person service.
- `apps/frontend` – React dashboard with live monitor, KG explorer, person search, and document workflows.
- `demo-app` – Original reference copy kept for posterity.

## Local development
### Backend
1. `cd apps/backend`
2. `python -m venv .venv && .venv\\Scripts\\activate` (PowerShell) or `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `cp .env.example .env` and fill in API keys/URLs (Postgres, Redis, Neo4j, Ollama embedding endpoint, News/X tokens, etc.).
5. Run `uvicorn api_gateway:app --reload --host 0.0.0.0 --port 8000`

Supporting services: Postgres (with pgvector), Redis, Neo4j, and an embedding provider (Ollama or OpenAI/Groq). The ingestion worker (`ingestor_service.py`) and person service (`person_service.py`) can be launched separately when testing those flows.

### Frontend
1. `cd apps/frontend && npm install`
2. Copy `.env.example` to `.env` and set `VITE_API_URL`, `VITE_WS_URL`, `VITE_PERSON_API_URL`, and `VITE_NEO4J_*` to match your backend/Neo4j endpoints.
3. `npm run dev` (append `-- --host` if you need to expose it beyond localhost)

## Environment variables
See the root `.env.example` (mirrors `apps/backend/.env.example` + frontend values). Key entries:
- Core AI + embeddings: `GROQ_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `EMBEDDING_*`
- Storage/services: `DATABASE_URL` (default `postgresql://user:password@postgres:5432/mediamonitor`), `REDIS_URL`, `NEO4J_URI`, `IMAGE_STORE_PATH`
- External data: `NEWSAPI_KEY`, `NEWS_DATA_API_KEY`, `X_BEARER_TOKEN`
- Streaming + capture: `WHISPER_MODEL`, `WHISPER_SOURCES`, capture timing knobs
- Person dataset routing: `PERSON_SERVICE_URL`, `PERSON_SERVICE_PORT`
- Frontend build: `VITE_API_URL`, `VITE_WS_URL`, `VITE_NEO4J_*`, `VITE_PERSON_API_URL`

## Docker stack
1. Copy `.env.example` to `.env` and set credentials/API keys. Defaults point the services at the Compose network (`postgres`, `redis`, `neo4j`, `embedding`, `person-service`).
2. From repo root, run `docker compose up --build`. Services included:
   - `backend` – FastAPI API gateway (uvicorn)
   - `frontend` – React dashboard served through nginx
   - `postgres` – pgvector-enabled Postgres datastore
   - `redis` – event queue for ASR ingestion and config
   - `embedding` – Ollama serving the embedding model (override if you use Groq/OpenAI)
   - `neo4j` – graph database for KG explorer
   - `ingestor` – background worker that captures livestreams and pushes ASR payloads into Redis
   - `person-service` – standalone dataset service with face embeddings + storage
3. Visit `http://localhost:5173` for the UI, `http://localhost:8000/docs` for API docs, and `http://localhost:7474` for the Neo4j browser (default creds `neo4j/please-change-me`).

Each container reads from the shared `.env`, so update that file when pointing at managed services instead of the Compose defaults.
