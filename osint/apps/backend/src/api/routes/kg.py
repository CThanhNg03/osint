"""Knowledge graph endpoints."""

from fastapi import APIRouter
from apps.backend.src.api.schemas import kg as schemas
from apps.backend.src.usecases import search_kg, person_analysis_report

router = APIRouter(prefix="/kg", tags=["kg"])


@router.get("/search", response_model=schemas.GraphResponse)
async def search(query: str):
    result = search_kg.execute(query)
    return schemas.GraphResponse(**result)


@router.post("/person-analysis")
async def person_analysis(name: str, bio: str):
    return person_analysis_report.execute(name, bio)
