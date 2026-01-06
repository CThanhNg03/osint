"""News crawling endpoints."""

from fastapi import APIRouter
from apps.backend.src.api.schemas import news as schemas
from apps.backend.src.usecases import crawl_news

router = APIRouter(tags=["news"])


@router.get("/crawl", response_model=schemas.NewsResponse)
async def crawl(query: str):
    items = crawl_news.execute(query)
    return schemas.NewsResponse(items=items)


@router.get("/news/sources")
async def sources():
    return {"sources": ["newsapi", "rss"]}
