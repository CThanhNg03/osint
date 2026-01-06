"""FastAPI application factory wiring routes and middleware."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.backend.src.infrastructure.settings import settings
from apps.backend.src.infrastructure.persistence import models
from apps.backend.src.infrastructure.persistence.database import engine
from apps.backend.src.common.logging import configure_logging
from apps.backend.src.api.routes import asr, documents, kg, news, people, live

configure_logging()
models.Base.metadata.create_all(bind=engine)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="OSINT Toolkit")

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(asr.router)
    app.include_router(documents.router)
    app.include_router(kg.router)
    app.include_router(news.router)
    app.include_router(people.router)
    app.include_router(live.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
