# OSINT Frontend (React + Vite)

This package hosts the real-time OSINT dashboard that ships with the monorepo. It was migrated from `demo-app/frontend` and keeps the same UX (live monitor, KG explorer, person search, document and news workflows).

## Requirements

- Node 18+ (Node 20 is used in CI/Docker)
- npm 9+

## Environment

Create a `.env` (or copy `.env.example`) with the URLs to the backend and optional external services:

```
VITE_API_URL=http://localhost:8000          # REST endpoints
VITE_WS_URL=ws://localhost:8000/ws/monitor  # live updates
VITE_NEO4J_URI=bolt://localhost:7687        # browser Neo4j viz
VITE_NEO4J_USER=neo4j
VITE_NEO4J_PASSWORD=please-change-me
VITE_PERSON_API_URL=                        # optional external face dataset service
```

The `person.html` entry point renders the standalone person search UI. Both HTML entry points are wired through the custom inputs defined in `vite.config.js`.

## Scripts

- `npm install` – install dependencies
- `npm run dev` – start the Vite dev server (pass `-- --host` to bind to all interfaces)
- `npm run build` – generate the static production build (consumed by Docker/CI)
- `npm run preview` – preview the production build locally
- `npm run lint` – run ESLint using the provided config

## Styling

Tailwind CSS powers the utility classes for quick iteration. Custom colors/animations live in `tailwind.config.js`, and component-specific overrides live alongside each component.
