# OSINT Toolkit

This repository contains a lightweight OSINT backend (FastAPI) and a small React frontend organized using clear layers and feature-based routing.

## Migration Notes
- `demo-app/backend/api_gateway.py` ➜ `apps/backend/src/main.py` plus individual route modules under `apps/backend/src/api/routes/`
- Websocket connection handling ➜ `apps/backend/src/common/websocket.py`
- Neo4j and graph helpers ➜ `apps/backend/src/domain/services/kg_service.py` and `apps/backend/src/infrastructure/graph/neo4j_client.py`
- Document parsing and summarization ➜ `apps/backend/src/domain/services/document_service.py`
- Translation and keyword helpers ➜ `apps/backend/src/domain/services/translation_service.py` and `apps/backend/src/domain/policies/keywords.py`
- Frontend single-page Next.js view ➜ Vite multi-page React app under `apps/frontend` with pages for News, Live Monitor, Knowledge Graph, People, Documents, and ASR.

### Running the backend
1. Install dependencies: `pip install -r apps/backend/requirements.txt`
2. Start the API: `uvicorn apps.backend.src.main:app --reload`

### Running the frontend
1. Install dependencies: `cd apps/frontend && npm install`
2. Start the dev server: `npm run dev`

### Environment variables
- `OPENAI_API_KEY` for LLM calls
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` for graph storage
- `DATABASE_URL` for SQLAlchemy persistence
- `PERSON_SERVICE_URL`, `NEWS_API_KEY`, `TWITTER_BEARER_TOKEN` for external data sources
- `CORS_ORIGINS` optional comma-separated allowed origins

