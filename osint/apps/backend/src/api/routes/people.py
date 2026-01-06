"""People search endpoints."""

from fastapi import APIRouter, UploadFile, File
from apps.backend.src.api.schemas import people as schemas
from apps.backend.src.usecases import people_search, people_face_search, people_social_preview, people_social_crawl

router = APIRouter(prefix="/people", tags=["people"])


@router.get("/search", response_model=schemas.PeopleResponse)
async def search(query: str):
    return schemas.PeopleResponse(**people_search.execute(query))


@router.post("/search/face")
async def face_search(file: UploadFile = File(...)):
    content = await file.read()
    return people_face_search.execute(content)


@router.get("/social/preview")
async def social_preview(username: str):
    return people_social_preview.execute(username)


@router.get("/social/crawl")
async def social_crawl(username: str):
    return people_social_crawl.execute(username)
